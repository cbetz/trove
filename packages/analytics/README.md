# analytics

Composed queries over the `hcris`, `form990` and `crosswalk` outputs.

## `community_benefit_gap()`

Builds the matched table published as `community_benefit_gap_2022`: one row per EIN, with IRS Form 990 Schedule H Part I line 7a next to CMS cost report Worksheet S-10 line 23, the components each filing publishes, and the periods and flags needed to read them.

```python
import pandas as pd
from hcris import download_year, parse_zip, pivot_wide
from crosswalk import load_seed
from analytics import community_benefit_gap

# Stack the CMS fiscal-year files that can hold a tax year 2022 hospital's report.
parts = []
for fy in (2022, 2023):
    wide = pivot_wide(parse_zip(download_year(fy)))
    wide.insert(0, "hcris_file_fy", fy)
    parts.append(wide)
hcris_wide = pd.concat(parts, ignore_index=True)

sched_h = pd.read_parquet("web/data/schedule_h_2022.parquet")  # or form990.parse_tax_year(...)
gap = community_benefit_gap(hcris_wide, sched_h, load_seed())
```

The full build, including the IRS ingest and the SVI join, is `scripts/build_gap_dataset.py`.

## What the function does

- **One return per EIN.** `form990.latest_return_per_ein` picks it: a full-year return over a short-year one, then the latest period end, then the latest e-file timestamp (so an amended return is used over the original), then the newest release.
- **Period matching.** CMS groups cost reports into fiscal-year files by the date the reporting period begins, so a tax year 2022 return can pair with a report in the FY2022 or the FY2023 file. For each CCN, `select_period_matched_reports` takes the report whose period ends closest to the 990's period end. When a report before and a report after are equally close, the side is chosen once per EIN, so a system's facilities never take reports from different years; report status and processing date break what is left.
- **`period_aligned`** is true only when every CCN under the EIN has a report ending within `alignment_months` (default 1) of the 990's period end. `hcris_fy_bgn_dt` / `hcris_fy_end_dt` are the worst-matching CCN's dates and `hcris_months_from_990` its distance.
- **EIN-level sums.** A 990 is filed per EIN and a cost report per CCN. Cost report figures are summed across the EIN's CCNs. `ccn_count` counts CCNs with a cost report in the frame passed in; `crosswalk_ccn_count` counts the CCNs the crosswalk lists.
- **Missing stays missing.** CMS's numeric file stores no zeros, so an absent S-10 cell is not a reported $0. Sums use `min_count=1`. `hcris_charity_care_cost` (S-10 line 23 column 3) is stricter: it is missing when any CCN under the EIN lacks the line, with the partial sum in `hcris_charity_care_cost_reporting_ccns` and the number of CCNs without it in `hcris_ccns_missing_charity`. `charity_gap` and `charity_gap_gross` are missing whenever either side is. `hcris_s10_filed` says whether every CCN's report has a Worksheet S-10 at all.
- **Components.** Line 7a columns (c), (d), (e); line 7b; S-10 line 23 columns 1, 2, 3; lines 20 to 22; line 5 (Medicaid DSH and supplemental payments net of provider taxes); line 8; line 30. `sched_h_fa_7a_consistent` records whether (c) − (d) = (e) on the return.

The docstring of `community_benefit_gap` lists every output column.

## Reading the output

- `charity_gap` is S-10 line 23 column 3 minus line 7a column (e); `charity_gap_gross` uses column (c). The two lines are defined differently, so a difference does not by itself say anything about either filing. The Schedule H instructions (Worksheet 1) let a filer include provider taxes in line 7a cost under a stated condition, with pool revenue in column (d); the cost report nets those on S-10 line 5, which is not part of line 23; and the S-10 insured column counts deductibles and coinsurance written off.
- Filter on `period_aligned` before comparing the two figures.
- Rows with `ccn_count > 1` are system sums. The ranked index (`scripts/build_gap_index.py`) keeps only single-CCN, period-aligned rows with both figures at least $1M and total expenses within 5%.
- Coverage is limited to EINs that are in the crosswalk, have a tax year 2022 Schedule H, and have a cost report in the frame passed in.

## Tests

`uv run pytest packages/analytics` covers the period matching, the tie-break, missing-value handling, and checks on the published data files.
