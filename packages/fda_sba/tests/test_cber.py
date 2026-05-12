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
