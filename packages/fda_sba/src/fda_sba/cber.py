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
import warnings
from collections.abc import Iterable
from datetime import date, datetime
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

# Any dated entry in the supporting-documents list, e.g.
# "June 21, 2023 Summary Basis for Regulatory Action - ELEVIDYS".
_DATED_DOC_RE = re.compile(r"^([A-Z][a-z]+ \d{1,2},?\s+\d{4})\s+\S")

# FDA moves a product's older documents off the product page and links to an
# archived copy: "Supporting Documents older than three years - IMLYGIC".
_OLDER_DOCS_RE = re.compile(r"Supporting Documents older than", re.I)

# Original approval dates for products whose FDA page cannot yield the right
# date by parsing: the original approval letter is not listed at all, or its
# link text carries the wrong date. Keyed by STN. Each entry cites the FDA
# document the date was verified against. ``build_cber_index`` refuses to
# publish a product whose page lacks its original letter unless it has an
# entry here, so new cases surface as warnings, not as silently wrong dates.
_ORIGINAL_APPROVAL_OVERRIDES: dict[str, tuple[date, str]] = {
    # ELEVIDYS: the page's earliest "Approval Letter" (January 10, 2024) is a
    # supplement approval. FDA's June 20, 2024 letter states "We approved BLA
    # STN BL 125781/0 on June 22, 2023"; the FDA press release announcing the
    # approval is dated June 22, 2023.
    "125781": (date(2023, 6, 22), "https://www.fda.gov/media/179484/download"),
    # RYONCIL: the page labels the original letter "December 19, 2024 Approval
    # Letter", but the letter itself ("BLA APPROVAL", STN BL 125706/0) is dated
    # December 18, 2024, as is FDA's press release.
    "125706": (date(2024, 12, 18), "https://www.fda.gov/media/184605/download"),
}

# Review documents are routinely signed a day or so before the approval letter
# (SBRA dated the day before approval on about a third of product pages), so a
# small lead is normal. A lead longer than this means the letter those reviews
# belong to is missing from the page. ELEVIDYS's lead is 203 days.
_MAX_REVIEW_LEAD_DAYS = 30

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
    cache_name: str | None = None,
) -> Path:
    """Fetch a single CBER per-product page; cache locally by URL slug.

    ``cache_name`` overrides the cache file stem (used for the archived
    older-documents page, whose own URL slug is an opaque ``ucm`` id).
    """
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{cache_name or _slug(product_url)}.html"
    if target.exists() and not force:
        return target
    time.sleep(_FETCH_DELAY_SEC)
    req = Request(product_url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp:
        target.write_bytes(resp.read())
    return target


def _slug(url: str) -> str:
    return url.rstrip("/").split("/")[-1] or "_root"


def parse_cber_product(product_html: bytes | str) -> dict:
    """Parse a CBER per-product page for the fields we want.

    All fields are best-effort. ``None`` when the parser can't find the field
    on this particular page (FDA layouts are inconsistent).

    Returns dict with keys:
        approval_date (date|None), stn (str|None), indication (str|None),
        manufacturer (str|None), package_insert_url (str|None),
        approval_letter_url (str|None), is_404 (bool),
        earliest_document_date (date|None), older_documents_url (str|None).

    ``approval_date`` is the earliest approval letter *listed on this page*.
    That is the original approval only when the page's history is complete —
    see ``resolve_original_approval_date`` for the two ways it is not.
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
            "earliest_document_date": None,
            "older_documents_url": None,
        }

    approval_date, approval_letter_url = _earliest_approval_letter(tree)
    stn = _first_stn(tree, body_text)
    indication = _indication_from_markup(tree) or _match_text(body_text, _INDICATION_RE)
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
        "earliest_document_date": _earliest_dated_document(tree),
        "older_documents_url": _older_documents_url(tree),
    }


def _parse_long_date(text: str) -> date | None:
    try:
        return datetime.strptime(" ".join(text.replace(",", " ").split()), "%B %d %Y").date()
    except ValueError:
        return None


def _earliest_dated_document(tree) -> date | None:
    """Earliest date on any dated supporting-document link (letters, SBRA, memos)."""
    earliest = None
    for a in tree.cssselect("a"):
        m = _DATED_DOC_RE.match(" ".join(a.text_content().split()))
        if not m:
            continue
        d = _parse_long_date(m.group(1))
        if d is not None and (earliest is None or d < earliest):
            earliest = d
    return earliest


def _older_documents_url(tree) -> str | None:
    """URL of the archived 'Supporting Documents older than three years' page."""
    for a in tree.cssselect("a"):
        if _OLDER_DOCS_RE.search(" ".join(a.text_content().split())):
            href = (a.get("href") or "").strip()
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("http://"):
                href = "https://" + href[len("http://") :]
            return _abs(href)
    return None


def resolve_original_approval_date(
    parsed: dict,
    older_documents_html: bytes | None = None,
) -> tuple[date | None, str | None]:
    """Return ``(original_approval_date, problem)`` for a parsed product page.

    The earliest approval letter listed on a product page is NOT always the
    original approval. Two FDA page behaviours break that assumption:

    1. FDA archives documents older than three years and replaces them with a
       "Supporting Documents older than three years" link. What is left on the
       page are supplement approvals (IMLYGIC: original approval October 27,
       2015; earliest letter still on the page December 8, 2021). When that
       link is present the archived page's letters must be considered too, so
       pass its HTML as ``older_documents_html``.
    2. FDA sometimes never lists the original approval letter (ELEVIDYS). The
       tell is a dated supporting document — typically the Summary Basis for
       Regulatory Action — that predates every listed approval letter by
       more than ``_MAX_REVIEW_LEAD_DAYS``. The real date then has to come
       from ``_ORIGINAL_APPROVAL_OVERRIDES``.

    ``problem`` is a human-readable reason when no trustworthy date can be
    established; the caller must not publish the row in that case.
    """
    stn = parsed.get("stn")
    if stn in _ORIGINAL_APPROVAL_OVERRIDES:
        return _ORIGINAL_APPROVAL_OVERRIDES[stn][0], None

    letter = parsed.get("approval_date")
    earliest_doc = parsed.get("earliest_document_date")

    if parsed.get("older_documents_url"):
        if older_documents_html is None:
            return None, "older documents are archived off-page and the archive was not read"
        older_tree = html.fromstring(older_documents_html)
        older_letter, _ = _earliest_approval_letter(older_tree)
        older_doc = _earliest_dated_document(older_tree)
        if older_letter is None:
            return None, "archived older-documents page lists no approval letter"
        letter = older_letter if letter is None else min(letter, older_letter)
        if older_doc is not None:
            earliest_doc = older_doc if earliest_doc is None else min(earliest_doc, older_doc)

    if letter is None:
        return None, "no approval letter listed"
    if earliest_doc is not None and (letter - earliest_doc).days > _MAX_REVIEW_LEAD_DAYS:
        return None, (
            f"a supporting document dated {earliest_doc.isoformat()} predates the earliest "
            f"listed approval letter ({letter.isoformat()}), so the original approval letter "
            "is not on the page; verify the date against FDA and add it to "
            "_ORIGINAL_APPROVAL_OVERRIDES"
        )
    return letter, None


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
        d = _parse_long_date(m.group(1))
        if d is None:
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


_INDICATION_LABEL_RE = re.compile(r"^\s*Indications?\s*:?\s*$", re.I)
_LABEL_TAGS = ("strong", "b")


def _squash(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _next_element(el):
    nxt = el.getnext()
    while nxt is not None and not isinstance(nxt.tag, str):
        nxt = nxt.getnext()
    return nxt


def _join_items(items: list[str]) -> str:
    """Join list items with "; ", or a space where an item already ends in a
    connective ("..., or" / "..., and")."""
    out = ""
    for item in items:
        if not out:
            out = item
        elif out.rstrip(",").endswith((" or", " and")) or out.endswith(","):
            out += " " + item
        else:
            out += "; " + item
    return out


def _list_items(list_el) -> list[str]:
    """Top-level items of a list; a nested list stays inside its parent's text."""
    items = [_squash(" ".join(li.itertext())).rstrip(" .;") for li in list_el.findall("li")]
    return [i for i in items if i]


def _statement(lead_in: str, list_el) -> str | None:
    parts = [lead_in] if lead_in else []
    if list_el is not None and list_el.tag in ("ul", "ol"):
        items = _list_items(list_el)
        if items:
            parts.append(_join_items(items))
    text = " ".join(parts).strip().lstrip(":").rstrip(":.").strip()
    if len(text) > 600:
        text = text[:600].rsplit(" ", 1)[0] + "…"
    return text or None


def _indication_from_markup(tree) -> str | None:
    """Read the indication from the page's markup rather than its flattened text.

    Product pages come in two layouts. The older one has a bold
    ``Indication:`` (or ``Indications:``) label followed by one or more of:
    text on the same line, text after a line break in the same paragraph, a
    paragraph of its own, and a bulleted list. The newer one is an accordion
    whose "Indication" panel holds the same content. Reading exactly that
    block keeps out the leftover "s:" of "Indications:", the "Product
    Information" heading that used to run on to the end, and "Limitations of
    Use" paragraphs. List items are joined with "; ". Returns ``None`` when
    the page has neither layout, so the caller can fall back to the text
    pattern.
    """
    for label in tree.iter(*_LABEL_TAGS):
        if not _INDICATION_LABEL_RE.match(label.text_content().replace("\xa0", " ")):
            continue
        # Text after the label inside its own paragraph. A line break right
        # after the label is layout; one after some text ends the statement.
        pieces = [label.tail or ""]
        for sib in label.itersiblings():
            if sib.tag in _LABEL_TAGS:
                break
            if sib.tag == "br":
                if _squash("".join(pieces)):
                    break
                pieces.append(sib.tail or "")
                continue
            pieces.append(" ".join(sib.itertext()))
            pieces.append(sib.tail or "")
        lead_in = _squash("".join(pieces))

        block = label.getparent() if label.getparent() is not None else label
        nxt = _next_element(block)
        # A label alone in its paragraph: the statement is the next paragraph.
        if not lead_in and nxt is not None and nxt.tag == "p" and not nxt.xpath(".//strong|.//b"):
            lead_in = _squash(" ".join(nxt.itertext()))
            nxt = _next_element(nxt)
        text = _statement(lead_in, nxt)
        if text:
            return text

    # Accordion layout: <div class="panel-heading"><h2><a>Indication</a></h2></div>
    # followed by the panel that holds the statement.
    for heading in tree.xpath('//div[contains(@class, "panel-heading")]'):
        if not _INDICATION_LABEL_RE.match(heading.text_content().replace("\xa0", " ")):
            continue
        panel = _next_element(heading)
        if panel is None:
            continue
        # Walk the panel in document order: paragraphs up to the first list
        # are the statement's lead-in and that list completes it. A
        # "Limitations of Use" paragraph ends the statement.
        lead: list[str] = []
        first_list = None
        for el in panel.iter("p", "ul", "ol"):
            if any(a.tag == "li" for a in el.iterancestors()):
                continue
            if el.tag in ("ul", "ol"):
                first_list = el
                break
            para = _squash(" ".join(el.itertext()))
            if para.lower().startswith("limitation"):
                break
            if para:
                lead.append(para)
        text = _statement(" ".join(lead), first_list)
        if text:
            return text
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
        if parsed["is_404"]:
            continue
        older_html = None
        if parsed["older_documents_url"]:
            try:
                older_html = fetch_cber_product(
                    parsed["older_documents_url"],
                    cache_dir,
                    cache_name=_slug(p["product_url"]) + "__older-documents",
                ).read_bytes()
            except Exception as exc:  # noqa: BLE001
                warnings.warn(
                    f"CBER {p['trade_name']}: could not read archived documents page "
                    f"{parsed['older_documents_url']} ({exc!r})",
                    stacklevel=2,
                )
        approval_date, problem = resolve_original_approval_date(parsed, older_html)
        if approval_date is None:
            # Products with no dated letters at all are pre-2017 legacy pages;
            # anything else is a row we would otherwise have misdated.
            if parsed["approval_date"] is not None:
                warnings.warn(
                    f"CBER {p['trade_name']} left out of the index: {problem}", stacklevel=2
                )
            continue
        year = approval_date.year
        if years is not None and year not in set(years):
            continue
        rows.append(
            {
                "year": year,
                "drug_name": p["trade_name"],
                "active_ingredient": p["active_ingredient"],
                "approval_date": approval_date,
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
