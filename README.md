# trove

Open-source parsers, agents, and visualizations for underused healthcare datasets.

## What this is

A side-by-side comparison tool for the charity-care cost numbers that nonprofit U.S. hospitals report to two different regulators: CMS (Worksheet S-10 of the Medicare Cost Report) and the IRS (Form 990 Schedule H Part I line 7a). Both lines are *intended* to capture the cost of care provided to patients who couldn't pay, but the rules and scope diverge enough that the two numbers can legitimately differ — often by a lot.

For tax year 2022, the funnel:

- **1,334 systems matched** at the EIN level (HCRIS CCNs rolled up to a 990 EIN via CBI's crosswalk).
- **1,295 computable** (39 systems have a blank Schedule H 7a, so a charity_gap can't be defined).
- **372 also period-aligned** within 1 month (HCRIS fiscal-year end ≈ 990 tax-period end). Alignment is what makes the comparison meaningful — most of the rest are 12 months out of phase because HCRIS uses the federal-fiscal-year reporting cycle as its file naming, not the underlying period covered.
- **228 also material** — both filings ≥ $500K. The dollar threshold is a noise floor, not a comparability test; the 144 aligned-but-sub-$500K systems are visible on the site when you toggle materiality off.

Among the 228 aligned + material systems:

- **Median proportional gap: 25%** — typical disagreement is large.
- **53 systems (23%)** disagree by more than 50%.
- **Largest aligned-period $ gap:** Yale New Haven Hospital — $36M HCRIS vs. $113M IRS = −$78M / -68%.
- **Largest aligned-period positive gap:** Orlando Health — $143M HCRIS vs. $73M IRS = +$71M / 49%.
- **Largest aligned-period proportional gap:** Western Regional Medical Center — $18M HCRIS vs. $1M IRS = +94%.

**→ Search the 228 aligned + material systems (or the full 1,295 computable) at [troveproject.com](https://troveproject.com).**

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
- **`sdoh`** — Social Determinants of Health enrichments. v0.1 ships county-level Area Deprivation Index aggregation from UW's Neighborhood Atlas block-group release (cite: Kind AJH, Buckingham W. *N Engl J Med* 2018;378:2456-2458). Used to attach a "service-area deprivation" signal to each hospital row.

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

- **M5.1** — `sdoh` package added. County-level Area Deprivation Index attached to every gap-dataset row (~98% coverage); surfaced on the troveproject.com detail card with national-percentile + state-decile + a one-line interpretation. Skill references updated so `hcris-analyst` can use ADI as a peer-cohort dimension. Raw block-group ADI data is gitignored per UW's terms; we publish only derived per-system aggregates.
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
- **Area Deprivation Index** — derived (county-level aggregates) from the University of Wisconsin Neighborhood Atlas block-group ADI release. Raw block-group data is **not redistributed** by trove — users with `data/raw/adi/` populated have downloaded it themselves under UW's terms. Required citation: **Kind AJH, Buckingham W. Making Neighborhood Disadvantage Metrics Accessible: The Neighborhood Atlas. *N Engl J Med* 2018;378:2456-2458.** See `packages/sdoh/README.md` for the full licensing posture.
