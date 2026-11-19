# Data layout: the bundles at troveproject.com/data/

DuckDB reads Parquet and JSON over HTTPS. Treat each URL as a table. Row and column counts below are from the November 2026 build; run `SELECT COUNT(*)` if the exact number matters.

## Bundles

| File (under `https://troveproject.com/data/`) | What it is | Rows × columns |
|---|---|---|
| `community_benefit_gap_2022.parquet` | The matched table: one row per EIN, IRS Schedule H line 7a next to CMS S-10 line 23, with components, periods and flags. Start here for any cross-form question. | 2,099 × 51 |
| `community_benefit_gap_2022.csv` | The same table as CSV. Read `ein`, `ccn_list`, `sched_h_object_id` and `hcris_rpt_rec_num` as text. | 2,099 × 51 |
| `community_benefit_gap_2022.json` | The same systems, shaped for the website: `rows` (both figures present) and `rows_not_computable` (one figure missing), plus `totals`. | 1,904 + 195 |
| `charity_care_gap_index_2022.json` | The ranked index shown on troveproject.com/hospitals/: the single-facility, same-period, same-scale subset, with components, note codes, the filter definition, sources and counts. | 493 |
| `hcris_2022_wide.parquet` | CMS HCRIS Hospital 2552-10, fiscal year 2022 file, one row per cost report, one column per dictionary variable. | 6,069 × 61 |
| `hcris_2023_wide.parquet` | The fiscal year 2023 file, same schema. | 6,109 × 61 |
| `schedule_h_2022.parquet` | IRS Form 990 Schedule H, tax year 2022, one row per return found (not deduplicated; some EINs appear more than once). | 2,360 × 51 |

## Is this the current build?

The site may serve an older build for a while after a plugin update, and a cached copy can be older still. Before a cross-form answer, check for the newer columns:

```sql
SELECT COUNT(*) AS has_new_columns
FROM (DESCRIBE SELECT * FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet'))
WHERE column_name IN ('period_aligned', 'hcris_medicaid_dsh_supplemental', 'sched_h_financial_assistance_gross');
```

Expect 3. If it returns 0 you have the older build (20 columns, about 1,334 rows). In that build a missing S-10 line was published as `0`, there are no component columns, no `period_aligned`, no `state`, and `hcris_2022_wide.parquet` and `rows_not_computable` do not exist. Tell the user the file is an older build and that you cannot give a reliable side-by-side from it; then use a repository clone (below) or stop. Do not work around it by treating zeros as real.

## If the site is unreachable

1. **Download, then query locally.** `curl -fsSL -o gap.parquet https://troveproject.com/data/community_benefit_gap_2022.parquet`, then `read_parquet('gap.parquet')`. This also avoids DuckDB's `httpfs` extension, which some environments cannot install.
2. **Clone the repository.** The same files are in `web/data/`:

   ```bash
   git clone --depth 1 https://github.com/cbetz/trove
   duckdb -c "SELECT COUNT(*) FROM read_parquet('trove/web/data/community_benefit_gap_2022.parquet')"
   ```

3. **Neither works.** Some sandboxes (claude.ai and Cowork code execution among them) only reach allow-listed domains. Say that the sandbox cannot reach `troveproject.com` or `github.com`, and that the user can allow the domain or upload the file. Do not answer from memory.

## The two HCRIS files

CMS groups cost reports into fiscal-year files by the date the reporting period **begins**. The FY2022 file holds periods beginning 2021-10-01 through 2022-09-30; the FY2023 file holds periods beginning 2022-10-01 through 2023-09-30. So:

- a calendar-2022 report (begins 2022-01-01) is in `hcris_2022_wide.parquet`;
- a report for October 2022 to September 2023 is in `hcris_2023_wide.parquet`;
- most hospitals have one report in each file, for consecutive periods. Always show `fy_bgn_dt` and `fy_end_dt`, and do not assume "2023" in the file name means the year the user has in mind.

The two files have the same schema and can be stacked:

```sql
SELECT hcris_file_fy, prvdr_num, hospital_name, fy_bgn_dt, fy_end_dt, rpt_status, charity_care_cost
FROM (
  SELECT * FROM read_parquet('https://troveproject.com/data/hcris_2022_wide.parquet')
  UNION ALL BY NAME
  SELECT * FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
)
WHERE prvdr_num = '330101'
ORDER BY fy_bgn_dt;
```

Columns in both files:

| Column | Meaning |
|---|---|
| `hcris_file_fy` | Which CMS fiscal-year file the row came from (2022 or 2023). |
| `rpt_rec_num` | CMS report record number. Unique across the two files. |
| `prvdr_num` | CCN, 6 characters, text. |
| `fy_bgn_dt`, `fy_end_dt` | The cost reporting period. |
| `rpt_stus_cd`, `rpt_status` | Report status: 1 `as_submitted`, 2 `settled_without_audit`, 3 `settled_with_audit`, 4 `reopened`, 5 `amended`. |
| `proc_dt` | CMS processing date of the report. |
| `s10_filed` | True when the report has any Worksheet S-10 cell. False means no S-10 at all. |
| 52 dictionary variables | See `dictionary.md`. Includes `hospital_name`, `ownership_type`, `chain_name`, beds, discharges, revenue, expenses, and the S-10 lines. |

**Worksheet S-10 code change.** Cost reports for periods beginning before 2022-10-01 carry S-10 under worksheet code `S100000`; later periods carry S-10 Part I as `S100001`. The line and column numbers are the same, and the bundles already map both to the same variables. You do not need to handle it.

**No zeros.** CMS's numeric file does not store zero values. A null dollar value means the cell was blank or zero on the form; it is not a reported $0. `s10_filed` separates "no S-10" from "S-10 present, this line empty".

**Not in the wide bundles:** state, city, teaching or children's flags, FTEs or any staffing or wage data, critical-access or DSH designations. City and state for matched nonprofit hospitals are on the matched table.

## The matched table: `community_benefit_gap_2022.parquet`

One row per EIN that has a tax year 2022 Schedule H, a crosswalk entry and at least one cost report in the two CMS files.

**Identity**

| Column | Meaning |
|---|---|
| `ein` | IRS EIN, 9 characters, text. |
| `hospital_name`, `city`, `state` | Lead facility: the CCN with the largest operating expenses. Names are as written on the cost report. |
| `sched_h_organization_name` | Filer name on the 990. |
| `ccn_list` | The CCNs with a cost report, `;`-joined, lead facility first. |
| `ccn_count` | Number of CCNs with a cost report in the two files. Greater than 1 means a multi-hospital system. |
| `crosswalk_ccn_count` | Number of CCNs the crosswalk lists for the EIN. Can exceed `ccn_count` when a listed CCN has no cost report in the files used. |

**IRS Schedule H (the return used for this EIN)**

| Column | Form location |
|---|---|
| `sched_h_financial_assistance_gross` | Part I line 7a column (c), total expense |
| `sched_h_financial_assistance_offset_revenue` | Line 7a column (d), direct offsetting revenue |
| `sched_h_financial_assistance_at_cost` | Line 7a column (e), net |
| `sched_h_fa_7a_consistent` | Whether (c) − (d) = (e) within $1 on the return. Null when (c) or (e) is blank. This is a stricter test than the `irs_7a_inconsistent` note code and the site's "7a columns do not add up" badge, which fire only when the three differ by more than $1,000: in the ranked index 3 rows are false here (two are off by exactly $1,000) and 1 row carries the note. |
| `sched_h_fa_offset_pct_of_gross` | Column (d) as a percentage of column (c). |
| `sched_h_unreimbursed_medicaid_gross`, `_offset_revenue`, `sched_h_unreimbursed_medicaid` | Line 7b columns (c), (d), (e) |
| `sched_h_total_community_benefit` | Line 7k column (e) |
| `sched_h_total_expenses` | Total expenses from the Form 990 |
| `sched_h_tax_period_begin`, `sched_h_tax_period_end` | The return's tax period |
| `sched_h_object_id` | IRS e-file object id (text). Used in the ProPublica link. |
| `sched_h_release_year` | IRS e-file release the return came from (2023 to 2026). |
| `sched_h_amended_return` | True when the return used is marked amended. |

**CMS cost report (summed across the EIN's CCNs)**

| Column | Form location |
|---|---|
| `hcris_charity_care_cost` | S-10 line 23 column 3. Null if **any** CCN under the EIN has no value on the line. |
| `hcris_charity_care_cost_uninsured`, `hcris_charity_care_cost_insured` | Line 23 columns 1 and 2 |
| `hcris_charity_care_charges` | Line 20 column 3 |
| `hcris_charity_care_cost_before_payments` | Line 21 column 3 |
| `hcris_charity_care_partial_payments` | Line 22 column 3 |
| `hcris_medicaid_dsh_supplemental` | Line 5: Medicaid DSH and supplemental payments net of provider taxes. Negative when the taxes exceed the payments. Not part of line 23. |
| `hcris_medicaid_shortfall` | Line 8 |
| `hcris_uncompensated_care_cost` | Line 30 |
| `hcris_total_operating_expenses` | Worksheet G-3 line 4 |
| `hcris_ccns_missing_charity` | How many of the EIN's CCNs have no line 23 column 3. |
| `hcris_charity_care_cost_reporting_ccns` | Partial sum over the CCNs that do have it. Equals `hcris_charity_care_cost` when none are missing. Label it "partial" if you quote it. |
| `hcris_s10_filed` | True when every CCN's report has a Worksheet S-10. |
| `hcris_fy_bgn_dt`, `hcris_fy_end_dt` | Period of the cost report used. For a multi-CCN row, the worst-matching CCN's dates. |
| `hcris_report_status` | Status of the report used; for multi-CCN rows the distinct statuses, `;`-joined. |
| `hcris_rpt_rec_num` | Report record number(s), `;`-joined in `ccn_list` order (text). |

**Matching and derived**

| Column | Meaning |
|---|---|
| `hcris_months_from_990` | Calendar months between the cost report's period end and the 990's period end (worst CCN). |
| `period_aligned` | True when every CCN's report ends within 1 month of the 990's period end. **Use this column; do not re-derive alignment from the dates.** |
| `charity_gap` | `hcris_charity_care_cost` − `sched_h_financial_assistance_at_cost` (CMS minus IRS net). Null when either is null. |
| `charity_gap_gross` | `hcris_charity_care_cost` − `sched_h_financial_assistance_gross` (CMS minus IRS column c). |
| `community_benefit_pct_of_expenses` | Line 7k as a percentage (0–100) of the 990's total expenses. Same-form ratio; the one to quote. |
| `community_benefit_pct_of_hcris_expenses` | Line 7k over the cost report's operating expenses (0–100). Cross-form; a rough check only. |
| `svi_overall_pct`, `svi_socio_pct`, `svi_household_pct`, `svi_minority_pct`, `svi_housing_pct` | CDC/ATSDR SVI 2022 home-county percentiles (0–100, higher is more vulnerable). Null for a small number of rows (Connecticut among them). A proxy, not a service-area measure. |

**How the cost report was chosen.** For each CCN, the report whose period ends closest to the end of the EIN's tax year 2022 Form 990. For the return, a full-year return is preferred over a short-year one, then the latest period end, then the latest e-file timestamp (so an amended return is used over the original).

## The ranked index: `charity_care_gap_index_2022.json`

Top-level keys: `tax_year`, `filter`, `sources`, `fields`, `note_codes`, `counts`, `rows`.

- `filter` is the definition. A row of the matched table is in the index when all four hold:
  1. `ccn_count = 1` (one CCN with a cost report);
  2. `period_aligned` (cost report ends within 1 month of the 990);
  3. both figures at least $1,000,000;
  4. both total-expense figures positive and within 5% of each other.
- `counts` holds the funnel: `matched`, `computable`, `aligned`, `aligned_single_facility`, `clean_aligned` (the index size), `clean_aligned_over_50pct`, `clean_states`, and counts per note code. Quote counts from here.
- `rows` are ordered by absolute dollar difference. Keys: `ein`, `name`, `city`, `state`, `ccn`, `irs_7a`, `irs_7a_gross`, `irs_7a_offset`, `irs_7a_consistent`, `irs_7b`, `irs_7b_gross`, `irs_7b_offset`, `cms_s10`, `cms_s10_uninsured`, `cms_s10_insured`, `cms_s10_charges`, `cms_s10_cost_before_payments`, `cms_s10_payments`, `cms_s10_line5`, `gap` (CMS minus IRS net), `gap_gross`, `gap_pct` (absolute difference over the larger figure, 0–1), `expense_base`, `period_begin`, `period_end`, `hcris_fy_begin`, `hcris_fy_end`, `hcris_status`, `object_id`, `release_year`, `amended_990`, `ccns_with_cost_report`, `crosswalk_ccn_count`, `multi_ccn_crosswalk`, `svi_overall_pct`, `notes`.
- `notes` is a list of fixed codes, defined in `note_codes`: `irs_7a_inconsistent`, `irs_offset_reported`, `cms_line5_reported`, `multi_ccn_crosswalk`, `cms_report_as_submitted`, `irs_amended_return`. They are mechanical facts read from the filings, not judgements.

Read it with DuckDB:

```sql
WITH idx AS (
  SELECT UNNEST(rows) AS r
  FROM read_json('https://troveproject.com/data/charity_care_gap_index_2022.json', maximum_object_size = 50000000)
)
SELECT r.name, r.state, r.irs_7a, r.cms_s10, r.gap, ROUND(r.gap_pct * 100, 1) AS pct_of_larger
FROM idx
ORDER BY ABS(r.gap) DESC
LIMIT 10;
```

The same rows can be selected from the Parquet, which is handy for joins. This filter reproduces the index:

```sql
SELECT hospital_name, state, ein,
       sched_h_financial_assistance_at_cost AS irs_7a_net,
       hcris_charity_care_cost AS cms_s10_line23,
       charity_gap AS cms_minus_irs,
       ABS(charity_gap) / GREATEST(hcris_charity_care_cost, sched_h_financial_assistance_at_cost) AS pct_of_larger
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE ccn_count = 1
  AND period_aligned
  AND hcris_charity_care_cost >= 1000000
  AND sched_h_financial_assistance_at_cost >= 1000000
  AND hcris_total_operating_expenses > 0 AND sched_h_total_expenses > 0
  AND GREATEST(hcris_total_operating_expenses, sched_h_total_expenses)
      / LEAST(hcris_total_operating_expenses, sched_h_total_expenses) <= 1.05
ORDER BY ABS(charity_gap) DESC;
```

"Over 50%" on the site means `pct_of_larger > 0.5`.

## The lookup JSON: `community_benefit_gap_2022.json`

Top-level keys: `tax_year`, `totals`, `rows`, `rows_not_computable`. It is an object, not an array.

- `rows`: systems with both figures. `rows_not_computable`: systems where one figure is not reported (`gap` is null). **Search both arrays**, or hospitals such as The Johns Hopkins Hospital, St. Jude Children's Research Hospital, Texas Children's Hospital and Cleveland Clinic will not be found.
- Row keys: `ein`, `system` (990 filer name), `facility` (cost report name), `city`, `state`, `ccns`, `ccn_list` (array), `crosswalk_ccns`, `period_begin`, `period_end`, `hcris_fy_begin`, `hcris_fy_end`, `aligned`, `computable`, `hcris_status`, `s10_filed`, `hcris_charity` (S-10 line 23 col 3), `hcris_charity_uninsured`, `hcris_charity_insured`, `hcris_charity_reporting_ccns`, `ccns_missing_s10_charity`, `hcris_dsh_supplemental` (line 5), `hcris_uncomp`, `hcris_opex`, `fa_990` (7a col e), `fa_990_gross` (col c), `fa_990_offset` (col d), `fa_990_consistent`, `medicaid_990`, `medicaid_990_gross`, `medicaid_990_offset`, `cb_990` (7k), `exp_990`, `cb_pct`, `gap`, `gap_gross`, `gap_pct` (signed, −1 to 1), `object_id`, `release_year`, `amended_990`, and the five `svi_*` fields.
- `totals`: `matched`, `computable`, `aligned`, `aligned_material`, `s10_charity_missing`, `fa_990_missing`, and summary statistics for the aligned subset with both figures at least $500K.

## Without DuckDB (curl and the Python standard library)

```bash
curl -fsSL 'https://troveproject.com/data/community_benefit_gap_2022.json' | python3 -c "
import json, sys
data = json.load(sys.stdin)
if 'rows_not_computable' not in data:
    sys.exit('Older build of the data: it has no rows_not_computable and shows a missing S-10 line as 0. Use a clone of github.com/cbetz/trove instead.')
needle = 'johns hopkins'
fmt = lambda v: 'not reported on this line' if v is None else f'\${v:,.0f}'
for r in data['rows'] + data['rows_not_computable']:
    if needle in (r.get('system') or '').lower() or needle in (r.get('facility') or '').lower():
        print(r['facility'], '|', r['city'], r['state'], '| EIN', r['ein'], '| CCN', ','.join(r['ccn_list']))
        print('  IRS 7a (e) net:', fmt(r['fa_990']), '| (c):', fmt(r['fa_990_gross']), '| (d):', fmt(r['fa_990_offset']))
        print('  CMS S-10 line 23 col 3:', fmt(r['hcris_charity']), '| line 5:', fmt(r['hcris_dsh_supplemental']), '| S-10 filed:', r['s10_filed'])
        print('  CMS minus IRS:', fmt(r['gap']), '| period aligned:', r['aligned'])
"
```

## Joining the matched table to the cost report rows

`ccn_list` and `hcris_rpt_rec_num` are `;`-joined text in the same order. To get each CCN's own cost report for a system:

```sql
WITH sys AS (
  SELECT ein, UNNEST(string_split(hcris_rpt_rec_num, ';')) AS rpt_rec_num
  FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
  WHERE ein = '383952644'   -- Mayo Clinic group return
),
hcris AS (
  SELECT * FROM read_parquet('https://troveproject.com/data/hcris_2022_wide.parquet')
  UNION ALL BY NAME
  SELECT * FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
)
SELECT h.prvdr_num, h.hospital_name, h.fy_bgn_dt, h.fy_end_dt, h.rpt_status,
       h.s10_filed, h.charity_care_cost, h.medicaid_dsh_supplemental_payments
FROM sys JOIN hcris h ON h.rpt_rec_num = CAST(sys.rpt_rec_num AS BIGINT)
ORDER BY h.total_operating_expenses DESC NULLS LAST;
```

## Local Python packages (optional)

With the repository cloned and `uv sync --all-packages` run, the parsers are importable (`hcris`, `form990`, `crosswalk`, `analytics`). The full CCN-to-EIN crosswalk, with `teaching_hospital`, `children_hospital`, `urban` and `bed_size_band` flags per CCN, is at `packages/crosswalk/src/crosswalk/data/cbi.parquet` in the clone; it is not published under `/data/`. Rebuilding the matched table from raw CMS and IRS files is `uv run python scripts/build_gap_dataset.py`; it downloads several gigabytes and is not needed to answer questions.
