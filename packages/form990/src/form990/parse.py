"""Parse 990 e-file XMLs from IRS bulk ZIPs into a tidy Schedule H DataFrame."""

from __future__ import annotations

import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd
from lxml import etree

from form990.schedule_h import OUTPUT_COLUMNS, PART_I_LINE_GROUPS

_NS_URI = "http://www.irs.gov/efile"
_NSMAP = {"e": _NS_URI}

# Cheap byte-level filter so we skip parsing returns that don't have Schedule H.
_SCH_H_MARKER = b"IRS990ScheduleH"


def parse_zip(zip_path: Path | str) -> pd.DataFrame:
    """Parse one bulk-XML ZIP and return a DataFrame of Schedule H filers."""
    rows = list(iter_schedule_h_filings(Path(zip_path)))
    if not rows:
        return pd.DataFrame(columns=list(OUTPUT_COLUMNS))
    df = pd.DataFrame(rows, columns=list(OUTPUT_COLUMNS))
    return _coerce_dtypes(df)


def iter_schedule_h_filings(zip_path: Path) -> Iterator[dict[str, Any]]:
    """Yield one row dict per filing that contains a Schedule H."""
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.endswith(".xml"):
                continue
            with zf.open(info) as f:
                blob = f.read()
            if _SCH_H_MARKER not in blob:
                continue
            row = _extract(blob)
            if row is not None:
                yield row


def _extract(xml_blob: bytes) -> dict[str, Any] | None:
    try:
        root = etree.fromstring(xml_blob)
    except etree.XMLSyntaxError:
        return None
    ns = _NSMAP

    header = root.find("e:ReturnHeader", ns)
    sch_h = root.find(".//e:IRS990ScheduleH", ns)
    if header is None or sch_h is None:
        return None
    main_990 = root.find(".//e:IRS990", ns)

    row: dict[str, Any] = dict.fromkeys(OUTPUT_COLUMNS)
    row["return_version"] = root.get("returnVersion")
    row["ein"] = _text(header, "e:Filer/e:EIN")
    row["organization_name"] = _text(header, "e:Filer/e:BusinessName/e:BusinessNameLine1Txt")
    row["tax_period_begin"] = _text(header, "e:TaxPeriodBeginDt")
    row["tax_period_end"] = _text(header, "e:TaxPeriodEndDt")
    row["tax_year"] = _text(header, "e:TaxYr")

    if main_990 is not None:
        row["total_revenue"] = _text(main_990, "e:CYTotalRevenueAmt")
        row["total_expenses"] = _text(main_990, "e:CYTotalExpensesAmt")

    for element_name, var_name in PART_I_LINE_GROUPS.items():
        group = sch_h.find(f".//e:{element_name}", ns)
        if group is None:
            continue
        row[var_name] = _text(group, "e:NetCommunityBenefitExpnsAmt")
        if var_name == "total_community_benefit":
            row["total_community_benefit_pct"] = _text(group, "e:TotalExpensePct")

    row["bad_debt_expense"] = _text(sch_h, ".//e:BadDebtExpenseAmt")
    row["hospital_facility_count"] = _text(sch_h, ".//e:HospitalFacilitiesCnt")

    return row


def _text(element: etree._Element, xpath: str) -> str | None:
    found = element.find(xpath, _NSMAP)
    if found is None or found.text is None:
        return None
    return found.text.strip() or None


def _coerce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    string_cols = ("ein", "organization_name", "return_version")
    int_cols = ("tax_year", "hospital_facility_count")
    money_cols = (
        "total_revenue",
        "total_expenses",
        "bad_debt_expense",
        *PART_I_LINE_GROUPS.values(),
    )
    ratio_cols = ("total_community_benefit_pct",)
    date_cols = ("tax_period_begin", "tax_period_end")

    for c in string_cols:
        df[c] = df[c].astype("string")
    for c in int_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in money_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ratio_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df
