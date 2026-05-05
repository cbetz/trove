"""Fetch and parse the drugs@FDA application overview page.

The overview page (e.g. https://www.accessdata.fda.gov/scripts/cder/daf/
index.cfm?event=overview.process&ApplNo=218614) carries the sponsor's
name, the marketing status, and links to every approval-package
document for an application. v0.1 of this module just extracts the
sponsor; richer parsing is a v0.2 add.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
from lxml import html

OVERVIEW_URL_TEMPLATE = (
    "https://www.accessdata.fda.gov/scripts/cder/daf/"
    "index.cfm?event=overview.process&ApplNo={appl_no}"
)
USER_AGENT = "trove/fda_sba (+https://github.com/cbetz/trove)"

# The overview page renders the sponsor as
#   <span class="prodBoldText">Company:</span> <span class="appl-details-top">{NAME} ...</span>
# The value cell is heavily padded with trailing whitespace.
_COMPANY_RE = re.compile(
    r'Company:\s*</span>\s*<span[^>]*class="appl-details-top"[^>]*>([^<]+)',
    re.I | re.S,
)


def fetch_application_overview(
    appl_no: str,
    cache_dir: Path | str = "data/raw/fda/overview",
    *,
    force: bool = False,
) -> Path:
    """Download the drugs@FDA overview HTML for ``appl_no`` and cache it."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{appl_no}.html"
    if target.exists() and not force:
        return target
    url = OVERVIEW_URL_TEMPLATE.format(appl_no=appl_no)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        target.write_bytes(resp.read())
    return target


def parse_sponsor(html_bytes: bytes) -> str | None:
    """Return the sponsor (Company) name from a drugs@FDA overview HTML.

    Falls back to None if the field can't be located.
    """
    if not html_bytes:
        return None
    text = html_bytes.decode("utf-8", errors="replace")
    m = _COMPANY_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Title-case is more readable than the all-caps FDA stores. Apply only
    # when the value is fully uppercase; preserve mixed-case as-is.
    return _normalize(raw)


def enrich_with_sponsor(
    df: pd.DataFrame,
    cache_dir: Path | str = "data/raw/fda/overview",
    *,
    progress: bool = True,
) -> pd.DataFrame:
    """Add a ``sponsor`` column to a DataFrame produced by ``build_index``.

    Skips rows without an ``application_number``. Caches the overview HTML
    per app number so re-runs are free after the first.
    """
    out = df.copy()
    sponsors: list[str | None] = []
    cache = Path(cache_dir)
    apps = out["application_number"].fillna("").tolist()
    for i, appl_no in enumerate(apps, start=1):
        if not appl_no:
            sponsors.append(None)
            continue
        if progress and i % 25 == 0:
            print(f"  sponsor enrichment: {i}/{len(apps)}", flush=True)
        try:
            page = fetch_application_overview(appl_no, cache)
            sponsors.append(parse_sponsor(page.read_bytes()))
        except Exception as exc:  # noqa: BLE001
            if progress:
                print(f"    skip {appl_no}: {exc!r}")
            sponsors.append(None)
    out["sponsor"] = sponsors
    return out


def _normalize(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        return name
    letters = [c for c in name if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        # Title-case all-caps names but keep recognized acronyms uppercase.
        keep_upper = {"INC", "LLC", "LTD", "LP", "LLP", "PLC", "USA", "AG", "SA", "SAS",
                      "SPA", "BV", "GMBH", "CO", "CORP", "AB", "AS", "OY"}
        words = [w for w in re.split(r"\s+", name) if w]
        out = []
        for w in words:
            stripped = re.sub(r"[^A-Z]", "", w)
            if stripped in keep_upper:
                out.append(w)
            else:
                out.append(w[0] + w[1:].lower() if len(w) > 1 else w)
        return " ".join(out)
    return name
