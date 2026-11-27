# trove

Open-source parsers, published data files, and Claude Code skills for public-domain U.S. healthcare data that is widely cited but hard to use raw. The first area sets two public hospital filings side by side; the second indexes FDA novel drug approvals.

**Hospital charity care: the IRS figure and the CMS figure, side by side.** Nonprofit hospitals publish a financial-assistance figure on IRS Form 990 Schedule H (Part I, line 7a) and a charity-care figure on the CMS cost report (Worksheet S-10, line 23). trove puts the two next to each other for 2,099 matched hospital systems, tax year 2022, with the components from each filing that show what is in the difference. The two lines are defined differently, so they can differ when both are filed correctly.

A ranked index covers the 493 hospitals, in 48 states, where one facility files both for the same fiscal period. In 107 of them the two figures differ by more than 50% of the larger; the CMS figure is the larger in 321, the IRS figure in 169, and 3 show the same amount. Those counts describe two differently defined lines: 143 of the 493 list offsetting revenue in line 7a column (d), and 301 show an amount on S-10 line 5.

An example, Yale New Haven Hospital (fiscal year ending 2023-09-30 on both filings):

- IRS line 7a: $257.3M total expense (c), $144.2M offsetting revenue (d), **$113.1M net (e)**.
- CMS S-10 line 23: **$35.6M**. S-10 line 5: −$71.5M.
- Of the $77.5M difference, about $71.5M appears to be Connecticut's hospital provider tax net of the state supplemental payments it funds: the amount on S-10 line 5, which the cost report keeps separate from charity care. The worksheet behind the IRS line is not public, so this is a reconciliation from the hospital's own filings, not a figure the hospital has stated.

**[Look up any hospital →](https://troveproject.com/hospitals/)** · **[How to read a difference →](https://troveproject.com/notes/charity-care-gap/)** · [ranked index](artifacts/charity_care_gap_index_2022.md) · [method](artifacts/community_benefit_gap_2022_summary.md)

> A difference between the two figures is a reason to open both filings and read the components. It does not, by itself, say anything about either filing.

## Query it in one line

The published tables are Parquet over HTTPS, so DuckDB reads them with no download and no API key. This runs as pasted:

```sql
INSTALL httpfs; LOAD httpfs;

SELECT hospital_name,
       sched_h_financial_assistance_at_cost AS irs_7a_net,
       hcris_charity_care_cost              AS cms_s10_line23,
       sched_h_tax_period_end, hcris_fy_end_dt
FROM 'https://troveproject.com/data/community_benefit_gap_2022.parquet'
WHERE sched_h_organization_name ILIKE '%yale%';
```

```
┌─────────────────────────┬─────────────┬────────────────┬────────────────────────┬─────────────────────┐
│      hospital_name      │ irs_7a_net  │ cms_s10_line23 │ sched_h_tax_period_end │   hcris_fy_end_dt   │
│         varchar         │   double    │     double     │       timestamp        │      timestamp      │
├─────────────────────────┼─────────────┼────────────────┼────────────────────────┼─────────────────────┤
│ YALE NEW HAVEN HOSPITAL │ 113100512.0 │     35568680.0 │ 2023-09-30 00:00:00    │ 2023-09-30 00:00:00 │
└─────────────────────────┴─────────────┴────────────────┴────────────────────────┴─────────────────────┘
```

Change `'%yale%'` to part of your hospital's legal name. (The CMS column can be `NULL`: a hospital with no value on S-10 line 23 is published as missing, never `0`.)

The components for the Connecticut hospitals with the largest differences:

```sql
SELECT hospital_name,
       sched_h_financial_assistance_gross::BIGINT          AS irs_7a_c,
       sched_h_financial_assistance_offset_revenue::BIGINT AS irs_7a_d,
       sched_h_financial_assistance_at_cost::BIGINT        AS irs_7a_e,
       hcris_charity_care_cost::BIGINT                     AS s10_line23,
       hcris_medicaid_dsh_supplemental::BIGINT             AS s10_line5,
       charity_gap::BIGINT                                 AS cms_minus_irs
FROM 'https://troveproject.com/data/community_benefit_gap_2022.parquet'
WHERE state = 'CT' AND period_aligned AND charity_gap IS NOT NULL
ORDER BY abs(charity_gap) DESC
LIMIT 6;
```

```
┌──────────────────────────────┬───────────┬───────────┬───────────┬────────────┬───────────┬───────────────┐
│        hospital_name         │ irs_7a_c  │ irs_7a_d  │ irs_7a_e  │ s10_line23 │ s10_line5 │ cms_minus_irs │
│           varchar            │   int64   │   int64   │   int64   │   int64    │   int64   │     int64     │
├──────────────────────────────┼───────────┼───────────┼───────────┼────────────┼───────────┼───────────────┤
│ YALE NEW HAVEN HOSPITAL      │ 257262512 │ 144162000 │ 113100512 │   35568680 │ -71469000 │     -77531832 │
│ GREENWICH HOSPITAL           │  34595829 │  11028000 │  23567829 │    3984548 │ -19837000 │     -19583281 │
│ LAWRENCE & MEMORIAL HOSPITAL │  32103082 │  11014000 │  21089082 │    4783389 │ -16316000 │     -16305693 │
│ BRIDGEPORT HOSPITAL          │  64722486 │  32019000 │  32703486 │   19539141 │ -12084000 │     -13164345 │
│ ST. MARYS HOSPITAL           │    518747 │      NULL │    518747 │    3392481 │      NULL │       2873734 │
│ HARTFORD HOSPITAL            │  21532625 │      NULL │  21532625 │   24361522 │ -12598390 │       2828897 │
└──────────────────────────────┴───────────┴───────────┴───────────┴────────────┴───────────┴───────────────┘
```

`period_aligned` is true when the cost report's period ends within one month of the 990's (1,979 of the 2,099 rows; 1,797 of the 1,904 with both figures). A difference on a row that is not aligned compares two different years. Four tables are served:

| URL | What's in it |
|---|---|
| [`community_benefit_gap_2022.parquet`](https://troveproject.com/data/community_benefit_gap_2022.parquet) | The matched table: Worksheet S-10 summed per EIN, joined to Schedule H line 7a, with components (2,099 × 51 from 1.1.0; also as [CSV](https://troveproject.com/data/community_benefit_gap_2022.csv)) |
| [`hcris_2022_wide.parquet`](https://troveproject.com/data/hcris_2022_wide.parquet) | HCRIS Hospital 2552-10, FY2022 file, one row per cost report, 52 named variables (6,069 rows; new in 1.1.0) |
| [`hcris_2023_wide.parquet`](https://troveproject.com/data/hcris_2023_wide.parquet) | The same for the FY2023 file (6,109 rows). CMS files a report under the fiscal year in which its period begins, so the two union directly |
| [`schedule_h_2022.parquet`](https://troveproject.com/data/schedule_h_2022.parquet) | IRS 990 Schedule H returns, tax year 2022, columns (c), (d) and (e) for every Part I line (2,360 × 51 from 1.1.0) |

Or skip SQL: the [`hcris-analyst`](https://troveproject.com/skills/hcris-analyst/) Claude Code skill answers the same questions in plain English.

## Look it up

- **[troveproject.com/hospitals/](https://troveproject.com/hospitals/)**: the ranked index of 493 hospitals, plus a lookup of 2,099 matched nonprofit hospital systems with both figures, their components, and links to both filings
- **[troveproject.com/drugs/](https://troveproject.com/drugs/)**: 268 FDA novel drug approvals, 2021–2025 (238 CDER NMEs and novel BLAs + 30 CBER cell and gene therapies); click any record for its full approval package
- **[troveproject.com/skills/](https://troveproject.com/skills/)**: install the trove Claude Code plugin (`fda-analyst` + `hcris-analyst`)
- **[troveproject.com/docs/](https://troveproject.com/docs/)**: plain-language explainers: [what is HCRIS](https://troveproject.com/docs/hcris/), [what is IRS 990 Schedule H](https://troveproject.com/docs/schedule-h/), [what is an FDA novel drug approval](https://troveproject.com/docs/fda-nme/)
- **[troveproject.com/notes/](https://troveproject.com/notes/)**: write-ups from the published tables

## What this is

Open-source parsers, Parquet/JSON bundles, and Claude Code skills for public-domain healthcare datasets that are widely cited but rarely usable in raw form. CMS publishes 100,000-row headerless long-skinny CSVs. The IRS publishes 990s as XML inside bulk ZIPs. The FDA scatters approval reviews across hundreds of PDF directories. trove does the parsing, joining, and packaging so the data is browsable and queryable. MIT-licensed; the data underneath is public domain.

Two areas live today:

### [/hospitals](https://troveproject.com/hospitals/) — hospital reporting (CMS + IRS)

Two public figures for each nonprofit hospital, side by side:

- **IRS Form 990, Schedule H, Part I, line 7a** reports financial assistance at cost: column (c) total expense, column (d) direct offsetting revenue, and column (e) net, which is (c) − (d).
- **CMS cost report (form 2552-10), Worksheet S-10, line 23, column 3** is the cost of charity care after patient payments: uninsured patients (column 1) plus insured patients (column 2).

The two lines are defined differently. The IRS Schedule H instructions (Worksheet 1, line 4) have a filer include Medicaid or provider taxes in the line 7a cost when payments from an uncompensated care pool or DSH program in its state are intended primarily to offset the cost of financial assistance, with that pool revenue reported as offsetting revenue; otherwise those amounts belong on line 7b. The cost report keeps Medicaid DSH and supplemental payments, net of provider taxes, on a separate line (S-10 line 5) that is not part of line 23. The S-10 insured column counts deductibles and coinsurance written off. So the two can differ when both are filed correctly, and the published components are there so a difference can be read.

For tax year 2022 the funnel is: **2,099 systems matched** at the EIN level → **1,904 with both figures** → **1,797 period-aligned** (cost report ending within one month of the 990) → **1,642 with a single cost report** → **493 in the ranked index**, which also requires both figures to be at least $1M and total expenses on the two filings to be within 5%. Multi-hospital systems (Mayo Clinic's return covers 19 cost reports, Cleveland Clinic's 17) are in the lookup but not the index.

**Missing is not zero.** 159 matched systems have no value on S-10 line 23 and 53 have a blank line 7a column (e). Those rows are published with an empty value and no difference, never `0`. The Johns Hopkins Hospital, for example, files a Worksheet S-10 with no value on line 23; St. Jude Children's Research Hospital and Texas Children's Hospital have no Worksheet S-10 in the CMS file.

Each row carries both fiscal periods, the cost report's status, a home-county Social Vulnerability Index value, and the object id of the return, which links to its Schedule H on ProPublica.

Ranked index: [`artifacts/charity_care_gap_index_2022.md`](artifacts/charity_care_gap_index_2022.md) · Full data: [`artifacts/community_benefit_gap_2022.csv`](artifacts/community_benefit_gap_2022.csv) · Method and every caveat: [`artifacts/community_benefit_gap_2022_summary.md`](artifacts/community_benefit_gap_2022_summary.md).

Sources: CMS HCRIS hospital cost report files for fiscal years 2022 and 2023 (extract generated 2026-10-02, posted 2026-10-05); IRS Form 990 e-file releases 2023 through 2026, returns for tax year 2022; the Community Benefit Insight CCN-to-EIN crosswalk (December 2024).

### [/drugs](https://troveproject.com/drugs/) — FDA drug approvals

Every FDA novel drug approval from 2021–2025 (268 drugs, by original approval date) across both regulatory centers: **CDER** (238 NMEs and novel antibody BLAs from the annual *Novel Drug Approvals* lists) plus **CBER** (30 cell and gene therapy approvals: Lenmeldy, Casgevy, Lyfgenia, Beqvez, Hemgenix, Roctavian, Adstiladrin, and others). Each row carries application number, sponsor, approval date, indication, a `regulatory_center` column, and a deep link to the approval-package documents — medical, statistical, pharmacology, and chemistry reviews. The `fda-analyst` skill reads those PDFs at query time.

For CDER approvals each record also links the approval letter and the review package posted with the original approval, and carries the review designation, orphan, accelerated approval, breakthrough and fast track status and the FDA receipt date from FDA's compilation. 2025 approvals link the label and the drugs@FDA record; their approval-letter and review links are not collected yet. Where openFDA's label data records an established pharmacologic class (110 of 268), the record has that too.

Beyond the per-drug index: a list for [every approval year from 1985](https://troveproject.com/drugs/2025/), [approval statistics](https://troveproject.com/drugs/statistics/) (approvals per year, designation shares, receipt-to-approval times), and FDA's *Compilation of CDER NME and New Biologic Approvals* (1,387 approvals, 1985–2025) [converted from Excel to CSV and Parquet](https://troveproject.com/drugs/compilation/).

Sources: FDA's annual *Novel Drug Approvals* lists (CDER); *Approved Cellular and Gene Therapy Products* page (CBER); drugs@FDA; *Compilation of CDER NME and New Biologic Approvals*. US government work, public domain.

## Install the skills

trove is packaged as a Claude Code plugin (`.claude-plugin/plugin.json`, version 1.2.0) containing both skills.

**Plugin install** — Anthropic's community marketplace:

```
/plugin marketplace add anthropics/claude-plugins-community
/plugin install trove@claude-community
```

That's the public community marketplace, not the separate official `claude-plugins-official` one.

Restart Claude Code and both skills are loaded. Each skill's `description` tells Claude when to invoke it — you don't call them by name.

- `skills/hcris-analyst/` — natural-language queries over hospital reporting (HCRIS S-10 + IRS 990 Schedule H + CCN↔EIN crosswalk + CDC SVI). Profile lookups, peer context, glossary, and the components behind a difference between the two filings.
- `skills/fda-analyst/` — questions about specific FDA approvals; reads approval-package PDFs at query time.

The plugin is the documented install path. To copy the skill folders by hand instead (per-project install, Claude.ai upload), or to author a new skill, see [`skills/README.md`](skills/README.md).

## What's in the box

**Hospital reporting:**

- **`hcris`** — CMS Medicare Cost Reports (form 2552-10) parser with a 52-variable semantic dictionary. Turns headerless long-skinny CSVs into tidy DataFrames and partitioned Parquet.
- **`form990`** — IRS Form 990 Schedule H parser. Bulk-XML download and ZIP discovery, columns (c), (d) and (e) for Part I lines 7a–k, and Part III bad debt. Handles the DEFLATE64 ZIPs the IRS introduced in 2025.
- **`crosswalk`** — CCN ↔ EIN crosswalk (3,523 hospitals, 2,385 EINs), bundled from Community Benefit Insight.
- **`analytics`** — composed queries. `community_benefit_gap()` is the cross-form charity-care primitive.
- **`sdoh`** — CDC Social Vulnerability Index 2022 county-level (public domain, ships in the public bundles) and UW Area Deprivation Index county aggregation (local-only — UW's terms are non-sublicensable).

**FDA drug approvals:**

- **`fda_sba`** — scrapes FDA's novel-approval sources across CDER and CBER; extracts application number, drug name, active ingredient, approval date, sponsor, indication, `regulatory_center`, and links to the label, approval letter and review package. Covers 2021–2025 (268 drugs: 238 CDER + 30 CBER). Also parses FDA's NME compilation workbook (1985–2025) and joins its review designations onto the index.

**Site:** static HTML on Vercel at troveproject.com. See [`web/README.md`](web/README.md).

## Rebuild from raw sources

Everything published here is reproducible from primary sources. The hospital build needs the CMS HCRIS ZIPs for fiscal years 2022 and 2023 (about 130 MB each, kept under `data/raw/`) and reads the IRS e-file ZIPs of the 2023–2026 releases, about 17 GB in total. The IRS ZIPs are downloaded and parsed one at a time and deleted after parsing, so the build never holds all of them at once; the first run is long.

```bash
git clone https://github.com/cbetz/trove
cd trove && uv sync --all-packages

# /hospitals, in this order; each reads the previous one's output.
# The first run downloads the CMS files and scans the IRS ZIPs; later runs use the caches.
uv run python scripts/build_gap_dataset.py   # artifacts CSV + sources JSON (source of truth)
uv run python scripts/build_gap_index.py     # ranked index + summary (MD) and index JSON
uv run python scripts/build_web_data.py      # site lookup JSON
uv run python scripts/build_web_bundles.py   # published Parquet files + CSV copy

# Optional flags
uv run python scripts/build_gap_dataset.py --refresh-hcris   # re-download the CMS files
uv run python scripts/build_gap_dataset.py --refresh-990     # re-ingest every IRS ZIP (~17 GB)
uv run python scripts/build_gap_index.py --inject-chart      # also rewrite the chart in the site pages

# /drugs
uv run python scripts/build_fda_index.py     # per-drug index + FDA's NME compilation as CSV/Parquet
uv run python scripts/build_drug_pages.py    # per-drug, per-year, statistics and compilation pages (HTML + Markdown) AND the /drugs/ entries in web/sitemap.xml
```

CDC SVI and the UW ADI file (if you have your own license) are read from `data/raw/svi/` and `data/raw/adi/`. ADI never enters the public bundles — see the license note below.

## Dev setup

```bash
uv sync --all-packages
uv run pytest
uv run ruff check
uv run ruff format --check
```

## Layout

```
packages/         Python libraries (hcris, form990, crosswalk, analytics, sdoh, fda_sba)
skills/           Claude skill bundles
web/              Static site at troveproject.com
artifacts/        Committable, GitHub-viewable result tables
scripts/          Build + demo scripts
pipelines/        ETL orchestration — TBD
notebooks/        Exploratory work, not shipped
docs/             mkdocs-material site
```

Per-package detail in `packages/*/README.md`. Release history in [`CHANGELOG.md`](CHANGELOG.md).

## Corrections

If a number here looks wrong, it might be: the join spans two federal systems with different fiscal calendars and reporting units. Open a [data question](https://github.com/cbetz/trove/issues/new?template=data-question.yml) with the hospital and the figure, and it gets checked against the source filing. Methodology disagreements are welcome too, as a [methodology issue](https://github.com/cbetz/trove/issues/new?template=methodology.yml) — better in public than in my inbox. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

Two things to check first: that `period_aligned` is true for the row (otherwise the two figures cover different years), and whether the line is empty (a missing S-10 line 23 is published as empty, not `0`).

Built by [Chris Betz](https://cbetz.com) on personal time. Not affiliated with my employer; opinions my own. Not medical, legal, or financial advice.

## License and citations

trove code is **MIT-licensed**. Underlying data sources have their own licensing and citation requirements:

- **CMS HCRIS** — US government work, public domain. No citation required; suggested phrasing: "CMS Healthcare Cost Report Information System (HCRIS), Hospital form 2552-10".
- **IRS Form 990 e-file** — US government work, public domain. Suggested: "IRS Tax-Exempt Organization Form 990 e-file (Schedule H)".
- **CCN ↔ EIN crosswalk** — derived from Community Benefit Insight (RTI International, funded by RWJF, frozen Dec 6 2024). Suggested: "Community Benefit Insight; RTI Press 10.3768/rtipress.2023.op.0080.2302".
- **CDC Social Vulnerability Index** — county-level 2022 release, US government work / public domain. Included in the public bundles as `svi_overall_pct` plus four sub-theme columns. Source: https://www.atsdr.cdc.gov/place-health/php/svi/index.html.
- **Area Deprivation Index** — UW's Neighborhood Atlas terms are non-sublicensable and forbid redistribution of the data, derived or otherwise, outside individual-and-employer "internal non-profit educational, research, and public health" use. trove **does not include ADI** in the public bundles for this reason. The `sdoh` package supports local pipelines: download the block-group CSV from `https://www.neighborhoodatlas.medicine.wisc.edu/` (registration required) and the matched hospital dataset built locally will include county-aggregated ADI columns. Required citation when you use that local output anywhere: **Kind AJH, Buckingham W. Making Neighborhood Disadvantage Metrics Accessible: The Neighborhood Atlas. *N Engl J Med* 2018;378:2456-2458; PMCID: PMC6051533. AND: University of Wisconsin School of Medicine and Public Health. {year} Area Deprivation Index {version}. Downloaded from https://www.neighborhoodatlas.medicine.wisc.edu/ {date}.**

To cite trove itself, see [`CITATION.cff`](CITATION.cff) or GitHub's "Cite this repository" button.
