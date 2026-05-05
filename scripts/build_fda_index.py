"""Build the FDA novel drug approvals index.

Scrapes FDA's annual Novel Drug Approvals pages for the last 5 calendar
years, parses each into a tidy DataFrame, and writes:

- ``data/parquet/fda_sba/year=YYYY/part.parquet`` — full per-year data
  (gitignored)
- ``artifacts/fda_approvals_nme_recent.csv`` — committed, GitHub-viewable
- ``web/data/fda_approvals_nme_recent.parquet`` and
  ``web/data/fda_approvals_nme_recent.json`` — published bundles for the
  /drugs page and the fda-analyst skill

Usage: ``uv run python scripts/build_fda_index.py``
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from fda_sba import build_index

YEARS = (2021, 2022, 2023, 2024)
ARTIFACTS_DIR = Path("artifacts")
PARQUET_DIR = Path("data/parquet")
WEB_DATA = Path("web/data")
RAW_CACHE = Path("data/raw/fda")


def main() -> None:
    print(f"Scraping FDA Novel Drug Approvals for {min(YEARS)}–{max(YEARS)}...")
    df = build_index(YEARS, cache_dir=RAW_CACHE)
    print(f"  {len(df):,} drug approvals across {df['year'].nunique()} years")
    print("  by year:")
    for year, count in df.groupby("year").size().sort_index(ascending=False).items():
        print(f"    {year}: {count}")

    # Persist as Parquet partitioned by year (gitignored)
    for year, sub in df.groupby("year"):
        out = PARQUET_DIR / "fda_sba" / f"year={year}" / "part.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(sub, preserve_index=False), out)
    print(f"  → {PARQUET_DIR}/fda_sba/")

    # Committable CSV artifact
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    csv_out = ARTIFACTS_DIR / "fda_approvals_nme_recent.csv"
    df.to_csv(csv_out, index=False)
    print(f"  → {csv_out} ({csv_out.stat().st_size / 1024:.1f} KB)")

    # Web Parquet bundle
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    web_pq = WEB_DATA / "fda_approvals_nme_recent.parquet"
    pq.write_table(
        pa.Table.from_pandas(df, preserve_index=False), web_pq, compression="zstd"
    )
    print(f"  → {web_pq} ({web_pq.stat().st_size / 1024:.1f} KB)")

    # Web JSON bundle for the lookup page
    rows = [_row_to_json(r) for r in df.itertuples(index=False)]
    bundle = {
        "totals": {
            "drugs": int(len(df)),
            "year_min": int(df["year"].min()),
            "year_max": int(df["year"].max()),
            "by_year": {
                int(y): int(c) for y, c in df.groupby("year").size().items()
            },
        },
        "rows": rows,
    }
    web_json = WEB_DATA / "fda_approvals_nme_recent.json"
    web_json.write_text(json.dumps(bundle, separators=(",", ":")) + "\n")
    print(f"  → {web_json} ({web_json.stat().st_size / 1024:.1f} KB)")


def _row_to_json(r) -> dict:
    return {
        "year": int(r.year),
        "drug_name": _str(r.drug_name),
        "active_ingredient": _str(r.active_ingredient),
        "approval_date": r.approval_date.isoformat() if r.approval_date else None,
        "indication": _str(r.indication),
        "application_number": _str(r.application_number),
        "application_type": _str(r.application_type),
        "label_pdf_url": _str(r.label_pdf_url),
        "drugs_at_fda_url": _str(r.drugs_at_fda_url),
        "trials_snapshot_url": _str(r.trials_snapshot_url),
    }


def _str(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    s = str(v).strip()
    return s if s else None


if __name__ == "__main__":
    main()
