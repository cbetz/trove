"""Showcase — what is in the gap between HCRIS S-10 and 990 Schedule H charity care.

Joins CMS HCRIS Worksheet S-10 (facility-level, FY2022 + FY2023 files) to IRS 990
Schedule H TY2022 (system-level) via the CBI CCN <-> EIN crosswalk, matching each
cost report to the 990's own fiscal period, and prints the period-aligned
single-facility hospitals with the largest differences next to the components
each form reports (Schedule H 7a gross / offsetting revenue / net; S-10 line 23
and line 5).

Run with ``uv run python scripts/demo_community_benefit_gap.py``. Requires the
caches written by ``uv run python scripts/build_gap_dataset.py``:
- data/parquet/hcris/wide/year={2022,2023}/part.parquet
- data/parquet/form990/schedule_h/year=2022/part.parquet
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from analytics import community_benefit_gap
from crosswalk import load_seed

pd.set_option("display.width", 240)
pd.set_option("display.max_colwidth", 40)

HCRIS_WIDE = [Path(f"data/parquet/hcris/wide/year={fy}/part.parquet") for fy in (2022, 2023)]
SCHED_H = Path("data/parquet/form990/schedule_h/year=2022/part.parquet")


def _usd_m(v: float | None) -> str:
    if pd.isna(v):
        return "—"
    return f"${v / 1e6:>7.1f}M"


def main() -> None:
    missing = [p for p in (*HCRIS_WIDE, SCHED_H) if not p.exists()]
    if missing:
        raise SystemExit(
            "missing " + ", ".join(map(str, missing)) + "; run scripts/build_gap_dataset.py first"
        )
    print("Loading HCRIS FY2022 + FY2023 (one row per cost report)...")
    hcris_wide = pd.concat([pd.read_parquet(p) for p in HCRIS_WIDE], ignore_index=True)
    print(f"  cost reports: {len(hcris_wide):,}")

    print("Loading TY2022 Schedule H...")
    sched_h = pd.read_parquet(SCHED_H)
    print(f"  Schedule H filings: {len(sched_h):,} ({sched_h['ein'].nunique():,} EINs)")

    print("Loading CBI crosswalk...")
    cw = load_seed()
    print(f"  CCN<->EIN rows: {len(cw):,} ({cw['ein'].nunique():,} unique EINs)")

    print("Computing community benefit gap...")
    gap = community_benefit_gap(hcris_wide, sched_h, cw)
    computable = gap["charity_gap"].notna()
    print(f"  Matched hospital systems: {len(gap):,}")
    print(f"  Both figures present: {computable.sum():,}")
    print(f"  ...and period-aligned: {(computable & gap['period_aligned']).sum():,}")
    print()

    print("=== Largest differences, period-aligned single-facility filers ===")
    print("    (7a = Schedule H Part I line 7a; S-10 = Worksheet S-10; blank = not on the form)")
    view = gap[computable & gap["period_aligned"] & (gap["ccn_count"] == 1)].head(15)
    cols = {
        "hospital_name": "hospital",
        "state": "st",
        "sched_h_financial_assistance_gross": "7a (c) gross",
        "sched_h_financial_assistance_offset_revenue": "7a (d) offset",
        "sched_h_financial_assistance_at_cost": "7a (e) net",
        "hcris_charity_care_cost": "S-10 L23",
        "hcris_medicaid_dsh_supplemental": "S-10 L5",
        "charity_gap": "net diff",
        "charity_gap_gross": "gross diff",
    }
    top = view[list(cols)].rename(columns=cols).copy()
    for c in list(cols.values())[2:]:
        top[c] = top[c].apply(_usd_m)
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
