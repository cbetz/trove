"""Unit tests for the CBER cell/gene therapy scraper."""

from __future__ import annotations

from datetime import date

from fda_sba.cber import (
    _split_trade_active,
    parse_cber_product,
)

# Minimal fixture matching the layout of FDA's per-product pages.
_LENMELDY_FIXTURE = b"""
<html><body>
<h1>LENMELDY</h1>
<div>
STN: 125758
Proper Name: atidarsagene autotemcel
Trade Name: LENMELDY
Manufacturer: Orchard Therapeutics (Europe) Limited
Indication: Indicated for the treatment of children with metachromatic leukodystrophy
Approval History, Letters, Reviews, and Related Documents - LENMELDY
</div>
<ul>
  <li><a href="/media/177122/download?attachment">March 18, 2024 Approval Letter - LENMELDY</a></li>
  <li><a href="/media/187811/download?attachment">May 30, 2025 Approval Letter - LENMELDY</a></li>
</ul>
<a href="/media/177109/download?attachment">Package Insert - LENMELDY</a>
</body></html>
"""

_404_FIXTURE = b"<html><body>Page Not Found</body></html>"


def test_split_trade_active_basic() -> None:
    assert _split_trade_active("LENMELDY (atidarsagene autotemcel)") == (
        "Lenmeldy",
        "atidarsagene autotemcel",
    )


def test_split_trade_active_strips_bracketed_alias() -> None:
    assert _split_trade_active("CASGEVY (exagamglogene autotemcel [exa-cel])") == (
        "Casgevy",
        "exagamglogene autotemcel",
    )


def test_split_trade_active_handles_trademark_symbol() -> None:
    assert _split_trade_active("OTARMENI™ (lunsotogene parvec cwha)") == (
        "Otarmeni",
        "lunsotogene parvec cwha",
    )


def test_split_trade_active_rejects_unparenthesized() -> None:
    # Cord-blood entries on the CBER index don't have the trade-name pattern;
    # the parser should reject them rather than misclassify.
    assert _split_trade_active("HPC, Cord Blood - LifeSouth") == (None, None)


def test_parse_cber_product_extracts_all_fields() -> None:
    parsed = parse_cber_product(_LENMELDY_FIXTURE)
    assert parsed["is_404"] is False
    assert parsed["approval_date"] == date(2024, 3, 18)
    assert parsed["stn"] == "125758"
    assert parsed["manufacturer"] == "Orchard Therapeutics (Europe) Limited"
    assert "metachromatic leukodystrophy" in parsed["indication"]
    assert parsed["package_insert_url"].endswith("/media/177109/download?attachment")


def test_parse_cber_product_picks_earliest_approval_letter() -> None:
    # Fixture has two letters: March 2024 (original) and May 2025 (supplement).
    # The original approval is the earlier date.
    parsed = parse_cber_product(_LENMELDY_FIXTURE)
    assert parsed["approval_date"] == date(2024, 3, 18)


def test_parse_cber_product_detects_404() -> None:
    parsed = parse_cber_product(_404_FIXTURE)
    assert parsed["is_404"] is True
    assert parsed["approval_date"] is None
    assert parsed["stn"] is None


# --- original-approval resolution (regressions: Imlygic, Elevidys) ----------

# IMLYGIC layout: the product page keeps only recent supplement letters and
# links to an archived page for "documents older than three years".
_IMLYGIC_FIXTURE = b"""
<html><body>
<div>STN: 125518 Proper Name: talimogene laherparepvec Tradename: IMLYGIC</div>
<ul>
  <li><a href="/media/165431/download">February 10, 2023 Approval Letter - IMLYGIC</a></li>
  <li><a href="/media/154750/download">December 8, 2021 Approval Letter - IMLYGIC</a></li>
  <li><a href="//wayback.archive-it.org/7993/2019/https://www.fda.gov/ucm469411.htm">
    Supporting Documents older than three years - IMLYGIC</a></li>
</ul>
</body></html>
"""

_IMLYGIC_ARCHIVE_FIXTURE = b"""
<html><body><ul>
  <li><a href="/x.pdf">October 27, 2015 Approval Letter - IMLYGIC (PDF - 71KB)</a></li>
  <li><a href="/y.pdf">October 27, 2015 Summary Basis for Regulatory Action - IMLYGIC</a></li>
</ul></body></html>
"""

# ELEVIDYS layout: the original approval letter is not listed; the earliest
# "Approval Letter" is a supplement, but the original SBRA is still there.
_MISSING_ORIGINAL_FIXTURE = b"""
<html><body>
<div>STN: 125999 Proper Name: examplegene Tradename: EXAMPLE</div>
<ul>
  <li><a href="/a">June 20, 2024 Approval Letter - EXAMPLE</a></li>
  <li><a href="/b">January 10, 2024 Approval Letter - EXAMPLE</a></li>
  <li><a href="/c">June 21, 2023 Summary Basis for Regulatory Action - EXAMPLE</a></li>
</ul>
</body></html>
"""


def test_parse_cber_product_reports_older_documents_link() -> None:
    parsed = parse_cber_product(_IMLYGIC_FIXTURE)
    assert parsed["approval_date"] == date(2021, 12, 8)  # earliest letter ON THE PAGE
    assert parsed["older_documents_url"] == (
        "https://wayback.archive-it.org/7993/2019/https://www.fda.gov/ucm469411.htm"
    )
    assert parse_cber_product(_LENMELDY_FIXTURE)["older_documents_url"] is None


def test_original_approval_uses_archived_documents() -> None:
    """Imlygic was approved in 2015, not on the date of its earliest listed supplement."""
    from fda_sba.cber import resolve_original_approval_date

    parsed = parse_cber_product(_IMLYGIC_FIXTURE)
    assert resolve_original_approval_date(parsed, _IMLYGIC_ARCHIVE_FIXTURE) == (
        date(2015, 10, 27),
        None,
    )


def test_original_approval_refuses_to_guess_without_the_archive() -> None:
    from fda_sba.cber import resolve_original_approval_date

    resolved, problem = resolve_original_approval_date(parse_cber_product(_IMLYGIC_FIXTURE))
    assert resolved is None
    assert "archive" in problem


def test_original_approval_flags_missing_original_letter() -> None:
    """A review dated months before every listed letter means the original is missing."""
    from fda_sba.cber import resolve_original_approval_date

    parsed = parse_cber_product(_MISSING_ORIGINAL_FIXTURE)
    assert parsed["earliest_document_date"] == date(2023, 6, 21)
    resolved, problem = resolve_original_approval_date(parsed)
    assert resolved is None
    assert "2023-06-21" in problem


def test_original_approval_tolerates_review_signed_just_before_letter() -> None:
    """An SBRA dated the day before the approval letter is normal, not a defect."""
    from fda_sba.cber import resolve_original_approval_date

    page = _LENMELDY_FIXTURE.replace(
        b"<ul>", b'<ul><li><a href="/s">March 17, 2024 Summary Basis - LENMELDY</a></li>'
    )
    assert resolve_original_approval_date(parse_cber_product(page)) == (date(2024, 3, 18), None)


def test_original_approval_overrides_are_cited_and_applied() -> None:
    from fda_sba.cber import _ORIGINAL_APPROVAL_OVERRIDES, resolve_original_approval_date

    for stn, (when, source) in _ORIGINAL_APPROVAL_OVERRIDES.items():
        assert source.startswith("https://www.fda.gov/"), stn
        assert resolve_original_approval_date({"stn": stn, "approval_date": None}) == (when, None)
    # Elevidys: accelerated approval June 22, 2023 (not the January 2024 supplement).
    assert _ORIGINAL_APPROVAL_OVERRIDES["125781"][0] == date(2023, 6, 22)
