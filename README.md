# trove

Open-source parsers, agents, and visualizations for underused healthcare datasets.

## What this is

trove builds open-source lookup tools, parsers, and Claude skills on top of public-domain healthcare datasets that are widely cited but rarely usable in their raw form. Site: [troveproject.com](https://troveproject.com).

Two areas live in v1:

### [/drugs](https://troveproject.com/drugs/) — FDA drug approvals

Look up any FDA Novel Drug Approval from 2021–2024 (192 drugs). Each row carries the application number, approval date, indication, and a deep link to the drugs@FDA application overview where every approval-package document lives (medical review, statistical review, pharmacology review, etc.). About two-thirds of rows also include a direct link to the FDA-approved label PDF. Companion Claude skill `fda-analyst` reads those PDFs at query time when a user asks about a specific approval.

Sources: FDA's annual *Novel Drug Approvals* curated lists; drugs@FDA database. US government work, public domain.

### [/hospitals](https://troveproject.com/hospitals/) — hospital reporting (CMS + IRS)

A lookup tool for the charity-care cost numbers that nonprofit U.S. hospitals report to two different regulators: CMS (Worksheet S-10 of the Medicare Cost Report) and the IRS (Form 990 Schedule H Part I line 7a). Both lines are *intended* to capture the cost of care provided to patients who couldn't pay, but the rules and scope diverge enough that the two numbers can legitimately differ — often by a lot. Search any of 1,295 nonprofit hospital systems for tax year 2022 and see the two filings side-by-side, with period-alignment context, a home-county Social Vulnerability Index proxy, and a deep link to the actual 990 on ProPublica.

For tax year 2022, the funnel: **1,334 systems matched** at the EIN level → **1,295 computable** → **372 period-aligned within 1 month** → **228 also material** (both filings ≥ $500K). Among those 228, the median proportional gap is **25%**.

Full data: [`artifacts/community_benefit_gap_2022.csv`](artifacts/community_benefit_gap_2022.csv) · Method: [`artifacts/community_benefit_gap_2022_summary.md`](artifacts/community_benefit_gap_2022_summary.md).

## Reproduce

```bash
git clone https://github.com/cbetz/trove
cd trove && uv sync --all-packages
# /hospitals dataset:
uv run python scripts/build_gap_dataset.py
# /drugs dataset:
uv run python scripts/build_fda_index.py
```

## What's in the box

**Hospital reporting area:**

- **`hcris`** — CMS Medicare Cost Reports (form 2552-10) parser with a 44-variable semantic dictionary. Raw HCRIS ships as headerless long-skinny CSVs; this turns them into tidy DataFrames and partitioned Parquet.
- **`form990`** — IRS Form 990 Schedule H parser. Bulk-XML download, index reader, and 19 fields per filing including Part I 7a–k community benefit amounts and Part III bad debt.
- **`crosswalk`** — CCN ↔ EIN crosswalk (3,523 hospitals, 2,385 EINs). Bundled from Community Benefit Insight.
- **`analytics`** — composed queries. `community_benefit_gap()` is the headline primitive.
- **`sdoh`** — Social Determinants of Health enrichments. Ships **CDC Social Vulnerability Index 2022 county-level** (public domain — included in the public bundles) and **UW Area Deprivation Index** county aggregation (local-only — UW's terms are non-sublicensable).

**FDA drug approvals area:**

- **`fda_sba`** — Scrapes FDA's annual *Novel Drug Approvals* pages (curated NMEs and novel BLAs), extracts application number / drug name / active ingredient / approval date / indication, and emits links to the approval-package PDFs. v0.1 covers 2021–2024 (~192 drugs).

**Skills (drop into `~/.claude/skills/`):**

- `skills/hcris-analyst/` — natural-language queries over the HCRIS + 990 + crosswalk bundle.
- `skills/fda-analyst/` — questions about specific FDA drug approvals; reads approval-package PDFs at query time.

**Site:** static, deployed to Vercel at troveproject.com.

## Dev setup

```bash
uv sync --all-packages
uv run pytest
uv run ruff check
```

## Layout

```
packages/         Python libraries (hcris, form990, crosswalk, analytics, sdoh, fda_sba)
skills/           Claude skill bundles
web/              Static site at troveproject.com
pipelines/        ETL orchestration — TBD
notebooks/        Exploratory work, not shipped
docs/             mkdocs-material site
artifacts/        Committable, GitHub-viewable result tables
scripts/          Build + demo scripts
```

## Status

- **M6** — Multi-area site: trove now has two live areas at troveproject.com (`/drugs` and `/hospitals`), each with its own search-first lookup page, methodology, and Claude skill. New `fda_sba` package indexes FDA Novel Drug Approvals 2021–2024 (~192 drugs); new `fda-analyst` Claude skill reads approval-package PDFs at query time. Adding more areas in the future is now a matter of adding a package + a page + a skill.
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
