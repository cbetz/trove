"""Build the full community-benefit-gap dataset: HCRIS Worksheet S-10 × IRS 990 Schedule H, TY2022.

What it does, in order:

1. **HCRIS.** Loads the CMS Hospital 2552-10 files for every fiscal year in
   ``HCRIS_FYS``. CMS files a cost report under the federal fiscal year in which
   its period BEGINS (the FY2023 file holds periods beginning 2022-10-01 through
   2023-09-30), so tax-year-2022 990s pair with reports in the FY2022 file
   (January-September starts) or the FY2023 file (October-December starts). The
   FY2024 file was checked and adds no period-matched report, so it is not loaded.
2. **Schedule H.** Parses every bulk XML ZIP of the IRS e-file releases in
   ``RELEASE_YEARS`` for tax-year-2022 returns with a Schedule H — one ZIP at a
   time, deleting each after parsing, keeping the matching raw XML.
3. **Gap.** ``analytics.community_benefit_gap`` picks, per CCN, the cost report
   whose period end is closest to the 990's, sums across the EIN's CCNs, and
   flags ``period_aligned``.

Produces:
- ``data/parquet/hcris/{rpt,nmrc,alpha}/year=<FY>/part.parquet`` — parsed HCRIS (gitignored)
- ``data/parquet/hcris/wide/year=<FY>/part.parquet`` — one row per cost report (gitignored)
- ``data/parquet/form990/schedule_h/year=2022/part.parquet`` — Schedule H ingest (gitignored)
- ``data/raw/form990/xml_ty2022/`` — raw XML of every TY2022 Schedule H return (gitignored)
- ``data/parquet/community_benefit_gap/year=2022/part.parquet`` — gap dataset (gitignored)
- ``artifacts/community_benefit_gap_2022.csv`` — full table, GitHub-viewable
- ``artifacts/community_benefit_gap_2022_sources.json`` — what the source files say
  about their own vintage (CMS extract date, date posted, latest processing date,
  ZIP hashes, IRS release counts), read by ``build_gap_index.py`` so no date is
  hand-typed

The ranked subset is built separately by ``scripts/build_gap_index.py``; this script
deliberately sorts its output alphabetically (see the note by the CSV write).

Usage::

    uv run python scripts/build_gap_dataset.py                  # use caches
    uv run python scripts/build_gap_dataset.py --refresh-hcris  # re-download CMS files
    uv run python scripts/build_gap_dataset.py --refresh-990    # re-ingest every IRS ZIP (~17 GB)
    uv run python scripts/build_gap_dataset.py --check-posted   # two HEAD requests to CMS
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import UTC
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from analytics import community_benefit_gap
from crosswalk import load_seed
from form990 import parse_tax_year
from form990 import write_parquet as write_990_parquet
from hcris import download_year, pivot_wide
from hcris import parse_zip as parse_hcris
from hcris import write_parquet as write_hcris_parquet
from hcris.download import hospital_2552_10_url
from sdoh import county_adi_from_block_group, load_svi_county

ARTIFACTS_DIR = Path("artifacts")
PARQUET_DIR = Path("data/parquet")
FORM990_RAW = Path("data/raw/form990")
TAX_YEAR = 2022
# 2023 carries most calendar-year filers' TY2022 returns; 2024 most fiscal-year
# filers'; 2025 and 2026 late and amended returns.
RELEASE_YEARS = (2023, 2024, 2025, 2026)
HCRIS_FYS = (2022, 2023)
# Later HCRIS files that are not loaded but, when the ZIP is on disk, are checked
# for crosswalk CCNs that have no report in HCRIS_FYS.
HCRIS_ALSO_CHECK = (2024,)
HCRIS_RAW = Path("data/raw/hcris")
USER_AGENT = "trove-build/1.0 (+https://troveproject.com)"
ADI_BG_CSV = Path("data/raw/adi/US_2023_ADI_Census_Block_Group_v4_0_1.csv")
SVI_COUNTY_CSV = Path("data/raw/svi/SVI_2022_US_county.csv")

# The columns the first published version of this table had, in their original
# order. New columns are appended after them so positional readers keep working.
LEGACY_COLUMNS = (
    "ein",
    "ccn_count",
    "hospital_name",
    "hcris_charity_care_cost",
    "hcris_uncompensated_care_cost",
    "hcris_total_operating_expenses",
    "hcris_fy_end_dt",
    "svi_overall_pct",
    "svi_socio_pct",
    "svi_household_pct",
    "svi_minority_pct",
    "svi_housing_pct",
    "sched_h_organization_name",
    "sched_h_tax_period_end",
    "sched_h_financial_assistance_at_cost",
    "sched_h_total_community_benefit",
    "sched_h_total_expenses",
    "charity_gap",
    "community_benefit_pct_of_expenses",
    "community_benefit_pct_of_hcris_expenses",
)
# Read these back as strings: they carry leading zeros or exceed float precision.
STRING_COLUMNS = ("ein", "ccn_list", "sched_h_object_id", "hcris_rpt_rec_num")
RATIO_COLUMNS = (
    "community_benefit_pct_of_expenses",
    "community_benefit_pct_of_hcris_expenses",
    "sched_h_fa_offset_pct_of_gross",
)


def load_hcris_wide(*, refresh: bool = False) -> pd.DataFrame:
    """One row per cost report across ``HCRIS_FYS``, tagged with ``hcris_file_fy``."""
    parts = []
    for fy in HCRIS_FYS:
        wide_path = PARQUET_DIR / "hcris" / "wide" / f"year={fy}" / "part.parquet"
        if wide_path.exists() and not refresh:
            print(f"  FY{fy}: using cached {wide_path}")
            parts.append(pd.read_parquet(wide_path))
            continue
        zip_path = download_year(fy, force=refresh)
        print(f"  FY{fy}: parsing {zip_path}")
        files = parse_hcris(zip_path)
        write_hcris_parquet(files, fy)
        wide = pivot_wide(files)
        wide.insert(0, "hcris_file_fy", fy)
        wide_path.parent.mkdir(parents=True, exist_ok=True)
        wide.to_parquet(wide_path, index=False)
        parts.append(wide)
    return pd.concat(parts, ignore_index=True)


def _zip_facts(zip_path: Path) -> dict:
    """Extract date (newest member timestamp inside the ZIP) and SHA-256 of a CMS ZIP."""
    with zipfile.ZipFile(zip_path) as zf:
        newest = max(info.date_time for info in zf.infolist())
    digest = hashlib.sha256()
    with zip_path.open("rb") as f:
        while chunk := f.read(1 << 20):
            digest.update(chunk)
    return {
        "extract_date": f"{newest[0]:04d}-{newest[1]:02d}-{newest[2]:02d}",
        "zip_sha256": digest.hexdigest(),
    }


def cms_posted_date(fy: int, zip_path: Path) -> str | None:
    """The date CMS posted a yearly ZIP: the Last-Modified header of its download URL.

    One HEAD request, nothing downloaded. The date is accepted only when the
    server's Content-Length equals the size of the ZIP on disk, so it describes
    the file this build read and not a later quarterly refresh. Returns None when
    the ZIP is not on disk, the sizes differ, or the request fails.
    """
    if not zip_path.exists():
        return None
    req = Request(hospital_2552_10_url(fy), method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=30) as resp:
            length = resp.headers.get("Content-Length")
            modified = resp.headers.get("Last-Modified")
    except (URLError, TimeoutError) as e:
        print(f"  FY{fy}: could not read the posted date from CMS ({e})")
        return None
    if not modified or not length or int(length) != zip_path.stat().st_size:
        print(f"  FY{fy}: the ZIP now on the CMS site is not the one on disk; no posted date")
        return None
    return parsedate_to_datetime(modified).astimezone(UTC).strftime("%Y-%m-%d")


def _zip_report_ccns(zip_path: Path) -> set[str]:
    """Provider numbers (CCNs) in a CMS HCRIS ZIP's report table."""
    with zipfile.ZipFile(zip_path) as zf:
        member = next(n for n in zf.namelist() if n.lower().endswith("_rpt.csv"))
        with zf.open(member) as f:
            rpt = pd.read_csv(f, header=None, usecols=[2], dtype=str)
    return set(rpt[2].str.strip())


def source_vintage(
    hcris_wide: pd.DataFrame,
    sched_h: pd.DataFrame,
    cw: pd.DataFrame,
    gap: pd.DataFrame,
    previous: dict | None = None,
    raw_dir: Path = HCRIS_RAW,
    posted_dates: dict[int, str | None] | None = None,
) -> dict:
    """Describe the inputs from the inputs themselves — nothing here is a literal.

    The CMS extract date and hash come from the ZIP on disk. When a ZIP has been
    deleted (the parsed Parquet is the cache), the values recorded by the previous
    build are carried forward only if the parsed file is unchanged (same report
    count and latest processing date); otherwise they are left null.

    ``posted_date`` (when CMS put the ZIP on its site) is not in the file itself.
    It comes from ``posted_dates`` (see ``cms_posted_date``) or, failing that, is
    carried forward from the previous build only while the ZIP hash, report count
    and latest processing date are all unchanged.
    """
    prev_files = {
        f["fiscal_year"]: f for f in ((previous or {}).get("cms_hcris") or {}).get("files", [])
    }
    files = []
    for fy in HCRIS_FYS:
        part = hcris_wide[hcris_wide["hcris_file_fy"] == fy]
        entry = {
            "fiscal_year": fy,
            "file": f"HOSP10FY{fy}.zip",
            "reports": int(len(part)),
            "latest_proc_dt": pd.Timestamp(part["proc_dt"].max()).strftime("%Y-%m-%d"),
            "extract_date": None,
            "posted_date": None,
            "zip_sha256": None,
        }
        zip_path = raw_dir / f"HOSP10FY{fy}.zip"
        prev = prev_files.get(fy)
        if zip_path.exists():
            entry.update(_zip_facts(zip_path))
        elif prev and all(prev.get(k) == entry[k] for k in ("reports", "latest_proc_dt")):
            entry.update({k: prev.get(k) for k in ("extract_date", "zip_sha256")})
        entry["posted_date"] = (posted_dates or {}).get(fy)
        if (
            entry["posted_date"] is None
            and prev
            and entry["zip_sha256"]
            and all(prev.get(k) == entry[k] for k in ("reports", "latest_proc_dt", "zip_sha256"))
        ):
            entry["posted_date"] = prev.get("posted_date")
        files.append(entry)

    # Crosswalk CCNs, for matched EINs, that have no cost report in the loaded files.
    pairs = cw[["ccn", "ein"]].dropna().drop_duplicates()
    pairs = pairs[pairs["ein"].isin(gap["ein"])]
    unreported = set(pairs.loc[~pairs["ccn"].isin(hcris_wide["prvdr_num"]), "ccn"])
    checked = [fy for fy in HCRIS_ALSO_CHECK if (raw_dir / f"HOSP10FY{fy}.zip").exists()]
    crosswalk = {
        "eins": int(cw["ein"].nunique()),
        "ccns_without_cost_report": len(unreported),
        "also_checked_fiscal_years": checked,
        "found_in_also_checked": None,
    }
    if checked:
        later: set[str] = set()
        for fy in checked:
            later |= _zip_report_ccns(raw_dir / f"HOSP10FY{fy}.zip")
        crosswalk["found_in_also_checked"] = len(unreported & later)
    else:
        prev_cw = (previous or {}).get("crosswalk") or {}
        if prev_cw.get("ccns_without_cost_report") == len(unreported) and prev_files == {
            f["fiscal_year"]: f for f in files
        }:
            crosswalk["also_checked_fiscal_years"] = prev_cw.get("also_checked_fiscal_years", [])
            crosswalk["found_in_also_checked"] = prev_cw.get("found_in_also_checked")

    by_release = sched_h.groupby("release_year").size()
    return {
        "tax_year": TAX_YEAR,
        "cms_hcris": {"form": "Hospital 2552-10", "files": files},
        "irs_990": {
            "release_years": list(RELEASE_YEARS),
            "schedule_h_returns": int(len(sched_h)),
            "schedule_h_eins": int(sched_h["ein"].nunique()),
            "returns_by_release_year": {str(int(k)): int(v) for k, v in by_release.items()},
            # ZIPs that held at least one tax-year Schedule H, not the number opened
            # (every ZIP of every release is opened; see packages/form990/README.md).
            "bulk_zips_with_schedule_h": int(sched_h["batch_id"].nunique())
            if "batch_id" in sched_h.columns
            else None,
        },
        "crosswalk": crosswalk,
    }


def load_schedule_h(*, refresh: bool = False) -> pd.DataFrame:
    """Every TY2022 Schedule H return across ``RELEASE_YEARS`` (not deduplicated)."""
    path = PARQUET_DIR / "form990" / "schedule_h" / f"year={TAX_YEAR}" / "part.parquet"
    if path.exists() and not refresh:
        cached = pd.read_parquet(path)
        if {"object_id", "batch_id", "financial_assistance_at_cost_gross"} <= set(cached.columns):
            print(f"  using cached {path}")
            return cached
        print(f"  cached {path} predates the current schema; re-ingesting")
    batch_cache = PARQUET_DIR / "form990" / "batches"
    if refresh:
        for stale in batch_cache.glob(f"ty{TAX_YEAR}_*.parquet"):
            stale.unlink()
    parts = []
    for release in RELEASE_YEARS:
        print(f"  release {release}:")
        parts.append(
            parse_tax_year(
                tax_year=TAX_YEAR,
                release_year=release,
                cache_dir=FORM990_RAW,
                keep_zips=False,
                xml_dir=FORM990_RAW / f"xml_ty{TAX_YEAR}",
                batch_cache_dir=batch_cache,
            )
        )
    sched_h = pd.concat(parts, ignore_index=True)
    write_990_parquet(sched_h, tax_year=TAX_YEAR, out_dir=PARQUET_DIR / "form990")
    return sched_h


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh-hcris", action="store_true", help="re-download CMS HCRIS files")
    ap.add_argument("--refresh-990", action="store_true", help="re-ingest every IRS bulk ZIP")
    ap.add_argument(
        "--check-posted",
        action="store_true",
        help="ask CMS (one HEAD request per file) when each HCRIS ZIP on disk was posted",
    )
    args = ap.parse_args()

    print(f"Loading HCRIS FY{', FY'.join(map(str, HCRIS_FYS))}...")
    hcris_wide = load_hcris_wide(refresh=args.refresh_hcris)
    print(f"  {len(hcris_wide):,} cost reports, {hcris_wide['prvdr_num'].nunique():,} CCNs")

    print(f"Ingesting TY{TAX_YEAR} Schedule H from releases {RELEASE_YEARS}...")
    sched_h = load_schedule_h(refresh=args.refresh_990)
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
    computable = gap["charity_gap"].notna()
    aligned = gap["period_aligned"]
    in_cw = sched_h.loc[sched_h["ein"].isin(cw["ein"]), "ein"].nunique()
    print(f"  Crosswalk EINs with a TY{TAX_YEAR} Schedule H: {in_cw:,} of {cw['ein'].nunique():,}")
    print(f"  Matched hospital systems: {len(gap):,}")
    print(f"  Computable (both figures present): {computable.sum():,}")
    print(
        f"  Period-aligned: {aligned.sum():,}  (and computable: {(aligned & computable).sum():,})"
    )
    no_s10 = gap["hcris_charity_care_cost"].isna()
    print(f"  S-10 charity care missing (not $0): {no_s10.sum():,}")
    print(f"  Schedule H 7a missing: {gap['sched_h_financial_assistance_at_cost'].isna().sum():,}")

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
    public = public.sort_values(["sched_h_organization_name", "ein"], na_position="last")
    legacy = [c for c in LEGACY_COLUMNS if c in public.columns]
    public = public[legacy + [c for c in public.columns if c not in legacy]]
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    full_csv = ARTIFACTS_DIR / f"community_benefit_gap_{TAX_YEAR}.csv"
    # ``to_csv(float_format=...)`` applies one format to every float column at once.
    # A blanket "%.0f" silently flattened the sub-100 ratio columns — a 12.9% ratio
    # wrote as "0" for all but a handful of rows. Format the two families separately:
    # dollars and percentiles as nullable integers, ratios to one decimal. Nullable
    # integers write a missing value as an empty field, never as 0.
    ratio_cols = [c for c in RATIO_COLUMNS if c in public.columns]
    int_cols = [
        c
        for c in public.select_dtypes("number").columns
        if c not in ratio_cols and c not in STRING_COLUMNS
    ]
    public[ratio_cols] = public[ratio_cols].astype("Float64").round(1)
    public[int_cols] = public[int_cols].round(0).astype("Int64")
    for c in ("hcris_fy_bgn_dt", "hcris_fy_end_dt", "sched_h_tax_period_begin"):
        if c in public.columns:
            public[c] = pd.to_datetime(public[c]).dt.strftime("%Y-%m-%d")
    public["sched_h_tax_period_end"] = pd.to_datetime(public["sched_h_tax_period_end"]).dt.strftime(
        "%Y-%m-%d"
    )
    public.to_csv(full_csv, index=False)
    print(
        f"  → {full_csv} ({full_csv.stat().st_size / 1024:.1f} KB, {len(public.columns)} columns)"
    )
    for c in ratio_cols:
        ok = public[c].notna().sum()
        print(f"    {c}: {ok:,} of {len(public):,} rows populated")

    sources_out = ARTIFACTS_DIR / f"community_benefit_gap_{TAX_YEAR}_sources.json"
    previous = json.loads(sources_out.read_text()) if sources_out.exists() else None
    posted = (
        {fy: cms_posted_date(fy, HCRIS_RAW / f"HOSP10FY{fy}.zip") for fy in HCRIS_FYS}
        if args.check_posted
        else None
    )
    vintage = source_vintage(hcris_wide, sched_h, cw, gap, previous, posted_dates=posted)
    sources_out.write_text(json.dumps(vintage, indent=2) + "\n")
    print(f"  → {sources_out}")
    for f in vintage["cms_hcris"]["files"]:
        print(
            f"    FY{f['fiscal_year']}: {f['reports']:,} reports, extract {f['extract_date']}, "
            f"posted {f['posted_date']}, latest processing date {f['latest_proc_dt']}"
        )
    print(f"    crosswalk: {vintage['crosswalk']}")


if __name__ == "__main__":
    main()
