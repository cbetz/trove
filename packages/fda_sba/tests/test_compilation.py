"""Tests for fda_sba.compilation and the approval-document parser."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd
import pytest
from fda_sba import parse_compilation, parse_original_approval_documents
from fda_sba.compilation import (
    _COLUMNS,
    _application_number,
    _to_iso_date,
    enrich_with_designations,
    is_priority,
    is_yes,
    read_xlsx_rows,
)

_SHEET_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
)


def _col(i: int) -> str:
    out = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        out = chr(65 + rem) + out
    return out


def _write_xlsx(path: Path, rows: list[list[str | None]]) -> Path:
    """A minimal workbook: inline strings, one sheet, blanks left out."""
    body = ""
    for r, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{_col(c)}{r}" t="inlineStr"><is><t>{v}</t></is></c>'
            for c, v in enumerate(row)
            if v is not None
        )
        body += f'<row r="{r}">{cells}</row>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="c" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        z.writestr("xl/worksheets/sheet1.xml", _SHEET_HEAD + body + "</sheetData></worksheet>")
    return path


def _row(**overrides: str | None) -> list[str | None]:
    base = {
        "Proprietary Name": "Lupron",
        "Active Ingredient/Moiety": "leuprolide acetate",
        "Applicant": "TAP Pharmaceuticals",
        "NDA/BLA": "NDA",
        "Application Number(1)": "19010",
        "Dosage Form(1)": "Injectable",
        "Route of Administration(1)": "Injection",
        "FDA Receipt Date": "30678",
        "FDA Approval Date": "31146",
        "Approval Year": "1985",
        "Abbreviated Indication(s)": "palliative treatment of advanced prostatic cancer",
        "Review Designation": "Priority",
        "Orphan Drug Designation": "No",
        "Accelerated Approval": "N/A",
        "Breakthrough Therapy Designation": "N/A",
        "Fast Track Designation": "N/A",
        "Qualified Infectious Disease Product": "N/A",
        "Issued a Priority Review Voucher": "N/A",
        "Redeemed a Priority Review Voucher": "N/A",
    }
    base.update(overrides)
    return [base.get(h) for h in _COLUMNS]


def test_excel_serial_and_text_dates_both_become_iso() -> None:
    assert _to_iso_date("31146") == "1985-04-09"
    assert _to_iso_date("12/23/2025") == "2025-12-23"
    assert _to_iso_date(None) is None


def test_application_numbers_are_padded_to_six_digits() -> None:
    assert _application_number("19010") == "019010"
    assert _application_number(" 761152 ") == "761152"
    with pytest.raises(ValueError):
        _application_number("N19010")


def test_parse_compilation_reads_fda_layout(tmp_path: Path) -> None:
    # FDA's real header has stray spaces ("Proprietary  Name", " Application Number(1)").
    header = [h.replace("Proprietary Name", "Proprietary  Name") for h in _COLUMNS]
    header = [" " + h if h.startswith("Application Number") else h for h in header]
    late = _row(
        **{
            "Proprietary Name": "Nereus",
            "Application Number(1)": "220152",
            "FDA Receipt Date": "12/30/2024",
            "FDA Approval Date": "12/30/2025",
            "Approval Year": "2025",
            "Abbreviated Indication(s)": None,
            "Approved Use(s)": "NEREUS is indicated for X.",
            "Review Designation": "Standard",
        }
    )
    path = _write_xlsx(tmp_path / "c.xlsx", [header, late, _row()])
    assert read_xlsx_rows(path)[0][0] == "Proprietary  Name"
    df = parse_compilation(path)
    assert list(df["proprietary_name"]) == ["Lupron", "Nereus"]  # sorted by approval date
    first, second = df.to_dict("records")
    assert first["application_number"] == "019010"
    assert first["fda_approval_date"] == "1985-04-09"
    assert first["days_receipt_to_approval"] == 468
    assert second["fda_receipt_date"] == "2024-12-30"
    assert second["days_receipt_to_approval"] == 365
    assert second["approval_year"] == 2025
    assert pd.isna(second["abbreviated_indication"])


def test_parse_compilation_refuses_a_changed_layout(tmp_path: Path) -> None:
    header = [*_COLUMNS, "A New Column"]
    path = _write_xlsx(tmp_path / "c.xlsx", [header, [*_row(), "x"]])
    with pytest.raises(ValueError, match="changed the compilation layout"):
        parse_compilation(path)


def test_parse_compilation_refuses_a_date_outside_its_year(tmp_path: Path) -> None:
    path = _write_xlsx(tmp_path / "c.xlsx", [list(_COLUMNS), _row(**{"Approval Year": "1986"})])
    with pytest.raises(ValueError, match="does not fall in approval year"):
        parse_compilation(path)


def test_qualified_values_count_as_yes_and_priority() -> None:
    assert is_yes("Yes (indication [A] only)")
    assert not is_yes("No")
    assert not is_yes("N/A")
    assert not is_yes(None)
    assert is_priority("Priority (used priority review voucher)")
    assert not is_priority("Standard")


def test_designations_join_on_any_listed_application_number(tmp_path: Path) -> None:
    two_forms = _row(
        **{
            "Proprietary Name": "Ojemda",
            "Application Number(1)": "217700",
            "Application Number(2)": "218033",
            "Dosage Form(1)": "Tablet",
            "Dosage Form(2)": "Suspension",
            "Route of Administration(2)": "Oral",
            "Route of Administration(1)": "Oral",
            "Orphan Drug Designation": "Yes",
        }
    )
    comp = parse_compilation(_write_xlsx(tmp_path / "c.xlsx", [list(_COLUMNS), two_forms]))
    index = pd.DataFrame({"application_number": ["218033", "125787", None]})
    out = enrich_with_designations(index, comp).to_dict("records")
    assert out[0]["orphan_drug_designation"] == "Yes"
    assert out[0]["dosage_form"] == "Tablet; Suspension"
    assert out[0]["route_of_administration"] == "Oral"
    # No match (a CBER product) and no number at all: every added column is empty.
    assert pd.isna(out[1]["review_designation"])
    assert pd.isna(out[2]["orphan_drug_designation"])


_OVERVIEW = b"""
<table id="exampleApplOrig"><tbody>
<tr><td>02/05/2021</td><td>ORIG-2</td><td> Approval </td><td>Efficacy</td><td>STANDARD; Orphan</td>
 <td><a href="https://x/second.pdf" target="_blank" title="Links to Letter">Letter (PDF)</a></td><td></td><td></td></tr>
<tr><td>02/05/2021</td><td>ORIG-1</td><td>
 Approval
 </td><td> Type 1 - New Molecular Entity </td><td>PRIORITY; Orphan</td>
 <td><a href="https://x/lbl.pdf" target="_blank" title="Links to Label">Label (PDF)</a><br />
 <a href="https://x/Orig1s000, Orig2s000ltr.pdf" target="_blank" title="Links to Letter">Letter (PDF)</a><br />
 <a href="https://x/TOC.html" target="_blank" title="Links to Review">Review</a></td><td></td><td></td></tr>
<tr><td>01/01/2020</td><td>ORIG-1</td><td>Tentative Approval</td><td></td><td></td>
 <td><a href="https://x/tentative.pdf" title="Links to Letter">Letter</a></td><td></td><td></td></tr>
</tbody></table>
<table id="exampleLabels"><tr><td>x</td><td>ORIG-1</td><td>Approval</td><td></td><td></td>
 <td><a href="https://x/other.pdf" title="Links to Label">Label</a></td></tr></table>
"""


def test_original_approval_documents_come_from_the_first_orig_approval_row() -> None:
    docs = parse_original_approval_documents(_OVERVIEW)
    assert docs == {
        "approval_letter_url": "https://x/Orig1s000, Orig2s000ltr.pdf",
        "review_url": "https://x/TOC.html",
        "label_url": "https://x/lbl.pdf",
        "submission_classification": "Type 1 - New Molecular Entity",
    }


def test_original_approval_documents_are_empty_without_an_approval_row() -> None:
    assert set(parse_original_approval_documents(b"").values()) == {None}
    assert set(parse_original_approval_documents(b"<html>withdrawn</html>").values()) == {None}
