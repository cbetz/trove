# trove

Open-source parsers, agents, and visualizations for underused healthcare datasets.

## What this is

A lookup tool for the charity-care cost numbers that nonprofit U.S. hospitals report to two different regulators: CMS (Worksheet S-10 of the Medicare Cost Report) and the IRS (Form 990 Schedule H Part I line 7a). Both lines are *intended* to capture the cost of care provided to patients who couldn't pay, but the rules and scope diverge enough that the two numbers can legitimately differ — often by a lot.

The site at [troveproject.com](https://troveproject.com) lets you search any of 1,295 nonprofit hospital systems for tax year 2022 and see the two filings side-by-side, with period-alignment context, the service-area Social Vulnerability Index, and a deep link to the actual 990 on ProPublica.

For tax year 2022, the funnel:

- **1,334 systems matched** at the EIN level (HCRIS CCNs rolled up to a 990 EIN via CBI's crosswalk).
- **1,295 computable** (39 systems have a blank Schedule H 7a, so a charity_gap can't be defined).
- **372 period-aligned** within 1 month (HCRIS fiscal-year end ≈ 990 tax-period end). Alignment is what makes the comparison meaningful — most of the rest are 12 months out of phase because HCRIS uses the federal-fiscal-year reporting cycle as its file naming, not the underlying period covered.
- **228 also material** — both filings ≥ $500K. The dollar threshold is a noise floor, not a comparability test.

Among the 228 aligned + material systems, the median proportional gap is **25%** (i.e., typical cross-form disagreement is large). 53 systems (23%) disagree by more than half. The full per-system data is in the published Parquet bundle and CSV artifact for anyone who wants to do their own analysis.

Full data: [`artifacts/community_benefit_gap_2022.csv`](artifacts/community_benefit_gap_2022.csv) · Method and caveats: [`artifacts/community_benefit_gap_2022_summary.md`](artifacts/community_benefit_gap_2022_summary.md). The per-system artifact has all 1,334 rows including misaligned ones; use `hcris_fy_end_dt` and `sched_h_tax_period_end` to filter to overlapping periods.

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
- **`sdoh`** — Social Determinants of Health enrichments. v0.2 ships **CDC Social Vulnerability Index 2022 county-level** (public domain — included in the public bundles) and **UW Area Deprivation Index** county aggregation (local-only — UW's terms are non-sublicensable). Both attach a "service-area" signal to each hospital row; the public site shows SVI, and a user with their own UW ADI download gets ADI in their local pipeline.

On top of those: a Claude skill bundle (`skills/hcris-analyst`, in progress) and a static Observable-style site (`web/`, deployed to Vercel).

## Dev setup

```bash
uv sync --all-packages
uv run pytest
uv run ruff check
```

## Layout

```
packages/         Python libraries (hcris, form990, crosswalk, analytics, sdoh)
skills/           Claude skill bundles
web/              Static site at troveproject.com
pipelines/        ETL orchestration — TBD
notebooks/        Exploratory work, not shipped
docs/             mkdocs-material site
artifacts/        Committable, GitHub-viewable result tables
scripts/          Build + demo scripts
```

## Status

- **M5.2** — CDC Social Vulnerability Index added to `sdoh` and wired through to the public bundles + the troveproject.com detail card. Each row now shows a "Service area (SVI)" signal: e.g. *"81st national percentile — high social vulnerability in the system's home county"*. SVI is fully public-domain, so unlike ADI this ships in the public CSV / Parquet / JSON. ADI capability remains in the local pipeline for users with their own UW license.
- **M5.1** — `sdoh` package added with `county_adi_from_block_group()`. ADI flows through the *local* pipeline only — UW's non-sublicensable terms mean it can't be in the public bundles.
- **M5** — `hcris-analyst` Claude skill shipped. Natural-language queries against HCRIS + 990 + the gap dataset, powered by DuckDB-over-HTTPS against three Parquet bundles served from troveproject.com (`hcris_2023_wide.parquet`, `schedule_h_2022.parquet`, `community_benefit_gap_2022.parquet`). Skill bundle at [`skills/hcris-analyst/`](skills/hcris-analyst/) includes the SKILL.md and reference docs (field dictionary, peer-cohort definitions, Schedule H map, runnable example queries).
- **M4.3** — Validation pass against IRS source XML (6 spot-checks, all exact); per-row alignment signals (HCRIS fiscal year end vs. 990 tax period end); default view filtered to aligned + material subset (228 systems); ProPublica deep links per row.
- **M4.2** — TY2022 ingest expanded to 2024+2025+2026 IRS release years (late filers and amendments). Form990 parser now handles DEFLATE64 ZIPs (introduced by IRS in 2025 release).
- **M4.1** — first published TY2022 gap dataset from the 2024 release year alone (1,317 systems).
- **M4** — `crosswalk` package + `analytics.community_benefit_gap()`.
- **M3** — `form990` Schedule H parser, full TY2022 ingest.
- **M2.5** — HCRIS semantic dictionary expanded to 44 variables.
- **M2** — `hcris.pivot_wide()` and dictionary v1.
- **M1** — `hcris` parser for Hospital 2552-10.

Per-package detail in `packages/*/README.md`.

## License and citations

trove code is **MIT-licensed**. Underlying data sources have their own licensing and citation requirements:

- **CMS HCRIS** — US government work, public domain. No citation required; suggested phrasing: "CMS Healthcare Cost Report Information System (HCRIS), Hospital form 2552-10".
- **IRS Form 990 e-file** — US government work, public domain. Suggested: "IRS Tax-Exempt Organization Form 990 e-file (Schedule H)".
- **CCN ↔ EIN crosswalk** — derived from Community Benefit Insight (RTI International, funded by RWJF, frozen Dec 6 2024). Suggested: "Community Benefit Insight; RTI Press 10.3768/rtipress.2023.op.0080.2302".
- **CDC Social Vulnerability Index** — county-level 2022 release, US government work / public domain. Included in the public bundles as `svi_overall_pct` plus four sub-theme columns. Source: https://www.atsdr.cdc.gov/place-health/php/svi/index.html.
- **Area Deprivation Index** — UW's Neighborhood Atlas terms are non-sublicensable and forbid redistribution of the data, derived or otherwise, outside individual-and-employer "internal non-profit educational, research, and public health" use. trove **does not include ADI** in the public bundles for this reason. The `sdoh` package supports local pipelines: download the block-group CSV from `https://www.neighborhoodatlas.medicine.wisc.edu/` (registration required) and the gap dataset built locally will include county-aggregated ADI columns. Required citation when you use that local output anywhere: **Kind AJH, Buckingham W. Making Neighborhood Disadvantage Metrics Accessible: The Neighborhood Atlas. *N Engl J Med* 2018;378:2456-2458; PMCID: PMC6051533. AND: University of Wisconsin School of Medicine and Public Health. {year} Area Deprivation Index {version}. Downloaded from https://www.neighborhoodatlas.medicine.wisc.edu/ {date}.**
