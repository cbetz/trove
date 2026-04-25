"""M2.5 showcase — raw HCRIS → rich hospital profile on FY2023.

Run with ``uv run python scripts/demo_hospital_summary.py`` after
``download_year(2023)`` has populated data/raw/hcris/HOSP10FY2023.zip.
"""

from __future__ import annotations

import pandas as pd
from hcris import load_dictionary, parse_zip, pivot_wide

pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 50)

FY = 2023
ZIP = f"data/raw/hcris/HOSP10FY{FY}.zip"


def _usd(v: float | None) -> str:
    if pd.isna(v):
        return "".rjust(8)
    if abs(v) >= 1e9:
        return f"${v / 1e9:>6.2f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:>6.1f}M"
    return f"${v:>10,.0f}"


def main() -> None:
    dictionary = load_dictionary()
    files = parse_zip(ZIP)
    wide = pivot_wide(files)

    print(f"Dictionary:  {len(dictionary)} variables")
    print(f"Parsed:      FY{FY}, {len(files.rpt):,} reports, {len(files.nmrc):,} NMRC cells")
    print(f"Pivoted:     {wide.shape[0]:,} rows × {wide.shape[1]} columns\n")

    # Pick a large AMC with full S-10 reporting for the rich profile.
    target = wide.nlargest(1, "net_patient_revenue").iloc[0]
    print(f"=== Profile: {target.hospital_name} (CCN {target.prvdr_num}) ===")
    print(
        f"  FY:                              {target.fy_bgn_dt.date()} – {target.fy_end_dt.date()}"
    )
    print(f"  Ownership type (CMS code):       {target.ownership_type}")
    chain = target.chain_name if not pd.isna(target.chain_name) else "(none)"
    print(f"  Chain:                           {chain}")
    print()
    print("  -- Capacity --")
    print(f"  Total beds:                      {target.total_beds:>10,.0f}")
    print(
        f"  ICU beds:                        {target.icu_beds:>10,.0f}"
        if pd.notna(target.icu_beds)
        else "  ICU beds:                         n/a"
    )
    print(
        f"  CCU beds:                        {target.ccu_beds:>10,.0f}"
        if pd.notna(target.ccu_beds)
        else "  CCU beds:                         n/a"
    )
    print(f"  Total discharges:                {target.total_discharges:>10,.0f}")
    print(f"  Inpatient bed-days utilized:     {target.inpatient_bed_days_utilized:>10,.0f}")
    print()
    print("  -- Revenue breakdown --")
    print(f"  Inpatient total revenue:          {_usd(target.inpatient_total_revenue)}")
    print(f"  Outpatient total revenue:         {_usd(target.outpatient_total_revenue)}")
    print(f"  Total patient revenue:            {_usd(target.total_patient_revenue)}")
    print(f"  Net patient revenue:              {_usd(target.net_patient_revenue)}")
    print()
    print("  -- Expense --")
    print(f"  Total operating expenses:         {_usd(target.total_operating_expenses)}")
    print()
    print("  -- Uncompensated care (S-10) --")
    print(f"  Charity care initial charges:     {_usd(target.charity_care_initial_charges)}")
    print(f"  Charity care cost:                {_usd(target.charity_care_cost)}")
    print(f"  Medicare bad debt (reimbursable): {_usd(target.medicare_bad_debt_reimbursable)}")
    print(f"  Non-Medicare bad debt (cost):     {_usd(target.non_medicare_bad_debt_cost)}")
    print(f"  Total uncompensated care cost:    {_usd(target.uncompensated_care_cost)}")
    print()
    print(
        f"  Cost-to-charge ratio:             {target.cost_to_charge_ratio:.4f}"
        if pd.notna(target.cost_to_charge_ratio)
        else "  Cost-to-charge ratio:              n/a"
    )
    print()

    print("=== Top 10 hospitals by uncompensated care cost (FY2023) ===")
    top = wide.nlargest(10, "uncompensated_care_cost")[
        [
            "prvdr_num",
            "hospital_name",
            "total_beds",
            "icu_beds",
            "net_patient_revenue",
            "uncompensated_care_cost",
            "charity_care_cost",
        ]
    ].copy()
    for col in ("net_patient_revenue", "uncompensated_care_cost", "charity_care_cost"):
        top[col] = top[col].apply(_usd)
    top["total_beds"] = top["total_beds"].apply(lambda v: f"{v:>5,.0f}" if pd.notna(v) else "")
    top["icu_beds"] = top["icu_beds"].apply(lambda v: f"{v:>5,.0f}" if pd.notna(v) else "")
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
