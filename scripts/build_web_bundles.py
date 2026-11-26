"""Publish web-accessible Parquet bundles for the hcris-analyst skill.

The skill queries data over HTTPS via DuckDB, so the bundles need to be
served as static files from troveproject.com. Reads from the working
parquet/CSV outputs of build_gap_dataset.py and writes:

- ``web/data/hcris_2022_wide.parquet`` and ``web/data/hcris_2023_wide.parquet`` —
  pivoted HCRIS, one row per cost report, every dictionary variable as a named
  column. One file per CMS fiscal-year file; CMS assigns a report to the federal
  fiscal year in which its period BEGINS, so the FY2023 file is periods beginning
  2022-10-01..2023-09-30 and the FY2022 file the twelve months before. Both files
  have the same schema (``hcris_file_fy`` says which one a row came from), so
  ``read_parquet([...2022..., ...2023...])`` unions them. ``hcris_2023_wide.parquet``
  keeps its name and its original columns; new columns are added, none renamed.
- ``web/data/schedule_h_2022.parquet`` — TY2022 Schedule H filings across IRS
  release years 2023-2026. NOT deduplicated: an EIN appears more than once when
  it amended or filed a short year; take the latest ``tax_period_end`` then the
  latest ``return_ts`` per EIN for the return of record.
- ``web/data/community_benefit_gap_2022.parquet`` — full matched gap
  dataset including non-computable rows
- ``web/data/community_benefit_gap_2022.csv`` — the same table as CSV, copied
  from ``artifacts/`` so the site's "download the data" link and the committed
  artifact can never drift apart

Re-run after ``build_gap_dataset.py`` to refresh.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

WEB_DATA = Path("web/data")
HCRIS_FYS = (2022, 2023)
TAX_YEAR = 2022
HCRIS_WIDE = "data/parquet/hcris/wide/year={fy}/part.parquet"
SCHED_H_PARQUET = Path(f"data/parquet/form990/schedule_h/year={TAX_YEAR}/part.parquet")
GAP_CSV = Path(f"artifacts/community_benefit_gap_{TAX_YEAR}.csv")
# Leading zeros (EIN, CCN) and 18-digit ids must not be parsed as numbers.
GAP_STRING_COLUMNS = ("ein", "ccn_list", "sched_h_object_id", "hcris_rpt_rec_num")
GAP_DATE_COLUMNS = (
    "hcris_fy_bgn_dt",
    "hcris_fy_end_dt",
    "sched_h_tax_period_begin",
    "sched_h_tax_period_end",
)


def main() -> None:
    WEB_DATA.mkdir(parents=True, exist_ok=True)

    for fy in HCRIS_FYS:
        src = Path(HCRIS_WIDE.format(fy=fy))
        if not src.exists():
            raise SystemExit(f"missing {src}; run scripts/build_gap_dataset.py first")
        print(f"Loading pivoted HCRIS FY{fy}...")
        _write(WEB_DATA / f"hcris_{fy}_wide.parquet", pd.read_parquet(src))

    print(f"Loading TY{TAX_YEAR} Schedule H...")
    if not SCHED_H_PARQUET.exists():
        raise SystemExit(f"missing {SCHED_H_PARQUET}; run scripts/build_gap_dataset.py first")
    sched_h = pd.read_parquet(SCHED_H_PARQUET)
    _write(WEB_DATA / f"schedule_h_{TAX_YEAR}.parquet", sched_h)

    print(f"Loading TY{TAX_YEAR} gap dataset...")
    gap = pd.read_csv(
        GAP_CSV,
        dtype={c: str for c in GAP_STRING_COLUMNS},
        parse_dates=list(GAP_DATE_COLUMNS),
    )
    _write(WEB_DATA / f"community_benefit_gap_{TAX_YEAR}.parquet", gap)

    # The site links the CSV directly; copy rather than re-serialize so the
    # published download is byte-identical to the committed artifact.
    csv_out = WEB_DATA / GAP_CSV.name
    csv_out.write_bytes(GAP_CSV.read_bytes())
    print(f"  → {csv_out} ({csv_out.stat().st_size / 1024:.1f} KB, copied from {GAP_CSV})")


def _write(path: Path, df: pd.DataFrame) -> None:
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), path, compression="zstd")
    size_kb = path.stat().st_size / 1024
    print(f"  → {path} ({len(df):,} rows × {len(df.columns)} cols, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
