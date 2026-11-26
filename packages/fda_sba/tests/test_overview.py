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


# --- original approval date from the drugs@FDA overview ---------------------

_OVERVIEW_APPROVALS = b"""<table><tbody>
<tr>
	<td>11/17/2022</td>
    <td>ORIG-1</td>
    <td>
    Approval
	</td>
    <td></td>
</tr>
<tr><td>03/01/2021</td><td>ORIG-1</td><td>Tentative Approval</td></tr>
<tr><td>12/13/2023</td><td>SUPPL-4</td><td>Approval</td></tr>
</tbody></table>"""


def test_parse_original_approval_date_ignores_supplements_and_tentative() -> None:
    from datetime import date

    from fda_sba import parse_original_approval_date

    assert parse_original_approval_date(_OVERVIEW_APPROVALS) == date(2022, 11, 17)
    assert parse_original_approval_date(b"<html>no table</html>") is None
    assert parse_original_approval_date(b"") is None


def test_reconcile_prefers_drugs_at_fda_action_date(tmp_path) -> None:
    """Tzield: the annual list says 11/18/22, the approval letter says November 17."""
    from datetime import date

    import pandas as pd
    from fda_sba import reconcile_approval_dates

    (tmp_path / "761183.html").write_bytes(_OVERVIEW_APPROVALS)
    (tmp_path / "214383.html").write_bytes(b"<html>withdrawn, no approvals table</html>")
    (tmp_path / "999999.html").write_bytes(_OVERVIEW_APPROVALS)
    df = pd.DataFrame(
        {
            "drug_name": ["Tzield", "Pepaxto", "YearOff"],
            "application_number": ["761183", "214383", "999999"],
            "approval_date": [date(2022, 11, 18), date(2021, 2, 26), date(2023, 1, 3)],
        }
    )
    import pytest

    with pytest.warns(UserWarning, match="YearOff"):
        out = reconcile_approval_dates(df, cache_dir=tmp_path)
    assert list(out["approval_date"]) == [
        date(2022, 11, 17),  # corrected to the drugs@FDA action date
        date(2021, 2, 26),  # no drugs@FDA row: list date kept
        date(2023, 1, 3),  # different year: kept, with a warning
    ]
