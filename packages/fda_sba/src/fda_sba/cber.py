"""Scrape FDA's Approved Cellular and Gene Therapy Products page.

FDA splits novel drug regulation between two centers:

  - CDER (Center for Drug Evaluation and Research) handles small-molecule
    drugs and most monoclonal antibody biologics. Its curated annual list
    is ``Novel Drug Approvals``, parsed by ``fda_sba.scrape``.

  - CBER (Center for Biologics Evaluation and Research) handles cell,
    gene, and tissue-engineered therapies. They appear on a separate
    FDA page — Approved Cellular and Gene Therapy Products — and never
    on the CDER novel-drug list.

This module ingests the CBER list so high-profile gene therapies like
Lenmeldy, Casgevy, Lyfgenia, Beqvez, Hemgenix, Roctavian, etc. show up
in the trove FDA index alongside CDER approvals.

The CBER index page has just two columns (trade name + manufacturer)
and a link to each product's own FDA page. The per-product pages carry
the structured detail we need: approval date(s), STN (the BLA number),
proper name, indication, package insert PDF, etc. Page layouts are
inconsistent across products, so the parser uses fallback regexes and
accepts ``None`` for fields it can't extract.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import pandas as pd
from lxml import html

# Be polite — small delay between fetches when the cache misses.
_FETCH_DELAY_SEC = 0.5

CBER_INDEX_URL = (
    "https://www.fda.gov/vaccines-blood-biologics/cellular-gene-therapy-products/"
    "approved-cellular-and-gene-therapy-products"
)
FDA_BASE = "https://www.fda.gov"
USER_AGENT = "trove/fda_sba (+https://github.com/cbetz/trove)"

# CBER product entry on the index has the form:
#   "TRADE_NAME (active ingredient [optional alias])"
# Allow ™/® trademark symbols on the trade name; some products carry them.
_TRADE_RE = re.compile(r"^(?P<trade>[A-Z][A-Z0-9\- ]+?)[™®]?\s*\((?P<active>[^)]+)\)\s*$")

# STN appears in different forms on per-product pages:
#   "STN: BL 125758"
#   "STN: 125758"
#   "STN 125787 -"
#   embedded in approval-letter anchor text: "Approval Letter - CASGEVY (STN 125785)"
_STN_RE = re.compile(r"STN[:\s]*(?:BL[A]?\s*)?(\d{6})", re.I)

# Approval letter anchor text looks like "March 18, 2024 Approval Letter - LENMELDY"
_APPROVAL_LETTER_DATE_RE = re.compile(r"([A-Z][a-z]+ \d{1,2},?\s+\d{4}).{0,5}Approval Letter", re.I)

# Indication text on per-product pages. Try to capture up to ~400 chars after
# "Indication:" up to the next labelled field.
_INDICATION_RE = re.compile(
    r"Indication[:\s]*(?:Indicated for )?(?P<text>.+?)"
    r"(?=\s*(?:Manufactur(?:er|e)|Proper Name|Trade ?[Nn]ame|"
    r"Approval History|Supporting Documents|Product Information|STN|$))",
    re.S,
)

# Manufacturer / Manufacture on per-product pages.
_MFR_RE = re.compile(
    r"Manufactur(?:er|e)[:\s]*(?P<text>[^\n]+?)"
    r"(?=\s*(?:Indication|Proper Name|Trade ?[Nn]ame|"
    r"Approval History|Supporting Documents|STN|$))",
    re.S,
)


def fetch_cber_index(
    cache_dir: Path | str = "data/raw/fda/cber",
    *,
    force: bool = False,
) -> Path:
    """Fetch the CBER index page; cache locally."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / "index.html"
    if target.exists() and not force:
        return target
    req = Request(CBER_INDEX_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp:
        target.write_bytes(resp.read())
    return target


def parse_cber_index(index_html_path: Path | str) -> list[dict]:
    """Parse the CBER index page into one dict per product.

    Each dict has: trade_name, active_ingredient, manufacturer_index, product_url.
    Trade name and active ingredient come from the first column. Manufacturer
    from the index is treated as a fallback — the per-product page is preferred.
    """
    tree = html.fromstring(Path(index_html_path).read_bytes())
    tables = tree.cssselect("table")
    if not tables:
        return []
    body_rows = tables[0].cssselect("tbody tr") or [
        r for r in tables[0].cssselect("tr") if r.cssselect("td")
    ]
    out: list[dict] = []
    for tr in body_rows:
        cells = tr.cssselect("td")
        if len(cells) < 2:
            continue
        name_cell, mfr_cell = cells[0], cells[1]
        raw_text = " ".join(name_cell.text_content().split()).strip()
        trade, active = _split_trade_active(raw_text)
        if not trade:
            continue
        anchors = name_cell.cssselect("a")
        href = anchors[0].get("href") if anchors else None
        product_url = urljoin(FDA_BASE, href) if href else None
        out.append(
            {
                "trade_name": trade,
                "active_ingredient": active,
                "manufacturer_index": " ".join(mfr_cell.text_content().split()).strip() or None,
                "product_url": product_url,
            }
        )
    return out


def _split_trade_active(text: str) -> tuple[str | None, str | None]:
    """Split 'LENMELDY (atidarsagene autotemcel)' into ('LENMELDY', 'atidarsagene autotemcel').

    Drops the bracketed alias when present, e.g. 'CASGEVY (exa-cel [exagamglogene])'.
    """
    m = _TRADE_RE.match(text)
    if not m:
        return None, None
    trade = m.group("trade").strip().title()
    active = m.group("active").strip()
    # Strip trailing aliases like "[exa-cel]"
    active = re.sub(r"\s*\[.*?\]\s*", "", active).strip()
    return trade, active


def fetch_cber_product(
    product_url: str,
    cache_dir: Path | str = "data/raw/fda/cber",
    *,
    force: bool = False,
) -> Path:
    """Fetch a single CBER per-product page; cache locally by URL slug."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    slug = product_url.rstrip("/").split("/")[-1] or "_root"
    target = cache / f"{slug}.html"
    if target.exists() and not force:
        return target
    time.sleep(_FETCH_DELAY_SEC)
    req = Request(product_url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp:
        target.write_bytes(resp.read())
    return target


def parse_cber_product(product_html: bytes | str) -> dict:
    """Parse a CBER per-product page for the fields we want.

    All fields are best-effort. ``None`` when the parser can't find the field
    on this particular page (FDA layouts are inconsistent).

    Returns dict with keys:
        approval_date (date|None), stn (str|None), indication (str|None),
        manufacturer (str|None), package_insert_url (str|None),
        approval_letter_url (str|None), is_404 (bool).
    """
    if isinstance(product_html, str):
        product_html = product_html.encode("utf-8", errors="replace")
    tree = html.fromstring(product_html)
    body_text = " ".join(tree.text_content().split())

    if "Page Not Found" in body_text:
        return {
            "approval_date": None,
            "stn": None,
            "indication": None,
            "manufacturer": None,
            "package_insert_url": None,
            "approval_letter_url": None,
            "is_404": True,
        }

    approval_date, approval_letter_url = _earliest_approval_letter(tree)
    stn = _first_stn(tree, body_text)
    indication = _match_text(body_text, _INDICATION_RE)
    manufacturer = _match_text(body_text, _MFR_RE)
    package_insert_url = _find_link_starting_with(tree, "Package Insert")

    return {
        "approval_date": approval_date,
        "stn": stn,
        "indication": indication,
        "manufacturer": manufacturer,
        "package_insert_url": package_insert_url,
        "approval_letter_url": approval_letter_url,
        "is_404": False,
    }


def _earliest_approval_letter(tree) -> tuple[object, str | None]:
    """Return (datetime.date, href) for the earliest 'Approval Letter' anchor.

    CBER lists approval letters reverse-chronologically in the approval-history
    section. The last entry — earliest date — is the original approval. We pick
    the minimum parsed date across all anchor texts to be robust to ordering.
    """
    earliest = None
    earliest_href = None
    for a in tree.cssselect("a"):
        t = " ".join(a.text_content().split())
        m = _APPROVAL_LETTER_DATE_RE.search(t)
        if not m:
            continue
        try:
            d = datetime.strptime(m.group(1).replace(",", ""), "%B %d %Y").date()
        except ValueError:
            continue
        if earliest is None or d < earliest:
            earliest = d
            earliest_href = _abs(a.get("href"))
    return earliest, earliest_href


def _first_stn(tree, body_text: str) -> str | None:
    """Look for STN in body text first, then approval-letter anchor texts."""
    m = _STN_RE.search(body_text)
    if m:
        return m.group(1)
    for a in tree.cssselect("a"):
        t = a.text_content()
        m = _STN_RE.search(t)
        if m:
            return m.group(1)
    return None


def _match_text(text: str, rx: re.Pattern) -> str | None:
    m = rx.search(text)
    if not m:
        return None
    val = " ".join(m.group("text").split()).strip().rstrip(":.")
    # Truncate runaway captures; pages without proper section breaks can pull
    # hundreds of words into a single field.
    if len(val) > 600:
        val = val[:600].rsplit(" ", 1)[0] + "…"
    return val or None


def _find_link_starting_with(tree, prefix: str) -> str | None:
    for a in tree.cssselect("a"):
        t = " ".join(a.text_content().split())
        if t.lower().startswith(prefix.lower()):
            return _abs(a.get("href"))
    return None


def _abs(href: str | None) -> str | None:
    if not href:
        return None
    return urljoin(FDA_BASE, href)


def build_cber_index(
    years: Iterable[int] | None = None,
    cache_dir: Path | str = "data/raw/fda/cber",
) -> pd.DataFrame:
    """Fetch + parse CBER, filter to ``years`` (e.g. range(2021, 2025)).

    Returns a DataFrame with the same columns as the CDER index produced by
    ``fda_sba.scrape.build_index``, plus a ``regulatory_center`` column set
    to ``"CBER"``.
    """
    index_path = fetch_cber_index(cache_dir)
    products = parse_cber_index(index_path)
    rows: list[dict] = []
    for p in products:
        if not p["product_url"]:
            continue
        try:
            product_path = fetch_cber_product(p["product_url"], cache_dir)
        except Exception:
            continue
        parsed = parse_cber_product(product_path.read_bytes())
        if parsed["is_404"] or parsed["approval_date"] is None:
            continue
        year = parsed["approval_date"].year
        if years is not None and year not in set(years):
            continue
        rows.append(
            {
                "year": year,
                "drug_name": p["trade_name"],
                "active_ingredient": p["active_ingredient"],
                "approval_date": parsed["approval_date"],
                "indication": parsed["indication"],
                "application_number": parsed["stn"],
                "application_type": "BLA",
                "label_pdf_url": parsed["package_insert_url"],
                # For CBER products the per-product FDA page is the canonical
                # one-stop document hub; more useful than the Drugs@FDA app
                # overview URL for end users.
                "drugs_at_fda_url": p["product_url"],
                "trials_snapshot_url": None,
                "sponsor": parsed["manufacturer"] or p["manufacturer_index"],
                "regulatory_center": "CBER",
            }
        )
    if not rows:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)
    df = pd.DataFrame(rows, columns=_OUTPUT_COLUMNS)
    return df.sort_values(["year", "approval_date"], ascending=[False, False]).reset_index(
        drop=True
    )


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
    "sponsor",
    "regulatory_center",
)
