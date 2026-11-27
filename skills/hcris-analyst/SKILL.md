---
name: hcris-analyst
description: Answer questions about U.S. nonprofit hospital financials, beds, charity care, and community benefit by querying CMS Medicare Cost Reports (HCRIS) and IRS Form 990 Schedule H filings. Use when the user asks about a specific hospital's cost-report numbers, wants a hospital's IRS financial-assistance figure and CMS charity-care figure side by side with the components behind the difference, asks what a worksheet/line/column code means, wants peer context across hospitals, or has any analytical question over the trove project's published HCRIS and Schedule H data bundles.
---

# hcris-analyst

A skill for looking up what U.S. nonprofit hospitals report on two public filings: the CMS Medicare cost report (HCRIS, form 2552-10) and IRS Form 990 Schedule H. The data comes from the [trove project](https://github.com/cbetz/trove), published as Parquet and JSON bundles at `https://troveproject.com/data/`.

## When to use this skill

- **One hospital, two figures.** IRS Schedule H Part I line 7a and CMS Worksheet S-10 line 23 for a hospital, side by side, with the components each filing publishes. Identify the hospital by name, EIN (9 characters, text) or CCN (6 characters, text).
- **"What is in the difference?"** Walk through the components for one hospital. See [`references/reading_a_difference.md`](references/reading_a_difference.md).
- **The ranked index.** Questions about the 493-hospital index on troveproject.com/hospitals/ (by state, by size of difference, by which components are present).
- **A hospital's cost-report profile.** Beds, discharges, revenue, expenses, charity care, bad debt, uncompensated care, ownership code.
- **Field glossary.** What a worksheet/line/column or a Schedule H line means.
- **Peer context and descriptive top-N queries**, when the user asks for them.
- **Schedule H filings per EIN.** Which returns exist for tax year 2022, which is amended, which release it came from.

## Don't use this skill for

- **Staffing, FTEs, wages, teaching status, quality, outcomes or readmissions.** None of these are in the bundles. Say so and name where they live (cost report Worksheet S-3 Parts II–V for wage and FTE data; CMS Care Compare for quality).
- **Trends.** The bundles hold tax year 2022 Schedule H and the two CMS fiscal-year files that overlap it. There is no earlier or later year.
- **For-profit and government hospitals' IRS figure.** They file cost reports (so they are in the HCRIS bundles) but no Form 990 Schedule H, so they are not in the matched table.
- **Drug approvals.** Hand those to the sibling `fda-analyst` skill in the same plugin.

## The framing, which is binding for every answer

The matched table puts two public figures next to each other. It does not compare two measurements of one thing.

- **IRS Form 990, Schedule H, Part I, line 7a** reports financial assistance at cost: column (c) total expense, column (d) direct offsetting revenue, column (e) net, which is (c) − (d).
- **CMS cost report (form 2552-10), Worksheet S-10, line 23, column 3** is the cost of charity care after patient payments: uninsured patients (column 1) plus insured patients (column 2).

The two lines are defined differently, so they can differ when both are filed correctly:

- The Schedule H instructions (Worksheet 1) let a filer include Medicaid or provider taxes in the line 7a cost when payments from its state's uncompensated care pool or DSH program are intended primarily to offset the cost of financial assistance, with that pool revenue reported as offsetting revenue in column (d). Otherwise those amounts belong on line 7b. This is a classification the instructions permit, and it depends on the state.
- The cost report keeps Medicaid DSH and supplemental payments, "net of associated provider taxes or assessments", on S-10 line 5. Line 5 is not part of line 23.
- S-10 column 2 counts deductibles and coinsurance written off for insured patients.
- Schedule H asks for the filer's most accurate costing method; S-10 derives cost from charges with the worksheet's own cost-to-charge ratio.
- A 990 is filed per legal entity (EIN); a cost report per provider (CCN).

Rules that follow:

1. **Neutral verbs only.** "Reports", "shows", "the filing lists". Never say or imply that a hospital misreported, inflated, hid or double-counted anything, or that either figure is wrong. Do not call the two lines "the same thing", "net-to-net" or "apples to apples".
2. **A reconciliation is yours, not the hospital's.** When components appear to account for a difference, say it is a reconciliation from the two filings. The worksheet behind the IRS line is not public, and no filing says what its offsetting revenue or its line 5 consists of.
3. **When nothing in the two filings accounts for a difference, say that**, and pose it as a question (what is in one figure that is not in the other?), not as a finding about the hospital.
4. **Missing is not zero.** A null `hcris_charity_care_cost` or a null line 7a means the form has no value on that line. Say "not reported on this line". Never print $0 for a null, never compute a difference from one, and never describe it as "near zero". `hcris_s10_filed` tells you whether the cost report has a Worksheet S-10 at all.
5. **Check `period_aligned` before quoting a difference.** If it is false, the two filings cover different fiscal periods; say so and do not present the difference as like-for-like.
6. **Multi-hospital systems.** One EIN can cover several CCNs (`ccn_count` > 1). The CMS figure is then a sum across cost reports. If any CCN lacks line 23, the system total is null and only a labelled partial (`hcris_charity_care_cost_reporting_ccns`) exists. Multi-CCN rows are in the matched table but not in the ranked index.

## How to query

DuckDB over HTTPS is the default path. Bundles are at `https://troveproject.com/data/`:

```bash
duckdb -c "SELECT hospital_name, sched_h_financial_assistance_at_cost, hcris_charity_care_cost, charity_gap, period_aligned
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE ein = '060646652'"
```

If `duckdb` is not installed, `uv run --with duckdb python` or `pip install duckdb` gives the same engine in Python. If neither is possible, use the JSON bundles with `curl` and the Python standard library (recipe in `parquet_layout.md`).

**If the site cannot be reached** (some sandboxes, including claude.ai and Cowork code execution, block outbound requests to domains that are not on an allow-list), get the same files from the repository and query them by local path:

```bash
git clone --depth 1 https://github.com/cbetz/trove
# then use trove/web/data/<file> in place of https://troveproject.com/data/<file>
```

If both are blocked, tell the user the sandbox cannot reach the data and that they can either allow `troveproject.com` or upload the file. Do not answer from memory.

**Check the bundle version before the first cross-form answer.** Plugin 1.2.0 expects the November 2026 build of the data. An older cached or not-yet-updated bundle lacks the columns this skill relies on and publishes a missing S-10 figure as 0. Run this once:

```sql
SELECT COUNT(*) AS has_new_columns
FROM (DESCRIBE SELECT * FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet'))
WHERE column_name IN ('period_aligned', 'hcris_medicaid_dsh_supplemental', 'sched_h_financial_assistance_gross');
```

It should return 3. If it returns 0, say plainly: "The data file I reached is an older build. It does not have the component columns, and it shows a missing S-10 line as $0, so I can't give a reliable side-by-side from it." Then use the repository clone instead, or stop.

## Reference docs (read before answering)

- [`references/parquet_layout.md`](references/parquet_layout.md): every bundle, its schema, the JSON shapes, the index definition, fetch fallbacks.
- [`references/reading_a_difference.md`](references/reading_a_difference.md): how to walk a user through one hospital's two figures, with the worked example and the filing links.
- [`references/schedule_h.md`](references/schedule_h.md): the Schedule H columns and which return is used per EIN.
- [`references/dictionary.md`](references/dictionary.md): every HCRIS variable in the wide bundles with its worksheet, line and column.
- [`references/cohorts.md`](references/cohorts.md): peer cohort dimensions that the bundles can and cannot support.
- [`references/examples.md`](references/examples.md): tested queries for the common question types.

## How to answer well

1. **Run the query; quote the result.** Do not repeat numbers from this file, from web pages or from memory. The counts and dollar figures in these docs were read from the November 2026 build and will change when the data is rebuilt.
2. **Read EIN, CCN and object ids as text.** They have leading zeros.
3. **Disambiguate names.** Names come from the cost report and are often truncated or abbreviated ("ST JUDE", "NEW YORK PRESBYTERIAN"). Search both `hospital_name` and `sched_h_organization_name`, strip punctuation, and if several rows match show the candidates (name, city, state, EIN, CCN) and ask.
4. **State the period and the status.** Give both fiscal periods, whether they are aligned, the cost report's status (`as_submitted`, `settled_without_audit`, `settled_with_audit`, `reopened`, `amended`) and whether the 990 is an amended return. Figures on an as-submitted report can change in later CMS files.
5. **Cite the source of each number**: the form, line and column, plus the bundle column (for example "CMS Worksheet S-10 line 23 column 3, `hcris_charity_care_cost` in `community_benefit_gap_2022.parquet`"). Offer the links to both filings (patterns in `reading_a_difference.md`).
6. **Pick the right HCRIS file.** `hcris_2022_wide.parquet` and `hcris_2023_wide.parquet` are CMS's fiscal-year files, keyed on the date the reporting period begins. A hospital usually has a report in each, for different periods. For anything tied to the tax year 2022 Form 990, use the matched table, which already selected the report whose period ends closest to the 990's.

## Coverage

- **CMS:** HCRIS Hospital 2552-10, fiscal year 2022 and 2023 files (periods beginning 2021-10-01 through 2023-09-30). Other provider types are not ingested.
- **IRS:** Form 990 Schedule H, tax year 2022, from e-file releases 2023 through 2026.
- **Crosswalk:** CCN to EIN from Community Benefit Insight, December 2024. For-profit and government hospitals are not in it.
- **Matched table:** one row per EIN. The exact counts (matched, with both figures, period-aligned, in the index) are in the `counts` object of `charity_care_gap_index_2022.json`; read them from there.
- **Home-county context:** CDC/ATSDR Social Vulnerability Index 2022 percentiles for the hospital's home county. A proxy, not a service-area measure. Area Deprivation Index is not in the public bundles (its license does not allow redistribution).

## Sources to cite

- **CMS Healthcare Cost Report Information System (HCRIS)**, Hospital form 2552-10. Public domain.
- **IRS Form 990 e-file**, Schedule H. Public domain.
- **CCN to EIN crosswalk**: Community Benefit Insight (RTI International / RWJF), December 2024. RTI Press DOI 10.3768/rtipress.2023.op.0080.2302.
- **CDC/ATSDR Social Vulnerability Index 2022.** Public domain. https://www.atsdr.cdc.gov/place-health/php/svi/index.html

## Skill version

Shipped in trove plugin 1.2.0 (November 2026). Corrections and questions: https://github.com/cbetz/trove/issues
