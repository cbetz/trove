# trove

**Yale New Haven Hospital reported $113.1M in financial assistance to the IRS and $35.6M in charity care to CMS — for the same fiscal year, on a comparable ~$4.1 billion expense base.**

Every nonprofit U.S. hospital reports the cost of the care it gave patients who couldn't pay to two federal regulators: to the IRS on Form 990 Schedule H (Part I, line 7a) and to CMS on Worksheet S-10 of the Medicare Cost Report. Both fiscal periods ended 2023-09-30; the two filings' total expenses agree within 5%. You can check it yourself: [Yale's 990 on ProPublica](https://projects.propublica.org/nonprofits/organizations/60646652) · [the method](artifacts/charity_care_gap_index_2022.md).

Of 1,295 nonprofit hospital systems, **99 clear an apples-to-apples bar** — single reporting facility, filing periods ending within one month of each other, both figures at least $1M, and total expenses within 5%. **22 of those 99 differ by more than 50%.**

> **A gap is not an accusation.** The two forms have genuinely different definitions, cost-to-charge handling, and category boundaries, and a difference can be entirely legitimate. That the two figures diverge is a long-documented measurement inconsistency, not a novel discovery — the GAO has noted there is no standard federal definition of uncompensated care ([GAO-16-568](https://www.gao.gov/products/gao-16-568)) and separately scrutinized Schedule H reporting ([GAO-20-679](https://www.gao.gov/products/gao-20-679)); CRS laid out the differing definitions (2018); researchers have compared the two sources (Zare et al., *Health Services Research*, 2022). What hasn't existed is a fast way to check it for a **specific hospital**, with links to both filings. That's what this is.

**[Read the write-up →](https://troveproject.com/notes/charity-care-gap/)** · **[Look up any hospital →](https://troveproject.com/hospitals/)**

## Query it in one line

The published bundles are Parquet over HTTPS, so DuckDB reads them with no download and no API key:

```sql
INSTALL httpfs; LOAD httpfs;

SELECT hospital_name,
       sched_h_financial_assistance_at_cost AS told_irs,
       hcris_charity_care_cost              AS told_cms,
       sched_h_tax_period_end, hcris_fy_end_dt
FROM 'https://troveproject.com/data/community_benefit_gap_2022.parquet'
WHERE sched_h_organization_name ILIKE '%<YOUR HOSPITAL>%';
```

Compare the two period-end columns before comparing the two dollar figures — 64% of matched systems are 12 months apart, and a difference across different years means nothing. Three bundles are served:

| URL | What's in it |
|---|---|
| [`community_benefit_gap_2022.parquet`](https://troveproject.com/data/community_benefit_gap_2022.parquet) | The matched dataset — HCRIS S-10 summed per EIN, joined to Schedule H 7a (1,334 × 20) |
| [`hcris_2023_wide.parquet`](https://troveproject.com/data/hcris_2023_wide.parquet) | HCRIS Hospital 2552-10 FY2023, pivoted wide, 48 named variables (~6,100 rows) |
| [`schedule_h_2022.parquet`](https://troveproject.com/data/schedule_h_2022.parquet) | IRS 990 Schedule H filings, TY2022 (~1,500 × 23) |

Or skip SQL: the [`hcris-analyst`](https://troveproject.com/skills/hcris-analyst/) Claude Code skill answers the same questions in plain English.

## Look it up

- **[troveproject.com/hospitals/](https://troveproject.com/hospitals/)** — the ranked index, plus a lookup of 1,295 nonprofit hospital systems with both filings side-by-side and a link to each 990
- **[troveproject.com/drugs/](https://troveproject.com/drugs/)** — 218 FDA novel drug approvals, 2021–2024 (CDER NMEs + CBER cell &amp; gene therapies); click any record for its full approval package
- **[troveproject.com/skills/](https://troveproject.com/skills/)** — install the trove Claude Code plugin (`fda-analyst` + `hcris-analyst`)
- **[troveproject.com/docs/](https://troveproject.com/docs/)** — plain-language explainers: [what is HCRIS](https://troveproject.com/docs/hcris/), [what is IRS 990 Schedule H](https://troveproject.com/docs/schedule-h/), [what is an FDA novel drug approval](https://troveproject.com/docs/fda-nme/)
- **[troveproject.com/notes/](https://troveproject.com/notes/)** — findings written from the published tables

## What this is

Open-source parsers, Parquet/JSON bundles, and Claude Code skills for public-domain healthcare datasets that are widely cited but rarely usable in raw form. CMS publishes 100,000-row headerless long-skinny CSVs. The IRS publishes 990s as XML inside bulk ZIPs. The FDA scatters approval reviews across hundreds of PDF directories. trove does the parsing, joining, and packaging so the data is browsable and queryable. MIT-licensed; the data underneath is public domain.

Two areas live today:

### [/hospitals](https://troveproject.com/hospitals/) — hospital reporting (CMS + IRS)

Charity-care reporting that nonprofit hospitals file with two different regulators, side by side. Both lines are meant to capture the cost of caring for patients who couldn't pay, but the rules and scope diverge enough that the two numbers can legitimately differ.

For tax year 2022 the funnel is: **1,334 systems matched** at the EIN level → **1,295 computable** (both figures present) → **372 period-aligned within 1 month** → **99 that also clear the single-facility, materiality, and same-expense-base tests**. Each row carries filing-period context, a home-county Social Vulnerability Index proxy, and a deep link to the actual 990 on ProPublica.

Ranked index: [`artifacts/charity_care_gap_index_2022.md`](artifacts/charity_care_gap_index_2022.md) · Full data: [`artifacts/community_benefit_gap_2022.csv`](artifacts/community_benefit_gap_2022.csv) · Method and every caveat: [`artifacts/community_benefit_gap_2022_summary.md`](artifacts/community_benefit_gap_2022_summary.md).

**The comparison is net-to-net.** The IRS figure is Schedule H Part I line 7a column (e) — net community benefit expense for financial assistance. The CMS figure is S-10 cost of charity care, net of partial patient payments. The two "net" definitions still aren't identical, so a residual difference is expected even for a hospital reporting both correctly.

### [/drugs](https://troveproject.com/drugs/) — FDA drug approvals

Every FDA novel drug approval from 2021–2024 (218 drugs) across both regulatory centers: **CDER** (192 NMEs and novel antibody BLAs from the annual *Novel Drug Approvals* lists) plus **CBER** (26 cell and gene therapy approvals — Lenmeldy, Casgevy, Lyfgenia, Beqvez, Hemgenix, Roctavian, Adstiladrin, and others). Each row carries application number, sponsor, approval date, indication, a `regulatory_center` column, and a deep link to the approval-package documents — medical, statistical, pharmacology, and chemistry reviews. The `fda-analyst` skill reads those PDFs at query time.

Sources: FDA's annual *Novel Drug Approvals* lists (CDER); *Approved Cellular and Gene Therapy Products* page (CBER); drugs@FDA. US government work, public domain.

## Install the skills

trove is packaged as a Claude Code plugin (`.claude-plugin/plugin.json`) containing both skills.

**Plugin install** — Anthropic's community marketplace:

```
/plugin marketplace add anthropics/claude-plugins-community
/plugin install trove@claude-community
```

That's the public community marketplace, not the separate official `claude-plugins-official` one.

**Filesystem install:**

```bash
git clone https://github.com/cbetz/trove
cp -r trove/skills/hcris-analyst ~/.claude/skills/
cp -r trove/skills/fda-analyst  ~/.claude/skills/
```

Either way, restart Claude Code and both are loaded. Each skill's `description` tells Claude when to invoke it — you don't call them by name.

- `skills/hcris-analyst/` — natural-language queries over hospital reporting (HCRIS S-10 + IRS 990 Schedule H + CCN↔EIN crosswalk + CDC SVI). Profile lookups, peer context, glossary, cross-form difference context.
- `skills/fda-analyst/` — questions about specific FDA approvals; reads approval-package PDFs at query time.

For per-project install, Claude.ai upload, or authoring a new skill, see [`skills/README.md`](skills/README.md).

## What's in the box

**Hospital reporting:**

- **`hcris`** — CMS Medicare Cost Reports (form 2552-10) parser with a 44-variable semantic dictionary. Turns headerless long-skinny CSVs into tidy DataFrames and partitioned Parquet.
- **`form990`** — IRS Form 990 Schedule H parser. Bulk-XML download, index reader, 19 fields per filing including Part I 7a–k community benefit amounts and Part III bad debt. Handles the DEFLATE64 ZIPs the IRS introduced in 2025.
- **`crosswalk`** — CCN ↔ EIN crosswalk (3,523 hospitals, 2,385 EINs), bundled from Community Benefit Insight.
- **`analytics`** — composed queries. `community_benefit_gap()` is the cross-form charity-care primitive.
- **`sdoh`** — CDC Social Vulnerability Index 2022 county-level (public domain, ships in the public bundles) and UW Area Deprivation Index county aggregation (local-only — UW's terms are non-sublicensable).

**FDA drug approvals:**

- **`fda_sba`** — scrapes FDA's novel-approval sources across CDER and CBER; extracts application number, drug name, active ingredient, approval date, sponsor, indication, `regulatory_center`, and links to the approval-package PDFs. Covers 2021–2024 (218 drugs: 192 CDER + 26 CBER).

**Site:** static HTML on Vercel at troveproject.com. See [`web/README.md`](web/README.md).

## Rebuild from raw sources

Everything published here is reproducible from primary sources. The downloads total roughly 8.4 GB — mostly the IRS bulk-XML ZIPs — and are automatic apart from the two calls noted below.

```bash
git clone https://github.com/cbetz/trove
cd trove && uv sync --all-packages

# One-time raw downloads (~8.4 GB, cached under data/raw/, gitignored)
uv run python -c "import hcris; hcris.download_year(2023)"
# IRS Schedule H ZIPs are fetched by build_gap_dataset.py on first run,
# or explicitly: form990.download_zip(tax_year=2022, release_year=2024)

# /hospitals — in this order; each reads the previous one's output
uv run python scripts/build_gap_dataset.py   # artifacts CSV + parquet (source of truth)
uv run python scripts/build_gap_index.py     # the ranked index (MD + JSON)
uv run python scripts/build_web_data.py      # site search JSON
uv run python scripts/build_web_bundles.py   # published Parquet bundles + CSV copy

# /drugs
uv run python scripts/build_fda_index.py
uv run python scripts/build_drug_pages.py    # per-drug pages AND web/sitemap.xml
```

CDC SVI and the UW ADI file (if you have your own license) are read from `data/raw/svi/` and `data/raw/adi/`. ADI never enters the public bundles — see the license note below.

## Dev setup

```bash
uv sync --all-packages
uv run pytest        # 116 tests
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

If a number here looks wrong, it might be — the underlying filings are self-reported and the join spans two federal systems with different fiscal calendars. Open a [data question](https://github.com/cbetz/trove/issues/new?template=data-question.yml) with the hospital and the figure, and it gets checked against the source filing. Methodology disagreements are welcome too, as a [methodology issue](https://github.com/cbetz/trove/issues/new?template=methodology.yml) — better in public than in my inbox. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

One thing to check first, because it explains most apparent errors: compare `hcris_fy_end_dt` against `sched_h_tax_period_end` before comparing two dollar figures.

Built by [Chris Betz](https://cbetz.com) on personal time. Not affiliated with my employer; opinions my own. Not medical, legal, or financial advice.

## License and citations

trove code is **MIT-licensed**. Underlying data sources have their own licensing and citation requirements:

- **CMS HCRIS** — US government work, public domain. No citation required; suggested phrasing: "CMS Healthcare Cost Report Information System (HCRIS), Hospital form 2552-10".
- **IRS Form 990 e-file** — US government work, public domain. Suggested: "IRS Tax-Exempt Organization Form 990 e-file (Schedule H)".
- **CCN ↔ EIN crosswalk** — derived from Community Benefit Insight (RTI International, funded by RWJF, frozen Dec 6 2024). Suggested: "Community Benefit Insight; RTI Press 10.3768/rtipress.2023.op.0080.2302".
- **CDC Social Vulnerability Index** — county-level 2022 release, US government work / public domain. Included in the public bundles as `svi_overall_pct` plus four sub-theme columns. Source: https://www.atsdr.cdc.gov/place-health/php/svi/index.html.
- **Area Deprivation Index** — UW's Neighborhood Atlas terms are non-sublicensable and forbid redistribution of the data, derived or otherwise, outside individual-and-employer "internal non-profit educational, research, and public health" use. trove **does not include ADI** in the public bundles for this reason. The `sdoh` package supports local pipelines: download the block-group CSV from `https://www.neighborhoodatlas.medicine.wisc.edu/` (registration required) and the matched hospital dataset built locally will include county-aggregated ADI columns. Required citation when you use that local output anywhere: **Kind AJH, Buckingham W. Making Neighborhood Disadvantage Metrics Accessible: The Neighborhood Atlas. *N Engl J Med* 2018;378:2456-2458; PMCID: PMC6051533. AND: University of Wisconsin School of Medicine and Public Health. {year} Area Deprivation Index {version}. Downloaded from https://www.neighborhoodatlas.medicine.wisc.edu/ {date}.**

To cite trove itself, see [`CITATION.cff`](CITATION.cff) or GitHub's "Cite this repository" button.
