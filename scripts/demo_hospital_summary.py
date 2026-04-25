"""M2 showcase — raw HCRIS → semantic wide DataFrame on FY2023.

Run with ``uv run python scripts/demo_hospital_summary.py`` after
``download_year(2023)`` has populated data/raw/hcris/HOSP10FY2023.zip.
"""

from __future__ import annotations

import pandas as pd
from hcris import load_dictionary, parse_zip, pivot_wide

pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 50)

FY = 2023
ZIP = f"data/raw/hcris/HOSP10FY{FY}.zip"


def _usd(v: float | None) -> str:
    return f"${v / 1e9:>6.2f}B" if pd.notna(v) else "".rjust(8)


def main() -> None:
    dictionary = load_dictionary()
    files = parse_zip(ZIP)
    wide = pivot_wide(files)

    print(f"Dictionary:  {len(dictionary)} variables")
    print(f"Parsed:      FY{FY}, {len(files.rpt):,} reports, {len(files.nmrc):,} NMRC cells")
    print(f"Pivoted:     {wide.shape[0]:,} rows × {wide.shape[1]} columns\n")

    sample = files.nmrc[
        (files.nmrc.rpt_rec_num == 748727)
        & (files.nmrc.wksht_cd == "S300001")
        & (files.nmrc.line_num == "01400")
        & (files.nmrc.clmn_num == "00200")
    ]
    print("=== BEFORE (raw HCRIS) ===")
    print("  Raw NMRC row for report 748727, Worksheet S-3 Part I line 1400 col 200:")
    print(sample.to_string(index=False))
    print()

    row = wide[wide.rpt_rec_num == 748727].iloc[0]
    print("=== AFTER (pivot_wide, same report) ===")
    print(f"  CCN:                     {row.prvdr_num}")
    print(f"  Name:                    {row.hospital_name}")
    print(f"  Ownership type (code):   {row.ownership_type}")
    print(f"  Total beds:              {row.total_beds:,.0f}")
    print(f"  Inpatient bed days:      {row.inpatient_bed_days_utilized:,.0f}")
    print(f"  Total discharges:        {row.total_discharges:,.0f}")
    print(f"  Net patient revenue:     ${row.net_patient_revenue:>15,.0f}")
    print(f"  Total operating expense: ${row.total_operating_expenses:>15,.0f}")
    print(f"  Uncompensated care cost: ${row.uncompensated_care_cost:>15,.0f}")
    print()

    print("=== Top 10 hospitals by net patient revenue (FY2023) ===")
    top = wide.nlargest(10, "net_patient_revenue")[
        [
            "prvdr_num",
            "hospital_name",
            "ownership_type",
            "total_beds",
            "net_patient_revenue",
            "total_operating_expenses",
            "uncompensated_care_cost",
        ]
    ].copy()
    top["net_patient_revenue"] = top["net_patient_revenue"].apply(_usd)
    top["total_operating_expenses"] = top["total_operating_expenses"].apply(_usd)
    top["uncompensated_care_cost"] = top["uncompensated_care_cost"].apply(_usd)
    top["total_beds"] = top["total_beds"].apply(lambda v: f"{v:>5,.0f}" if pd.notna(v) else "")
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
