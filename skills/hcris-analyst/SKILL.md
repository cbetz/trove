---
name: hcris-analyst
description: Answer questions about U.S. nonprofit hospital financials, beds, staffing, charity care, and community benefit by querying CMS Medicare Cost Reports (HCRIS) and IRS Form 990 Schedule H filings. Use when the user asks about a specific hospital's cost-report numbers, peer comparisons across hospitals, the meaning of a worksheet/line/column code, the gap between CMS and IRS charity-care reporting, or any analytical question over the trove project's published HCRIS+990 data bundles.
---

# hcris-analyst

A skill for analyzing U.S. nonprofit hospital financials. Powered by the [trove project](https://github.com/cbetz/trove)'s parsed HCRIS Hospital 2552-10 data and IRS 990 Schedule H filings, published as Parquet bundles at troveproject.com.

## When to use this skill

Invoke when the user asks about:

- **A specific hospital's profile** — beds, revenue, charity care, ownership, etc. Identifiers are CCN (HCRIS, 6-char) or EIN (IRS, 9-char) or hospital name.
- **Peer comparisons** — how does X stack up against similar hospitals.
- **Field-glossary lookups** — what does Worksheet S-X line Y column Z mean.
- **Community benefit gap** — the difference between what a hospital reports as charity care to CMS (Worksheet S-10) and what it reports as financial assistance on IRS Schedule H Part I line 7a.
- **Top-N rankings** — largest by some metric, most uncompensated care, etc.
- **Schedule H amendments** — has a particular EIN been amended across IRS release years.
- **NL → DuckDB SQL** — translate ad-hoc questions into queries over the bundles.

## Don't use this skill for

- Questions about hospitals not in the U.S. (HCRIS is CMS / Medicare-specific).
- For-profit and government hospitals that don't file 990s — they're in HCRIS but not in the gap dataset. The skill can answer HCRIS-only questions about them.
- Patient-level outcomes, quality metrics, or readmission rates — those live in CMS Care Compare / Hospital Compare, not HCRIS. Tell the user the data source they want is elsewhere.
- Drug-approval questions — that's the FDA SBA dataset, planned as a Phase 2 trove package, not yet shipped.

## How to query

The data lives as Parquet bundles served over HTTPS from troveproject.com. DuckDB can query them directly. Two execution paths:

1. **Bash + DuckDB CLI:** `duckdb -c "SELECT ... FROM read_parquet('https://troveproject.com/data/...')"`
2. **Python:** `import duckdb; duckdb.sql("...").df()`

Both work in any environment with bash / Python and DuckDB available. If the user has the [`trove` repo](https://github.com/cbetz/trove) cloned and `uv sync --all-packages` has been run, the Python packages are also importable directly (`from hcris import pivot_wide`, etc.) — that's faster for repeated queries but not required.

**Reference docs (read these before answering):**

- [`references/parquet_layout.md`](references/parquet_layout.md) — bundle URLs, schemas, common query patterns.
- [`references/dictionary.md`](references/dictionary.md) — every HCRIS variable the bundles expose, with worksheet/line/column source.
- [`references/schedule_h.md`](references/schedule_h.md) — IRS 990 Schedule H field map.
- [`references/cohorts.md`](references/cohorts.md) — peer cohort dimensions and useful canned cohorts.
- [`references/examples.md`](references/examples.md) — runnable example queries that pattern-match the most common question types.

## How to answer well

1. **Read the reference docs before writing SQL.** The variable names are not always intuitive — e.g. `charity_care_cost` is HCRIS Worksheet S-10 line 23 column 3, *not* the gross charges line 22 column 1. Always look up the right column.
2. **Quote raw numbers from the data, not from memory.** Don't repeat headline numbers from web pages, news articles, or training data; run the query and quote the result.
3. **Disambiguate hospital names.** "Memorial Hermann" matches a dozen rows in HCRIS. If a name search has multiple results, surface the candidates (CCN, beds, location, revenue) and ask which one.
4. **Be explicit about period alignment when crossing HCRIS and 990s.** HCRIS labels its bulk files by federal-fiscal-year reporting cycle, not period covered — for many hospitals, "FY2023" data is 12 months later than the matching TY2022 990. The default in cross-form analyses should be to filter to systems where `|hcris_fy_end_dt - sched_h_tax_period_end| ≤ 1 month`. ~28% of EIN-matched systems pass this filter; the rest are misaligned and should not be treated as direct comparisons.
5. **Be cautious about the gap as evidence of misconduct.** A nonzero `charity_gap` has many legitimate explanations (definitional differences in what each form requires; cost-to-charge ratio handling; charity vs. bad debt classification; non-Medicare patient mix). Surface the gap with its caveats — it's a starting point for review, not an accusation.
6. **Children's hospitals, specialty cancer centers, and major non-Medicare-volume teaching hospitals** legitimately report near-zero charity care on HCRIS S-10 while reporting substantial financial assistance on Schedule H 7a. If a top-of-list result has this profile, name the structural reason.
7. **Cite the source.** When you give a number, include the column name and the bundle it came from so the user can verify (e.g. *"FY2023 HCRIS Worksheet S-10 charity-care cost from `hcris_2023_wide.parquet`"*).

## Coverage and time window

- **HCRIS:** Hospital 2552-10 only. Fiscal Year 2023 (CMS reporting cycle). Other forms (SNF, HHA, hospice, etc.) are not yet ingested.
- **IRS 990 Schedule H:** Tax Year 2022, ingested across IRS release-year ZIPs 2024, 2025, and 2026. Late filers and amendments are included.
- **CCN ↔ EIN crosswalk:** Community Benefit Insight, December 2024 vintage. ~3,500 hospital facilities, ~2,400 unique parent EINs. ~50% of HCRIS hospitals (mostly for-profit and government) don't appear in the crosswalk and so have no 990 to compare against.
- **Earlier years** (TY2018–TY2021 + matching HCRIS years) are planned for v2 — not available now. If the user asks for trends, say so.

## Sources and citations

When you produce output that quotes data values, cite the source bundle.

- **HCRIS** — CMS Healthcare Cost Report Information System, Hospital form 2552-10. Public domain.
- **IRS 990 Schedule H** — IRS Tax-Exempt Organization Form 990 e-file. Public domain.
- **CCN ↔ EIN crosswalk** — Community Benefit Insight (RTI International / RWJF), Dec 2024 vintage. Cite: RTI Press DOI 10.3768/rtipress.2023.op.0080.2302.

The public bundles do **not** include Area Deprivation Index (ADI) — UW's Neighborhood Atlas terms are non-sublicensable, so derived ADI columns can't be redistributed via troveproject.com. Users who download the trove repo and the ADI block-group data themselves (with a UW account) get ADI in their *local* gap parquet via `packages/sdoh/`, but the public skill can't query it. SDOH context for the public skill is on the v2 roadmap, likely via CDC's Social Vulnerability Index (which is fully open).

## Skill version

v1, May 2026. Bug reports and questions: github.com/cbetz/trove/issues.
