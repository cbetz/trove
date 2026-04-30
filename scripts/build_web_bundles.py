"""Publish web-accessible Parquet bundles for the hcris-analyst skill.

The skill queries data over HTTPS via DuckDB, so the bundles need to be
served as static files from troveproject.com. Reads from the working
parquet/CSV outputs of build_gap_dataset.py and writes:

- ``web/data/hcris_2023_wide.parquet`` — pivoted HCRIS FY2023, one row
  per hospital, every dictionary variable as a named column
- ``web/data/schedule_h_2022.parquet`` — TY2022 Schedule H filings,
  concat across IRS release years 2024/2025/2026, latest amendment per
  EIN preferred (downstream consumers should still ``GROUP BY ein`` if
  they want to dedupe further)
- ``web/data/community_benefit_gap_2022.parquet`` — full matched gap
  dataset including non-computable rows

Re-run after ``build_gap_dataset.py`` to refresh.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from hcris import parse_zip as parse_hcris
from hcris import pivot_wide

WEB_DATA = Path("web/data")
HCRIS_FY = 2023
TAX_YEAR = 2022
SCHED_H_PARQUET = Path(f"data/parquet/form990/schedule_h/year={TAX_YEAR}/part.parquet")
GAP_CSV = Path(f"artifacts/community_benefit_gap_{TAX_YEAR}.csv")


def main() -> None:
    WEB_DATA.mkdir(parents=True, exist_ok=True)

    print(f"Loading HCRIS FY{HCRIS_FY} and pivoting wide...")
    hcris_wide = pivot_wide(parse_hcris(f"data/raw/hcris/HOSP10FY{HCRIS_FY}.zip"))
    _write(WEB_DATA / f"hcris_{HCRIS_FY}_wide.parquet", hcris_wide)

    print(f"Loading TY{TAX_YEAR} Schedule H...")
    if not SCHED_H_PARQUET.exists():
        raise SystemExit(
            f"missing {SCHED_H_PARQUET}; run scripts/build_gap_dataset.py first"
        )
    sched_h = pd.read_parquet(SCHED_H_PARQUET)
    _write(WEB_DATA / f"schedule_h_{TAX_YEAR}.parquet", sched_h)

    print(f"Loading TY{TAX_YEAR} gap dataset...")
    gap = pd.read_csv(
        GAP_CSV,
        dtype={"ein": str},
        parse_dates=["hcris_fy_end_dt", "sched_h_tax_period_end"],
    )
    _write(WEB_DATA / f"community_benefit_gap_{TAX_YEAR}.parquet", gap)


def _write(path: Path, df: pd.DataFrame) -> None:
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path, compression="zstd")
    size_kb = path.stat().st_size / 1024
    print(f"  → {path} ({len(df):,} rows × {len(df.columns)} cols, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
