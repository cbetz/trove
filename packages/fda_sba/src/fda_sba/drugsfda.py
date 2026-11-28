"""Application records from openFDA's Drugs@FDA endpoint.

``https://api.fda.gov/drug/drugsfda.json`` is FDA's public API over the same
data as the drugs@FDA website: for each application, its sponsor, its products
and its submissions, and for each submission the documents FDA posted (label,
letter, review) with their URLs. It is the programmatic route FDA provides, and
the index's source for document links. The website's application pages
(``fda_sba.overview``) are only read from a local cache, as a fallback for an
application openFDA does not have.

Two lookups:

- by application number (``fetch_application``), for approvals whose number
  FDA's annual list or its compilation gives;
- by brand name (``find_application``), for approvals FDA lists without a
  link. A match is accepted only when the application's original approval
  date agrees with the list's.

Without an API key openFDA allows 240 requests a minute and 1,000 a day per
address. This module makes one request per application, waits between
requests, caches every answer, and stops for the run if told to slow down.
To re-read FDA's current data, delete the cache directory and rebuild.
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

from fda_sba.overview import _normalize as normalize_company

API_URL = "https://api.fda.gov/drug/drugsfda.json"
USER_AGENT = "trove/fda_sba (+https://github.com/cbetz/trove)"
REQUEST_DELAY = 0.5
# How far the original approval date in Drugs@FDA may sit from the date on
# FDA's annual list for a brand-name match to count. The list is hand-kept and
# has been a day off before (Tzield, 2022).
MAX_DATE_GAP_DAYS = 3

_rate_limited = False


def _query(search: str, limit: int) -> dict:
    """Send one search to openFDA. A "no matches" answer is an empty result."""
    global _rate_limited
    if _rate_limited:
        raise RuntimeError("openFDA asked this run to slow down; not sending more requests")
    query = urlencode({"search": search, "limit": limit})
    req = Request(f"{API_URL}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as exc:
        if exc.code == 404:  # openFDA's "no matches found"
            return {"results": [], "meta": {}}
        if exc.code == 429:
            _rate_limited = True
            raise RuntimeError("openFDA answered 429 (rate limit)") from exc
        raise
    finally:
        time.sleep(REQUEST_DELAY)


def _slim(record: dict, key: str, payload: dict) -> dict:
    """The parts of an openFDA application record the index uses."""
    return {
        "application": key,
        "fetched": date.today().isoformat(),
        "last_updated": payload.get("meta", {}).get("last_updated"),
        "sponsor_name": record.get("sponsor_name"),
        "products": [{"brand_name": p.get("brand_name")} for p in record.get("products", [])],
        "submissions": [
            s for s in record.get("submissions", []) if s.get("submission_type") == "ORIG"
        ],
    }


def fetch_application(
    application_type: str,
    application_number: str,
    cache_dir: Path | str = "data/raw/fda/drugsfda",
    *,
    force: bool = False,
) -> Path:
    """Fetch and cache openFDA's Drugs@FDA record for one application.

    The cached file keeps the sponsor, the products' brand names, the ORIG
    submissions and their documents, the day it was fetched and openFDA's
    ``last_updated`` stamp. An application openFDA does not have is
    cached as an empty record.
    """
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    key = f"{application_type}{application_number}"
    target = cache / f"{key}.json"
    if target.exists() and not force:
        return target
    payload = _query(f'application_number:"{key}"', 1)
    record = (payload.get("results") or [{}])[0]
    target.write_text(json.dumps(_slim(record, key, payload), indent=1) + "\n")
    return target


def find_application(
    brand_name: str,
    approval_date: date | str,
    cache_dir: Path | str = "data/raw/fda/drugsfda",
) -> dict | None:
    """Find the application behind a brand name FDA listed without a link.

    Searches openFDA for products with that brand name and returns the cached
    record of the one application whose original approval falls within
    ``MAX_DATE_GAP_DAYS`` of ``approval_date``. Returns ``None`` when no
    application, or more than one, fits: a wrong match would attach another
    product's documents to the page.
    """
    cache = Path(cache_dir)
    names = cache / "by-name"
    names.mkdir(parents=True, exist_ok=True)
    target = names / f"{re.sub(r'[^a-z0-9]+', '-', brand_name.lower()).strip('-')}.json"
    if target.exists():
        keys = json.loads(target.read_text())["applications"]
    else:
        phrase = brand_name.replace('"', " ")
        payload = _query(f'products.brand_name:"{phrase}"', 10)
        keys = []
        for record in payload.get("results") or []:
            key = record.get("application_number")
            if not key:
                continue
            keys.append(key)
            (cache / f"{key}.json").write_text(
                json.dumps(_slim(record, key, payload), indent=1) + "\n"
            )
        target.write_text(
            json.dumps(
                {
                    "brand_name": brand_name,
                    "fetched": date.today().isoformat(),
                    "applications": keys,
                },
                indent=1,
            )
            + "\n"
        )
    wanted = date.fromisoformat(str(approval_date)[:10])
    fits = []
    for key in keys:
        record = json.loads((cache / f"{key}.json").read_text())
        if not any(_same_brand(brand_name, p.get("brand_name")) for p in record["products"]):
            continue
        approved = parse_original_approval(record)["approval_date"]
        if approved and abs((date.fromisoformat(approved) - wanted).days) <= MAX_DATE_GAP_DAYS:
            fits.append(record)
    if len(fits) == 1:
        return fits[0]
    if len(fits) > 1:
        warnings.warn(
            f"{brand_name}: {len(fits)} Drugs@FDA applications share the name and approval "
            "date; none used",
            stacklevel=2,
        )
    return None


def _same_brand(listed: str, product: str | None) -> bool:
    """True when a Drugs@FDA product name is the listed brand, device suffix or not.

    Drugs@FDA names some products with a presentation after the brand
    (``AWIQLI FLEXTOUCH``, ``LIFYORLI (COPACKAGED)``); FDA's list gives the
    brand alone.
    """
    a, b = listed.strip().lower(), (product or "").strip().lower()
    return bool(a) and (b == a or (b.startswith(a) and not b[len(a)].isalnum()))


def parse_original_approval(record: dict) -> dict[str, str | None]:
    """Return what FDA recorded for an application's original approval.

    Reads the lowest-numbered ``ORIG`` submission whose status is ``AP``
    (approved): ``approval_letter_url``, ``review_url``, ``label_url``,
    ``submission_classification``, ``approval_date`` (ISO),
    ``review_designation`` (``Priority`` or ``Standard``) and ``orphan``
    (``Yes`` when the submission carries the orphan property, else ``None``).
    When FDA posted a letter or label more than once (a corrected letter, say)
    the latest is used; for the review it is the earliest review index. Every
    value is ``None`` when there is no such submission.
    """
    out: dict[str, str | None] = {
        "approval_letter_url": None,
        "review_url": None,
        "label_url": None,
        "submission_classification": None,
        "approval_date": None,
        "review_designation": None,
        "orphan": None,
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
    priority = (first.get("review_priority") or "").strip().upper()
    if priority in ("PRIORITY", "STANDARD"):
        out["review_designation"] = priority.capitalize()
    properties = {(p.get("code") or "").lower() for p in first.get("submission_property_type", [])}
    if "orphan" in properties:
        out["orphan"] = "Yes"
    for kind, key in (
        ("Letter", "approval_letter_url"),
        ("Review", "review_url"),
        ("Label", "label_url"),
    ):
        docs = [d for d in first.get("application_docs", []) if d.get("type") == kind]
        if kind == "Review" and docs:
            # The approval package is the review index ("...TOC.html") posted
            # with the original approval; FDA sometimes files a later review
            # under the same submission (Imdelltra, 2026).
            index = [d for d in docs if "toc" in (d.get("url") or "").lower()]
            url = min(index or docs, key=lambda d: d.get("date") or "").get("url")
            out[key] = re.sub(r"^http://", "https://", url) if url else None
        elif docs:
            url = max(docs, key=lambda d: d.get("date") or "").get("url")
            # openFDA records a few document links with http://; FDA serves https.
            out[key] = re.sub(r"^http://", "https://", url) if url else None
    return out


def fill_application_numbers(
    df: pd.DataFrame,
    cache_dir: Path | str = "data/raw/fda/drugsfda",
) -> pd.DataFrame:
    """Give rows FDA listed without an application number the one openFDA has.

    FDA's annual list does not always link a drug name to its label (the 2026
    list links none). For those rows the brand name and approval date are
    looked up with ``find_application``; a match sets ``application_number``,
    ``application_type`` and ``drugs_at_fda_url``. Rows with a number are left
    alone, as are rows with no confident match.
    """
    out = df.copy()
    numbers = out["application_number"].tolist()
    kinds = out["application_type"].tolist()
    urls = out["drugs_at_fda_url"].tolist()
    for i, number in enumerate(numbers):
        if isinstance(number, str) and number:
            continue
        name = out["drug_name"].iloc[i]
        try:
            record = find_application(name, out["approval_date"].iloc[i], cache_dir)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"{name}: openFDA brand-name lookup failed ({exc!r})", stacklevel=2)
            continue
        match = re.fullmatch(r"(NDA|BLA)(\d{6})", (record or {}).get("application", ""))
        if not match:
            warnings.warn(f"{name}: no application found in openFDA's Drugs@FDA data", stacklevel=2)
            continue
        kinds[i], numbers[i] = match.groups()
        urls[i] = (
            "https://www.accessdata.fda.gov/scripts/cder/daf/"
            f"index.cfm?event=overview.process&ApplNo={numbers[i]}"
        )
    out["application_number"] = numbers
    out["application_type"] = kinds
    out["drugs_at_fda_url"] = urls
    return out


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def enrich_from_drugsfda(
    df: pd.DataFrame,
    cache_dir: Path | str = "data/raw/fda/drugsfda",
) -> pd.DataFrame:
    """Bring each row up to date with openFDA's Drugs@FDA record of its application.

    Run after the cached drugs@FDA pages and FDA's compilation have been
    applied. For every row with an application number:

    - ``approval_letter_url``, ``review_url`` and (NDAs only)
      ``submission_classification`` take openFDA's value when it has one, since
      it is the fresher read; a value openFDA lacks is kept.
    - ``label_pdf_url`` and ``sponsor`` are filled only where empty.
    - ``review_designation`` and ``orphan_drug_designation`` are filled only on
      rows FDA's compilation does not cover, and ``designations_source`` says
      which source a row's values came from (``compilation`` or ``openfda``).
      Drugs@FDA's orphan flag belongs to the application, so it can be set for
      a use other than the one approved; an application without it is left
      empty, not "No". openFDA records no accelerated approval, breakthrough or
      fast track status, so those stay empty on such rows, as do dosage form
      and route (its product fields are unreliable for recent approvals).
    - ``approval_date`` takes the original approval date in Drugs@FDA when the
      two differ within a year; a gap across years is reported and left.

    Adds ``documents_read``: the day openFDA was read, on every row whose
    application it has.
    """
    out = df.copy()
    doc_columns = (
        "approval_letter_url",
        "review_url",
        "label_pdf_url",
        "submission_classification",
    )
    fill_columns = ("sponsor", "review_designation", "orphan_drug_designation")
    values = {
        c: [_text(v) for v in out[c].tolist()] if c in out.columns else [None] * len(out)
        for c in (*doc_columns, *fill_columns)
    }
    source = ["compilation" if v else None for v in values["review_designation"]]
    read: list[str | None] = [None] * len(out)
    dates = list(out["approval_date"])
    kinds = out["application_type"].tolist()
    numbers = out["application_number"].tolist()
    names = out["drug_name"].tolist()
    for i, (kind, number) in enumerate(zip(kinds, numbers, strict=True)):
        if not (_text(kind) and _text(number)):
            continue
        try:
            record = json.loads(fetch_application(kind, number, cache_dir).read_text())
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"{kind} {number}: no openFDA Drugs@FDA record ({exc!r})", stacklevel=2)
            continue
        found = parse_original_approval(record)
        if not found["approval_date"]:
            continue
        read[i] = record.get("fetched")

        listed = dates[i]
        official = date.fromisoformat(found["approval_date"])
        if hasattr(listed, "year") and official != listed:
            if official.year == listed.year:
                dates[i] = official
            else:
                warnings.warn(
                    f"{names[i]}: approval date {listed.isoformat()} and openFDA's original "
                    f"approval ({official.isoformat()}) disagree by year; keeping the list date",
                    stacklevel=2,
                )

        for column in ("approval_letter_url", "review_url"):
            if found[column]:
                values[column][i] = found[column]
        if kind == "NDA" and found["submission_classification"]:
            # drugs@FDA's own pages show a classification for NDAs only; keep
            # BLAs blank so the column means one thing.
            values["submission_classification"][i] = found["submission_classification"]
        if values["label_pdf_url"][i] is None:
            values["label_pdf_url"][i] = found["label_url"]

        if values["sponsor"][i] is None and _text(record.get("sponsor_name")):
            values["sponsor"][i] = normalize_company(record["sponsor_name"])
        if source[i] is None and found["review_designation"]:
            values["review_designation"][i] = found["review_designation"]
            values["orphan_drug_designation"][i] = found["orphan"]
            source[i] = "openfda"
    for c in (*doc_columns, *fill_columns):
        out[c] = values[c]
    out["approval_date"] = dates
    out["designations_source"] = source
    out["documents_read"] = read
    return out
