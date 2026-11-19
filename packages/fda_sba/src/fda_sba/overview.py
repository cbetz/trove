"""Fetch and parse the drugs@FDA application overview page.

The overview page (e.g. https://www.accessdata.fda.gov/scripts/cder/daf/
index.cfm?event=overview.process&ApplNo=218614) carries the sponsor's
name, the marketing status, and links to every approval-package
document for an application. v0.1 of this module just extracts the
sponsor; richer parsing is a v0.2 add.
"""

from __future__ import annotations

import re
import warnings
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

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


# Rows of the "Original Approvals or Tentative Approvals" table:
#   <td>11/17/2022</td> <td>ORIG-1</td> <td> Approval </td>
# "Tentative Approval" rows are deliberately not matched.
_ORIG_APPROVAL_RE = re.compile(
    r"<td>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</td>\s*<td>\s*ORIG-\d+\s*</td>\s*<td>\s*Approval\s*</td>",
    re.I,
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


def parse_original_approval_date(html_bytes: bytes) -> date | None:
    """Return the original-approval action date from a drugs@FDA overview HTML.

    This is the action date of the ORIG approval submission — the date on the
    approval letter. ``None`` when the page has no such row (e.g. the
    application has since been withdrawn and dropped from drugs@FDA).
    """
    if not html_bytes:
        return None
    text = html_bytes.decode("utf-8", errors="replace")
    dates = []
    for m in _ORIG_APPROVAL_RE.finditer(text):
        try:
            dates.append(datetime.strptime(m.group(1), "%m/%d/%Y").date())
        except ValueError:
            continue
    return min(dates) if dates else None


def reconcile_approval_dates(
    df: pd.DataFrame,
    cache_dir: Path | str = "data/raw/fda/overview",
) -> pd.DataFrame:
    """Replace list-page approval dates with the drugs@FDA action date where they differ.

    FDA's annual Novel Drug Approvals page is hand-maintained and occasionally
    off by a day from the approval letter (Tzield is listed as 11/18/22; its
    approval letter and drugs@FDA both say November 17, 2022). drugs@FDA is
    FDA's system of record for the action date, so it wins. The list-page date
    is kept when drugs@FDA has no original-approval row, or when the two
    disagree about the *year* — that is too large a gap to resolve silently,
    so it is reported instead. Uses the overview pages already cached by
    ``enrich_with_sponsor``; makes no extra requests once that has run.
    """
    out = df.copy()
    cache = Path(cache_dir)
    dates = list(out["approval_date"])
    apps = out["application_number"].fillna("").tolist()
    names = out["drug_name"].tolist()
    for i, appl_no in enumerate(apps):
        if not appl_no:
            continue
        try:
            official = parse_original_approval_date(
                fetch_application_overview(appl_no, cache).read_bytes()
            )
        except Exception:  # noqa: BLE001
            continue
        if official is None or official == dates[i]:
            continue
        if official.year != dates[i].year:
            warnings.warn(
                f"{names[i]}: drugs@FDA original approval {official.isoformat()} and the "
                f"Novel Drug Approvals list ({dates[i].isoformat()}) disagree by year; "
                "keeping the list date",
                stacklevel=2,
            )
            continue
        dates[i] = official
    out["approval_date"] = dates
    return out


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
        keep_upper = {
            "INC",
            "LLC",
            "LTD",
            "LP",
            "LLP",
            "PLC",
            "USA",
            "AG",
            "SA",
            "SAS",
            "SPA",
            "BV",
            "GMBH",
            "CO",
            "CORP",
            "AB",
            "AS",
            "OY",
        }
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
