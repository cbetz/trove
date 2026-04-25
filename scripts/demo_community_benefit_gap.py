"""M4 showcase — community benefit gap between HCRIS S-10 and 990 Schedule H.

Joins HCRIS FY2023 facility-level Worksheet S-10 to IRS 990 Schedule H
TY2022 (system-level) via the CBI CCN <-> EIN crosswalk and surfaces the
hospitals where the two reports tell different stories.

Run with ``uv run python scripts/demo_community_benefit_gap.py``. Requires:
- data/raw/hcris/HOSP10FY2023.zip  (download_year(2023))
- data/raw/form990/2024_TEOS_XML_01A.zip  (download_zip(2024, "2024_TEOS_XML_01A"))
"""

from __future__ import annotations

import pandas as pd
from analytics import community_benefit_gap
from crosswalk import load_seed
from form990 import parse_zip as parse_990
from hcris import parse_zip as parse_hcris
from hcris import pivot_wide

pd.set_option("display.width", 220)
pd.set_option("display.max_colwidth", 50)


def _usd_m(v: float | None) -> str:
    if pd.isna(v):
        return "—"
    return f"${v / 1e6:>7.1f}M"


def _pct(v: float | None) -> str:
    if pd.isna(v):
        return "—"
    return f"{v * 100:>5.1f}%"


def main() -> None:
    print("Loading HCRIS FY2023...")
    hcris_files = parse_hcris("data/raw/hcris/HOSP10FY2023.zip")
    hcris_wide = pivot_wide(hcris_files)

    print("Loading 990 Schedule H from 2024_TEOS_XML_01A...")
    sched_h = parse_990("data/raw/form990/2024_TEOS_XML_01A.zip")
    print(f"  Schedule H filings: {len(sched_h):,}")

    print("Loading CBI crosswalk...")
    cw = load_seed()
    print(f"  CCN<->EIN rows: {len(cw):,} ({cw['ein'].nunique():,} unique EINs)")

    print("Computing community benefit gap...")
    gap = community_benefit_gap(hcris_wide, sched_h, cw)
    print(f"  Joined hospital systems: {len(gap):,}")
    print()

    print("=== Top systems by absolute charity-care gap (HCRIS S-10 vs. 990 Sched H 7a) ===")
    cols = [
        "ein",
        "hospital_name",
        "ccn_count",
        "hcris_charity_care_cost",
        "sched_h_financial_assistance_at_cost",
        "charity_gap",
        "hcris_uncompensated_care_cost",
        "sched_h_total_community_benefit",
        "community_benefit_pct_of_expenses",
    ]
    top = gap[cols].head(10).copy()
    for c in (
        "hcris_charity_care_cost",
        "sched_h_financial_assistance_at_cost",
        "charity_gap",
        "hcris_uncompensated_care_cost",
        "sched_h_total_community_benefit",
    ):
        top[c] = top[c].apply(_usd_m)
    top["community_benefit_pct_of_expenses"] = top["community_benefit_pct_of_expenses"].apply(_pct)
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
