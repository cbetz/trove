"""Build the full community-benefit-gap dataset for the bootstrap pair (FY2023 HCRIS + TY2022 990).

Produces:
- ``data/parquet/form990/schedule_h/year=2022/part.parquet`` — Schedule H ingest (gitignored)
- ``data/parquet/community_benefit_gap/year=2022/part.parquet`` — gap dataset (gitignored)
- ``artifacts/community_benefit_gap_2022.csv`` — full table, GitHub-viewable
- ``artifacts/community_benefit_gap_2022_top50.csv`` — leaderboard

Usage: ``uv run python scripts/build_gap_dataset.py``
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from analytics import community_benefit_gap
from crosswalk import load_seed
from form990 import parse_tax_year
from form990 import write_parquet as write_990_parquet
from hcris import parse_zip as parse_hcris
from hcris import pivot_wide
from sdoh import county_adi_from_block_group, load_svi_county

ARTIFACTS_DIR = Path("artifacts")
PARQUET_DIR = Path("data/parquet")
TAX_YEAR = 2022
RELEASE_YEARS = (2024, 2025, 2026)
HCRIS_FY = 2023
ADI_BG_CSV = Path("data/raw/adi/US_2023_ADI_Census_Block_Group_v4_0_1.csv")
SVI_COUNTY_CSV = Path("data/raw/svi/SVI_2022_US_county.csv")


def main() -> None:
    print(f"Loading HCRIS FY{HCRIS_FY}...")
    hcris_wide = pivot_wide(parse_hcris(f"data/raw/hcris/HOSP10FY{HCRIS_FY}.zip"))

    print(f"Ingesting TY{TAX_YEAR} Schedule H from releases {RELEASE_YEARS}...")
    sched_h_path = PARQUET_DIR / "form990" / "schedule_h" / f"year={TAX_YEAR}" / "part.parquet"
    if sched_h_path.exists() and "release_year" in pd.read_parquet(sched_h_path, columns=None).columns:
        print(f"  using cached {sched_h_path}")
        sched_h = pd.read_parquet(sched_h_path)
    else:
        parts = []
        for release in RELEASE_YEARS:
            print(f"  release {release}:")
            parts.append(parse_tax_year(tax_year=TAX_YEAR, release_year=release))
        sched_h = pd.concat(parts, ignore_index=True)
        write_990_parquet(sched_h, tax_year=TAX_YEAR, out_dir=PARQUET_DIR / "form990")
    print(f"  {len(sched_h):,} filings, {sched_h['ein'].nunique():,} unique EINs")
    by_release = sched_h.groupby("release_year", dropna=False).size().to_dict()
    print(f"  by release year: {by_release}")

    print("Loading CBI crosswalk...")
    cw = load_seed()
    if SVI_COUNTY_CSV.exists():
        print("  enriching crosswalk with CDC SVI 2022 (public)...")
        svi = load_svi_county(SVI_COUNTY_CSV)[
            [
                "county_fips",
                "svi_overall_pct",
                "svi_socio_pct",
                "svi_household_pct",
                "svi_minority_pct",
                "svi_housing_pct",
            ]
        ]
        cw = cw.merge(svi, on="county_fips", how="left")
        print(f"  SVI coverage: {cw['svi_overall_pct'].notna().sum():,} of {len(cw):,}")
    else:
        print(f"  SVI source not found at {SVI_COUNTY_CSV}; skipping SVI enrichment")
    if ADI_BG_CSV.exists():
        print("  enriching crosswalk with UW ADI (local only — non-sublicensable)...")
        county_adi = county_adi_from_block_group(ADI_BG_CSV)
        cw = cw.merge(county_adi, on="county_fips", how="left")
        print(f"  ADI coverage: {cw['adi_natrank'].notna().sum():,} of {len(cw):,}")
    else:
        print(f"  ADI source not found at {ADI_BG_CSV}; skipping ADI enrichment")

    print("Computing gap...")
    gap = community_benefit_gap(hcris_wide, sched_h, cw)
    abs_gap = gap["charity_gap"].abs().sum() / 1e9
    sum_7k = gap["sched_h_total_community_benefit"].sum() / 1e9
    pos = gap["charity_gap"] > 0
    neg = gap["charity_gap"] < 0
    print(f"  Matched hospital systems: {len(gap):,}")
    print(f"  Total absolute charity gap: ${abs_gap:.2f}B")
    print(f"  Total reported community benefit (990 7k sum): ${sum_7k:.2f}B")
    print(f"  Systems with HCRIS > 990: {pos.sum()} ({pos.mean() * 100:.0f}%)")
    print(f"  Systems with 990 > HCRIS: {neg.sum()} ({neg.mean() * 100:.0f}%)")

    # Persist as Parquet (gitignored, full fidelity — includes ADI when present.
    # Local users with their own UW Neighborhood Atlas license can use this).
    parquet_out = PARQUET_DIR / "community_benefit_gap" / f"year={TAX_YEAR}" / "part.parquet"
    parquet_out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(gap, preserve_index=False), parquet_out)
    print(f"  → {parquet_out}")

    # Persist as CSV artifact (committable, GitHub-viewable).
    # Strip ADI columns before publication: UW's Neighborhood Atlas terms
    # are non-sublicensable, so derived ADI numbers must not appear in
    # publicly redistributable bundles. Run locally to get them in the
    # gitignored Parquet above.
    # Sort alphabetically by system name (not by gap) so the published
    # CSV doesn't read as a curated "biggest gaps" leaderboard.
    public = gap.drop(columns=[c for c in ("adi_natrank", "adi_state_decile") if c in gap.columns])
    public = public.sort_values("sched_h_organization_name", na_position="last")
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    full_csv = ARTIFACTS_DIR / f"community_benefit_gap_{TAX_YEAR}.csv"
    public.to_csv(full_csv, index=False, float_format="%.0f")
    print(f"  → {full_csv} ({full_csv.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
