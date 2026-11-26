# artifacts

Result tables, committed so they're viewable and diffable on GitHub without cloning or
running anything. All of these are **generated** — see the regeneration commands in each
row. Don't hand-edit them.

| File | What it is |
|---|---|
| [`charity_care_gap_index_2022.md`](charity_care_gap_index_2022.md) | **Start here.** The ranked index: the IRS Schedule H line 7a figure and the CMS Worksheet S-10 line 23 figure side by side for the 493 hospitals with a single cost report for the same fiscal period as the 990, ranked by the size of the difference, with the components each form reports and a link to each 990. `scripts/build_gap_index.py` |
| [`community_benefit_gap_2022.csv`](community_benefit_gap_2022.csv) | The full matched dataset: 2,099 hospital systems (1,904 with both figures present), HCRIS Worksheet S-10 joined to IRS 990 Schedule H at the EIN level, 51 columns. Sorted alphabetically, not by difference — it's a lookup table, not a ranking. `scripts/build_gap_dataset.py` |
| [`community_benefit_gap_2022_summary.md`](community_benefit_gap_2022_summary.md) | Method, the 2,099 → 1,904 → 1,797 → 493 funnel, the column list and every caveat. Read this before quoting any number. `scripts/build_gap_index.py` |
| [`community_benefit_gap_2022_sources.json`](community_benefit_gap_2022_sources.json) | What the source files say about their own vintage: CMS extract date, posted date, latest processing date and ZIP hashes, IRS returns by release year, crosswalk coverage. The summary quotes it instead of a hand-typed date. `scripts/build_gap_dataset.py` |
| [`fda_approvals_nme_recent.csv`](fda_approvals_nme_recent.csv) | FDA novel drug approvals 2021–2024, 217 rows across CDER (NMEs and novel BLAs) and CBER (cell and gene therapy), each with links to its label, approval letter and review package, plus the review designation and expedited-program flags FDA records in its NME compilation. `scripts/build_fda_index.py` |

## The caveats that matter most

- **A blank is not a zero.** CMS's numeric file never stores a zero, so a hospital with
  no Worksheet S-10 line 23 has an empty `hcris_charity_care_cost` and an empty
  `charity_gap`, never `0`.
- **Check the period.** Each cost report is matched to the 990's own fiscal period
  (CMS files a report under the federal fiscal year in which its period *begins*, so the
  FY2022 and FY2023 files are both used). `period_aligned` is True when every CCN under
  the EIN has a cost report ending within one calendar month of the 990's tax-period
  end. The ranked index requires it; the full CSV keeps the unaligned rows so you can see
  what was excluded.
- **`ccn_count` = 1 means one CCN with a cost report**, not that the crosswalk lists one
  facility. `crosswalk_ccn_count` is published beside it, and index rows where the two
  differ are marked.
- **A difference is not a finding about a hospital.** The two forms define the figure
  differently; the components are published so the difference can be read, not assumed.

## Preferring these over the bundles

These files are for reading. For querying, the same data is served as Parquet over HTTPS
and DuckDB reads it without a download — see the [root README](../README.md).
