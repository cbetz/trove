# artifacts

Result tables, committed so they're viewable and diffable on GitHub without cloning or
running anything. All of these are **generated** — see the regeneration commands in each
row. Don't hand-edit them.

| File | What it is |
|---|---|
| [`charity_care_gap_index_2022.md`](charity_care_gap_index_2022.md) | **Start here.** The Charity Care Gap Index — the 99 hospitals where charity care reported to CMS and to the IRS is genuinely comparable, ranked by the size of the difference, with a ProPublica link to each 990. `scripts/build_gap_index.py` |
| [`community_benefit_gap_2022.csv`](community_benefit_gap_2022.csv) | The full matched dataset: 1,334 hospital systems (1,295 computable), HCRIS Worksheet S-10 joined to IRS 990 Schedule H at the EIN level. Sorted alphabetically, not by difference — it's a lookup table, not a ranking. `scripts/build_gap_dataset.py` |
| [`community_benefit_gap_2022_summary.md`](community_benefit_gap_2022_summary.md) | Method, the 1,334 → 1,295 → 372 → 99 funnel, validation spot-checks against IRS source XML, and every caveat — most importantly the fiscal-period alignment problem. Read this before quoting any number. |
| [`fda_approvals_nme_recent.csv`](fda_approvals_nme_recent.csv) | FDA novel drug approvals 2021–2024, 218 rows across CDER (NMEs and novel BLAs) and CBER (cell and gene therapy), each with a link to its approval package. `scripts/build_fda_index.py` |

## The one caveat that matters most

HCRIS names its files by CMS *reporting cycle*, not by the period a report covers. The
file labeled FY2023 holds whatever each hospital filed during that cycle, so for a
July–June filer it contains the report ending June 2024 — twelve months later than the
TY2022 990. **64% of matched systems are 12 months apart.** Before comparing two dollar
figures for a hospital, check `hcris_fy_end_dt` against `sched_h_tax_period_end`. The
Gap Index already does this; the full CSV deliberately does not filter, so you can see
what was excluded.

## Preferring these over the bundles

These files are for reading. For querying, the same data is served as Parquet over HTTPS
and DuckDB reads it without a download — see the [root README](../README.md).
