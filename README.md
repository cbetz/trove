# trove

Open-source parsers, agents, and visualizations for underused healthcare datasets.

## The first finding

**Across 1,334 nonprofit U.S. hospital systems for tax year 2022:**

- **$5.14B** total absolute gap between charity-care cost reported on CMS Worksheet S-10 and "financial assistance at cost" reported on IRS Form 990 Schedule H.
- **60% of systems** report MORE charity care to CMS than to the IRS.
- **Top single gap:** Memorial Hermann Health System — $428M to CMS vs. $307M to the IRS, a +$121M difference.
- **$60.5B** total community benefit reported on Schedule H system-wide.

These two filings are *supposed* to report the same underlying number under different rules. trove makes the comparison computable.

**→ Search any of the 1,334 systems at [troveproject.com](https://troveproject.com).**

Full table: [`artifacts/community_benefit_gap_2022.csv`](artifacts/community_benefit_gap_2022.csv) · Top 50: [`artifacts/community_benefit_gap_2022_top50.csv`](artifacts/community_benefit_gap_2022_top50.csv) · Method and caveats: [`artifacts/community_benefit_gap_2022_summary.md`](artifacts/community_benefit_gap_2022_summary.md).

## Reproduce

```bash
git clone https://github.com/cbetz/trove
cd trove && uv sync --all-packages
uv run python scripts/build_gap_dataset.py
```

## What's in the box

Phase 1 packages:

- **`hcris`** — CMS Medicare Cost Reports (form 2552-10) parser with a 44-variable semantic dictionary. Raw HCRIS ships as headerless long-skinny CSVs; this turns them into tidy DataFrames and partitioned Parquet.
- **`form990`** — IRS Form 990 Schedule H parser. Bulk-XML download, index reader, and 19 fields per filing including Part I 7a–k community benefit amounts and Part III bad debt.
- **`crosswalk`** — CCN ↔ EIN crosswalk (3,523 hospitals, 2,385 EINs) — the bridge that makes HCRIS-to-990 joins possible. Bundled from Community Benefit Insight.
- **`analytics`** — composed queries. `community_benefit_gap()` is the headline primitive.

On top of those: a Claude skill bundle (`skills/hcris-analyst`, in progress) and a static Observable-style site (`web/`, deployed to Vercel).

## Dev setup

```bash
uv sync --all-packages
uv run pytest
uv run ruff check
```

## Layout

```
packages/         Python libraries (hcris, form990, crosswalk, analytics)
skills/           Claude skill bundles
web/              Static site at troveproject.com
pipelines/        ETL orchestration — TBD
notebooks/        Exploratory work, not shipped
docs/             mkdocs-material site
artifacts/        Committable, GitHub-viewable result tables
scripts/          Build + demo scripts
```

## Status

- **M4.2** — TY2022 ingest expanded to 2024+2025+2026 IRS release years (late filers and amendments included). 1,334 systems, $60.5B community benefit, $5.14B absolute gap. Form990 parser now handles DEFLATE64 ZIPs (introduced by IRS in 2025 release).
- **M4.1** — first published TY2022 gap dataset from the 2024 release year alone (1,317 systems).
- **M4** — `crosswalk` package + `analytics.community_benefit_gap()`.
- **M3** — `form990` Schedule H parser, full TY2022 ingest.
- **M2.5** — HCRIS semantic dictionary expanded to 44 variables.
- **M2** — `hcris.pivot_wide()` and dictionary v1.
- **M1** — `hcris` parser for Hospital 2552-10.

Per-package detail in `packages/*/README.md`.

## License

MIT. Source data (CMS HCRIS, IRS 990) is US government work and public domain.
