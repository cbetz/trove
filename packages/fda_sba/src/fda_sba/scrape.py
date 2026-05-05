"""Scrape FDA's annual Novel Drug Approvals pages.

Each year's page (e.g. https://www.fda.gov/drugs/novel-drug-approvals-fda/
novel-drug-approvals-2024) is a single HTML table where each row is one
approval: drug name, active ingredient, approval date, FDA-approved use.
The drug-name cell links to the FDA-approved label PDF, from which we
parse the application number.

We use FDA's curated "novel drug approvals" list (rather than every
approval in the openFDA API) because that list is what public discourse
cares about — first-time approvals of meaningful new drugs.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
from lxml import html

NME_PAGE_URL_TEMPLATE = (
    "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-{year}"
)
USER_AGENT = "trove/fda_sba (+https://github.com/cbetz/trove)"

# FDA links from the annual novel-drug-approvals page take two shapes:
#   1. A direct label PDF URL: /drugsatfda_docs/label/2024/{appl_no}...lbl.pdf
#      Variants: bare, Orig1s000, Orig1s000corrected, Corrected_, multi-app
#      (comma-separated). We capture the first 6-digit run after the year.
#   2. The drugs@FDA application overview URL with the app number as a query
#      param: ?ApplNo=215866 or ?varApplNo=761180
_APPL_NO_LABEL_RE = re.compile(r"/drugsatfda_docs/(?:label|nda|bla)/\d{4}/(\d{6})", re.I)
_APPL_NO_QUERY_RE = re.compile(r"[Vv]ar[Aa]pplNo=(\d+)|[Aa]pplNo=(\d+)")


def fetch_nme_year_html(
    year: int,
    cache_dir: Path | str = "data/raw/fda",
    *,
    force: bool = False,
) -> Path:
    """Download FDA's Novel Drug Approvals page for ``year`` and cache it."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"nme_{year}.html"
    if target.exists() and not force:
        return target
    url = NME_PAGE_URL_TEMPLATE.format(year=year)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp:
        target.write_bytes(resp.read())
    return target


def scrape_nme_year(
    year: int,
    cache_dir: Path | str = "data/raw/fda",
) -> pd.DataFrame:
    """Return a DataFrame of FDA novel drug approvals listed for ``year``."""
    page_path = fetch_nme_year_html(year, cache_dir)
    rows = list(_iter_rows(page_path, year))
    if not rows:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)
    df = pd.DataFrame(rows, columns=_OUTPUT_COLUMNS)
    df["approval_date"] = pd.to_datetime(df["approval_date"], errors="coerce").dt.date
    return df


def build_index(
    years: Iterable[int],
    cache_dir: Path | str = "data/raw/fda",
) -> pd.DataFrame:
    """Build the full FDA NME index across ``years``."""
    parts = [scrape_nme_year(y, cache_dir) for y in years]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)
    df = pd.concat(parts, ignore_index=True)
    return df.sort_values(["year", "approval_date"], ascending=[False, False]).reset_index(drop=True)


_OUTPUT_COLUMNS = (
    "year",
    "drug_name",
    "active_ingredient",
    "approval_date",
    "indication",
    "application_number",
    "application_type",
    "label_pdf_url",
    "drugs_at_fda_url",
    "trials_snapshot_url",
)


def _iter_rows(page_path: Path, year: int):
    tree = html.fromstring(page_path.read_bytes())
    tables = tree.cssselect("table")
    if not tables:
        return
    table = tables[0]
    body_rows = table.cssselect("tbody tr") or [
        r for r in table.cssselect("tr") if r.cssselect("td")
    ]
    for tr in body_rows:
        cells = tr.cssselect("td")
        if len(cells) < 4:
            continue
        # FDA's table is [no., drug name (with label-PDF link), active ingredient,
        # approval date, FDA-approved use (with optional Drug Trials Snapshot link)]
        drug_name = _clean(cells[1].text_content())
        if not drug_name:
            continue
        anchor = cells[1].cssselect("a")
        link_url = anchor[0].get("href") if anchor else None
        appl_no = _appl_no_from_label_url(link_url)
        # Only set label_pdf_url when the link is actually a label PDF;
        # otherwise FDA points at the drugs@FDA overview directly.
        label_url = link_url if _is_label_pdf_url(link_url) else None
        active = _clean(cells[2].text_content())
        approval_date = _clean(cells[3].text_content())
        use_cell = cells[4] if len(cells) > 4 else None
        indication = _strip_to_indication(use_cell)
        snapshot_url = _trials_snapshot_url(use_cell) if use_cell is not None else None
        yield {
            "year": year,
            "drug_name": drug_name,
            "active_ingredient": active,
            "approval_date": approval_date,
            "indication": indication,
            "application_number": appl_no,
            "application_type": _appl_type(appl_no),
            "label_pdf_url": label_url,
            "drugs_at_fda_url": _drugs_at_fda_url(appl_no),
            "trials_snapshot_url": snapshot_url,
        }


def _clean(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def _appl_no_from_label_url(url: str | None) -> str | None:
    """Extract the application number from either a label PDF URL or a
    drugs@FDA application-overview URL."""
    if not url:
        return None
    m = _APPL_NO_LABEL_RE.search(url)
    if m:
        return m.group(1)
    m = _APPL_NO_QUERY_RE.search(url)
    if m:
        return m.group(1) or m.group(2)
    return None


def _is_label_pdf_url(url: str | None) -> bool:
    return bool(url) and "/drugsatfda_docs/" in url and url.lower().endswith(".pdf")


def _appl_type(appl_no: str | None) -> str | None:
    if not appl_no:
        return None
    # FDA convention: 6-digit BLA app numbers are 7XXXXX; NDAs are typically 0XXXXX
    # or 2XXXXX. This is a best-effort inference.
    return "BLA" if appl_no.startswith(("7", "1")) else "NDA"


def _drugs_at_fda_url(appl_no: str | None) -> str | None:
    if not appl_no:
        return None
    return (
        f"https://www.accessdata.fda.gov/scripts/cder/daf/"
        f"index.cfm?event=overview.process&ApplNo={appl_no}"
    )


def _strip_to_indication(cell) -> str:
    """Pull the text indication out of a use cell, dropping trailing links.

    The cell typically looks like: indication text, optional <br>, then one or
    more <a> tags (Drug Trials Snapshot, Press Release, etc.). We drop the
    anchors entirely before extracting text — much more robust than regex-
    matching the various link labels FDA uses ("Drug Trial Snapshot",
    "Drug Trials Snapshots: VYLOY", "Press Release", "Approval History", ...).
    """
    if cell is None:
        return ""
    # Operate on a copy so we don't mutate the parsed tree.
    from copy import deepcopy

    cell = deepcopy(cell)
    for a in cell.cssselect("a"):
        # Remove the anchor and any tail text it leaves behind.
        a.getparent().remove(a)
    return _clean(cell.text_content())


def _trials_snapshot_url(cell) -> str | None:
    """Extract the Drug Trials Snapshot URL from a use cell, when present."""
    for a in cell.cssselect("a"):
        if "snapshot" in (a.text_content() or "").lower():
            href = a.get("href")
            if href and href.startswith("/"):
                href = "https://www.fda.gov" + href
            return href
    return None
