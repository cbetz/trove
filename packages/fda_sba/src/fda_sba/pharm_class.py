"""Pharmacologic class for an application, from openFDA's drug label API.

openFDA (https://open.fda.gov/apis/drug/label/) is FDA's public API over
structured product labeling. Each label record carries an ``openfda`` block
that FDA harmonises from the label's indexing data, including the Established
Pharmacologic Class (``pharm_class_epc``, e.g. "Kinase Inhibitor [EPC]") and
the mechanism-of-action class (``pharm_class_moa``). Not every product has
them: FDA fills them only where the active moiety has been indexed.

Without an API key openFDA allows 240 requests a minute and 1,000 a day per
address. This module makes one request per application, waits between
requests, caches every answer, and stops for the run if it is told to slow
down.
"""

from __future__ import annotations

import json
import time
import warnings
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

API_URL = "https://api.fda.gov/drug/label.json"
USER_AGENT = "trove/fda_sba (+https://github.com/cbetz/trove)"
REQUEST_DELAY = 0.5

_rate_limited = False


def fetch_label_records(
    application_type: str,
    application_number: str,
    cache_dir: Path | str = "data/raw/fda/openfda",
    *,
    force: bool = False,
) -> Path:
    """Fetch and cache openFDA's label records for one application.

    An application with no label in openFDA is cached as an empty result, so
    it is not asked for again.
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
    query = urlencode({"search": f'openfda.application_number:"{key}"', "limit": 5})
    req = Request(f"{API_URL}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())
    except HTTPError as exc:
        if exc.code == 404:  # openFDA's "no matches found"
            payload = {"results": []}
        elif exc.code == 429:
            _rate_limited = True
            raise RuntimeError("openFDA answered 429 (rate limit)") from exc
        else:
            raise
    finally:
        time.sleep(REQUEST_DELAY)
    slim = {
        "application": key,
        "results": [
            {"effective_time": r.get("effective_time"), "openfda": r.get("openfda", {})}
            for r in payload.get("results", [])
        ],
    }
    target.write_text(json.dumps(slim, indent=1) + "\n")
    return target


def _strip_tag(value: str) -> str:
    """``Kinase Inhibitor [EPC]`` -> ``Kinase Inhibitor``."""
    return value.rsplit(" [", 1)[0].strip() if value.endswith("]") else value.strip()


def parse_pharm_class(payload: dict) -> dict[str, str | None]:
    """Return the EPC and MoA classes across an application's label records.

    Values are de-duplicated in first-seen order and joined with "; ".
    """
    out: dict[str, str | None] = {"pharm_class_epc": None, "pharm_class_moa": None}
    for field in out:
        seen: list[str] = []
        for record in payload.get("results", []):
            for value in record.get("openfda", {}).get(field) or []:
                value = _strip_tag(value)
                if value and value not in seen:
                    seen.append(value)
        out[field] = "; ".join(seen) or None
    return out


def enrich_with_pharm_class(
    df: pd.DataFrame,
    cache_dir: Path | str = "data/raw/fda/openfda",
) -> pd.DataFrame:
    """Add ``pharm_class_epc`` and ``pharm_class_moa`` columns from openFDA."""
    out = df.copy()
    epc: list[str | None] = []
    moa: list[str | None] = []
    types = out["application_type"].tolist()
    numbers = out["application_number"].tolist()
    for kind, number in zip(types, numbers, strict=True):
        classes: dict[str, str | None] = {"pharm_class_epc": None, "pharm_class_moa": None}
        if isinstance(kind, str) and isinstance(number, str) and kind and number:
            try:
                path = fetch_label_records(kind, number, cache_dir)
                classes = parse_pharm_class(json.loads(path.read_text()))
            except Exception as exc:  # noqa: BLE001
                warnings.warn(f"{kind} {number}: no openFDA label data ({exc!r})", stacklevel=2)
        epc.append(classes["pharm_class_epc"])
        moa.append(classes["pharm_class_moa"])
    out["pharm_class_epc"] = epc
    out["pharm_class_moa"] = moa
    return out
