"""Tests for fda_sba.overview."""

from __future__ import annotations

from fda_sba import parse_sponsor


def test_extracts_company_value() -> None:
    html_bytes = b"""<html><body>
    <span class="prodBoldText">Company:</span> <span class="appl-details-top">IONIS PHARMS INC                </span>
    </body></html>"""
    assert parse_sponsor(html_bytes) == "Ionis Pharms INC"


def test_handles_missing_company_field() -> None:
    html_bytes = b"<html><body>nothing here</body></html>"
    assert parse_sponsor(html_bytes) is None


def test_handles_empty_input() -> None:
    assert parse_sponsor(b"") is None


def test_preserves_mixed_case() -> None:
    html_bytes = b"""<span class="prodBoldText">Company:</span> <span class="appl-details-top">Pfizer Inc.</span>"""
    assert parse_sponsor(html_bytes) == "Pfizer Inc."


def test_normalizes_whitespace() -> None:
    html_bytes = b"""<span class="prodBoldText">Company:</span> <span class="appl-details-top">ELI   LILLY   AND   CO              </span>"""
    assert parse_sponsor(html_bytes) == "Eli Lilly And CO"


def test_handles_corporate_suffixes() -> None:
    """Common corporate suffixes stay uppercase."""
    html_bytes = b"""<span class="prodBoldText">Company:</span> <span class="appl-details-top">PHATHOM PHARMACEUTICALS INC</span>"""
    assert parse_sponsor(html_bytes) == "Phathom Pharmaceuticals INC"
