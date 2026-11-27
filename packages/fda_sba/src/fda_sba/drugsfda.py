"""Original-approval documents from openFDA's Drugs@FDA endpoint.

``https://api.fda.gov/drug/drugsfda.json`` is FDA's public API over the same
data as the drugs@FDA website: for each application, its sponsor and its
submissions, and for each submission the documents FDA posted (label, letter,
review) with their URLs. It is the programmatic route FDA provides; the
website's application pages (``fda_sba.overview``) are a fallback that FDA does
not always serve to scripts.

Without an API key openFDA allows 240 requests a minute and 1,000 a day per
address. This module makes one request per application, waits between
requests, caches every answer, and stops for the run if told to slow down.
"""

from __future__ import annotations

import json
import re
import time
import warnings
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

API_URL = "https://api.fda.gov/drug/drugsfda.json"
USER_AGENT = "trove/fda_sba (+https://github.com/cbetz/trove)"
REQUEST_DELAY = 0.5

_rate_limited = False


def fetch_application(
    application_type: str,
    application_number: str,
    cache_dir: Path | str = "data/raw/fda/drugsfda",
    *,
    force: bool = False,
) -> Path:
    """Fetch and cache openFDA's Drugs@FDA record for one application.

    The cached file keeps the sponsor, the ORIG submissions and their
    documents, the day it was fetched and openFDA's ``last_updated`` stamp. An
    application openFDA does not have is cached as an empty record.
    """
    global _rate_limited
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    key = f"{application_type}{application_number}"
    target = cache / f"{key}.json"
    if target.exists() and not force:
        return target
    if _rate_limited:
        raise RuntimeError("openFDA asked this run to slow down; not sending more requests")
    query = urlencode({"search": f'application_number:"{key}"', "limit": 1})
    req = Request(f"{API_URL}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())
    except HTTPError as exc:
        if exc.code == 404:  # openFDA's "no matches found"
            payload = {"results": [], "meta": {}}
        elif exc.code == 429:
            _rate_limited = True
            raise RuntimeError("openFDA answered 429 (rate limit)") from exc
        else:
            raise
    finally:
        time.sleep(REQUEST_DELAY)
    results = payload.get("results") or [{}]
    record = results[0]
    slim = {
        "application": key,
        "fetched": date.today().isoformat(),
        "last_updated": payload.get("meta", {}).get("last_updated"),
        "sponsor_name": record.get("sponsor_name"),
        "submissions": [
            s for s in record.get("submissions", []) if s.get("submission_type") == "ORIG"
        ],
    }
    target.write_text(json.dumps(slim, indent=1) + "\n")
    return target


def parse_original_approval(record: dict) -> dict[str, str | None]:
    """Return the documents and classification of an application's original approval.

    Reads the lowest-numbered ``ORIG`` submission whose status is ``AP``
    (approved): ``approval_letter_url``, ``review_url``, ``label_url``,
    ``submission_classification`` and ``approval_date`` (ISO). When FDA posted
    a document more than once (a corrected letter, say) the latest is used.
    """
    out: dict[str, str | None] = {
        "approval_letter_url": None,
        "review_url": None,
        "label_url": None,
        "submission_classification": None,
        "approval_date": None,
    }
    approved = [
        s
        for s in record.get("submissions", [])
        if s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP"
    ]
    if not approved:
        return out
    first = min(approved, key=lambda s: int(s.get("submission_number") or 0))
    stamp = first.get("submission_status_date") or ""
    if len(stamp) == 8 and stamp.isdigit():
        out["approval_date"] = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}"
    out["submission_classification"] = first.get("submission_class_code_description") or None
    for kind, key in (
        ("Letter", "approval_letter_url"),
        ("Review", "review_url"),
        ("Label", "label_url"),
    ):
        docs = [d for d in first.get("application_docs", []) if d.get("type") == kind]
        if docs:
            url = max(docs, key=lambda d: d.get("date") or "").get("url")
            # openFDA records a few document links with http://; FDA serves https.
            out[key] = re.sub(r"^http://", "https://", url) if url else None
    return out


def fill_approval_documents(
    df: pd.DataFrame,
    cache_dir: Path | str = "data/raw/fda/drugsfda",
) -> pd.DataFrame:
    """Fill the approval-document columns that the drugs@FDA page pass left empty.

    For each row with an application number, a missing ``approval_letter_url``,
    ``review_url``, ``label_pdf_url`` or ``submission_classification`` is taken
    from openFDA. Values already present are kept. Adds ``documents_read``:
    the day openFDA was read, on rows where it supplied the letter or the
    review, so a page can say how fresh its links are. Warns when openFDA's
    original approval date differs from the row's.
    """
    out = df.copy()
    columns = ("approval_letter_url", "review_url", "label_pdf_url", "submission_classification")
    values = {
        c: [v if isinstance(v, str) and v else None for v in out[c].tolist()] for c in columns
    }
    read: list[str | None] = [None] * len(out)
    kinds = out["application_type"].tolist()
    numbers = out["application_number"].tolist()
    for i, (kind, number) in enumerate(zip(kinds, numbers, strict=True)):
        if not (isinstance(kind, str) and isinstance(number, str) and kind and number):
            continue
        if all(values[c][i] for c in columns if c != "submission_classification"):
            continue
        try:
            record = json.loads(fetch_application(kind, number, cache_dir).read_text())
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"{kind} {number}: no openFDA Drugs@FDA record ({exc!r})", stacklevel=2)
            continue
        docs = parse_original_approval(record)
        listed = out["approval_date"].iloc[i]
        listed = listed.isoformat() if hasattr(listed, "isoformat") else str(listed)
        if docs["approval_date"] and docs["approval_date"] != listed[:10]:
            warnings.warn(
                f"{out['drug_name'].iloc[i]}: approval date {listed[:10]} differs from "
                f"openFDA's original approval ({docs['approval_date']})",
                stacklevel=2,
            )
        supplied = False
        for column, key in (
            ("approval_letter_url", "approval_letter_url"),
            ("review_url", "review_url"),
            ("label_pdf_url", "label_url"),
            ("submission_classification", "submission_classification"),
        ):
            if column == "submission_classification" and kind != "NDA":
                # drugs@FDA's own pages show a classification for NDAs only;
                # keep BLAs blank so the column means one thing.
                continue
            if values[column][i] is None and docs[key]:
                values[column][i] = docs[key]
                supplied = supplied or column in ("approval_letter_url", "review_url")
        if supplied:
            read[i] = record.get("fetched")
    for c in columns:
        out[c] = values[c]
    out["documents_read"] = read
    return out
