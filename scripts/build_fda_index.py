"""Build the FDA novel drug approvals index (CDER + CBER).

Scrapes two FDA sources for the complete calendar years in ``YEARS`` and writes:

- CDER — annual Novel Drug Approvals pages (NMEs and novel BLAs from
  the Center for Drug Evaluation and Research)
- CBER — Approved Cellular and Gene Therapy Products page (cell and
  gene therapies from the Center for Biologics Evaluation and Research)

Outputs:

- ``data/parquet/fda_sba/year=YYYY/part.parquet`` — full per-year data
  (gitignored)
- ``artifacts/fda_approvals_nme_recent.csv`` — committed, GitHub-viewable
- ``web/data/fda_approvals_nme_recent.parquet`` and
  ``web/data/fda_approvals_nme_recent.json`` — published bundles for the
  /drugs page and the fda-analyst skill
- ``web/data/fda_nme_compilation.{csv,parquet}`` — FDA's Compilation of CDER
  NME and New Biologic Approvals (1985 onward), converted from FDA's XLSX, plus
  ``fda_nme_compilation_source.json`` recording which FDA file it came from

Usage: ``uv run python scripts/build_fda_index.py``
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from fda_sba import build_index, fetch_compilation, parse_compilation, read_source_metadata

YEARS = (2021, 2022, 2023, 2024, 2025)
ARTIFACTS_DIR = Path("artifacts")
PARQUET_DIR = Path("data/parquet")
WEB_DATA = Path("web/data")
RAW_CACHE = Path("data/raw/fda")


def main() -> None:
    print(f"Scraping FDA novel approvals (CDER + CBER) for {min(YEARS)}–{max(YEARS)}...")
    compilation_path = fetch_compilation(RAW_CACHE / "compilation")
    compilation = parse_compilation(compilation_path)
    df = build_index(YEARS, cache_dir=RAW_CACHE, compilation=compilation)
    print(f"  {len(df):,} drug approvals across {df['year'].nunique()} years")
    print("  by year:")
    for year, count in df.groupby("year").size().sort_index(ascending=False).items():
        print(f"    {year}: {count}")
    print("  by regulatory center:")
    for center, count in df.groupby("regulatory_center").size().items():
        print(f"    {center}: {count}")
    _check_dates(df)
    # Rows whose letter or review link came from the cached drugs@FDA pages
    # were read when that cache was; openFDA-filled rows carry their own date.
    page_read = _sources_read()["drugs_at_fda"]
    has_docs = df["approval_letter_url"].notna() | df["review_url"].notna()
    df.loc[has_docs & df["documents_read"].isna(), "documents_read"] = page_read
    sponsor_cov = df["sponsor"].notna().sum()
    print(f"  sponsor coverage: {sponsor_cov:,}/{len(df):,}")
    for col in (
        "label_pdf_url",
        "approval_letter_url",
        "review_url",
        "review_designation",
        "pharm_class_epc",
        "pharm_class_moa",
    ):
        print(f"  {col} coverage: {df[col].notna().sum():,}/{len(df):,}")

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
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), web_pq, compression="zstd")
    print(f"  → {web_pq} ({web_pq.stat().st_size / 1024:.1f} KB)")

    # Web JSON bundle for the lookup page
    rows = [_row_to_json(r) for r in df.itertuples(index=False)]
    bundle = {
        "totals": {
            "drugs": int(len(df)),
            "year_min": int(df["year"].min()),
            "year_max": int(df["year"].max()),
            "by_year": {int(y): int(c) for y, c in df.groupby("year").size().items()},
            "sources_read": _sources_read(),
        },
        "rows": rows,
    }
    web_json = WEB_DATA / "fda_approvals_nme_recent.json"
    web_json.write_text(json.dumps(bundle, separators=(",", ":")) + "\n")
    print(f"  → {web_json} ({web_json.stat().st_size / 1024:.1f} KB)")

    _write_compilation(compilation, read_source_metadata(compilation_path))


def _write_compilation(comp: pd.DataFrame, source: dict) -> None:
    """Publish FDA's NME compilation as CSV and Parquet, with its provenance."""
    year_min, year_max = int(comp["approval_year"].min()), int(comp["approval_year"].max())
    print(f"FDA NME compilation: {len(comp):,} approvals, {year_min}–{year_max}")
    csv_out = WEB_DATA / "fda_nme_compilation.csv"
    comp.to_csv(csv_out, index=False)
    print(f"  → {csv_out} ({csv_out.stat().st_size / 1024:.1f} KB)")
    pq_out = WEB_DATA / "fda_nme_compilation.parquet"
    pq.write_table(pa.Table.from_pandas(comp, preserve_index=False), pq_out, compression="zstd")
    print(f"  → {pq_out} ({pq_out.stat().st_size / 1024:.1f} KB)")
    meta = {
        "source": source,
        "totals": {
            "approvals": int(len(comp)),
            "year_min": year_min,
            "year_max": year_max,
            "by_year": {int(y): int(c) for y, c in comp.groupby("approval_year").size().items()},
        },
        "columns": list(comp.columns),
    }
    meta_out = WEB_DATA / "fda_nme_compilation_source.json"
    meta_out.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"  → {meta_out}")


def _sources_read() -> dict:
    """When the cached FDA pages behind the index were fetched.

    Uses the oldest file in each cache, so the date on a drug page is never
    later than the day its FDA page was actually read.
    """

    def oldest(paths) -> str | None:
        stamps = [p.stat().st_mtime for p in paths]
        return date.fromtimestamp(min(stamps)).isoformat() if stamps else None

    return {
        "cder_lists": oldest(RAW_CACHE.glob("nme_*.html")),
        "drugs_at_fda": oldest((RAW_CACHE / "overview").glob("*.html")),
        "cber": oldest((RAW_CACHE / "cber").glob("*.html")),
        "openfda": oldest((RAW_CACHE / "openfda").glob("*.json")),
    }


def _check_dates(df) -> None:
    """Refuse to publish a row with a missing or out-of-range approval date."""
    bad = [
        f"{r.drug_name}: approval_date={r.approval_date!r} year={r.year}"
        for r in df.itertuples(index=False)
        if pd.isna(r.approval_date) or r.approval_date.year != r.year or r.year not in YEARS
    ]
    if bad:
        raise SystemExit("Refusing to publish rows with bad approval dates:\n  " + "\n  ".join(bad))


def _row_to_json(r) -> dict:
    return {
        "year": int(r.year),
        "drug_name": _str(r.drug_name),
        "active_ingredient": _str(r.active_ingredient),
        "sponsor": _str(getattr(r, "sponsor", None)),
        # NaT is truthy, so a bare truthiness test would publish the string "NaT".
        "approval_date": None if pd.isna(r.approval_date) else r.approval_date.isoformat(),
        "indication": _str(r.indication),
        "application_number": _str(r.application_number),
        "application_type": _str(r.application_type),
        "label_pdf_url": _str(r.label_pdf_url),
        "drugs_at_fda_url": _str(r.drugs_at_fda_url),
        "trials_snapshot_url": _str(r.trials_snapshot_url),
        "regulatory_center": _str(getattr(r, "regulatory_center", None)),
        "approval_letter_url": _str(r.approval_letter_url),
        "review_url": _str(r.review_url),
        "submission_classification": _str(r.submission_classification),
        "fda_receipt_date": _str(r.fda_receipt_date),
        "dosage_form": _str(r.dosage_form),
        "route_of_administration": _str(r.route_of_administration),
        "review_designation": _str(r.review_designation),
        "orphan_drug_designation": _str(r.orphan_drug_designation),
        "accelerated_approval": _str(r.accelerated_approval),
        "breakthrough_therapy_designation": _str(r.breakthrough_therapy_designation),
        "fast_track_designation": _str(r.fast_track_designation),
        "qualified_infectious_disease_product": _str(r.qualified_infectious_disease_product),
        "priority_review_voucher_issued": _str(r.priority_review_voucher_issued),
        "priority_review_voucher_redeemed": _str(r.priority_review_voucher_redeemed),
        "documents_read": _str(getattr(r, "documents_read", None)),
        "pharm_class_epc": _str(r.pharm_class_epc),
        "pharm_class_moa": _str(r.pharm_class_moa),
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
