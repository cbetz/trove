# Example queries for hcris-analyst

Each example is a question, the approach, and a DuckDB query that runs against the published bundles. All of them were run against the November 2026 build. Swap `https://troveproject.com/data/` for a local path (`trove/web/data/`) when working from a clone.

Before the first cross-form query in a session, run the bundle check in `parquet_layout.md` ("Is this the current build?").

## 1. Both figures for one hospital

**Q:** "What did Yale New Haven Hospital report as charity care to the IRS and to CMS?"

Search both name columns; names on the cost report are often abbreviated.

```sql
SELECT hospital_name, city, state, ein, ccn_list,
       sched_h_financial_assistance_at_cost AS irs_7a_net,
       hcris_charity_care_cost              AS cms_s10_line23,
       charity_gap                          AS cms_minus_irs,
       period_aligned, hcris_fy_end_dt, sched_h_tax_period_end,
       hcris_report_status, sched_h_amended_return
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE LOWER(hospital_name) LIKE '%yale%'
   OR LOWER(sched_h_organization_name) LIKE '%yale%'
ORDER BY hcris_total_operating_expenses DESC NULLS LAST;
```

If more than one row comes back, list them and ask which. Report both figures with their form, line and column, the fiscal period, and whether the periods are aligned. Then offer the components.

## 2. What is in the difference

**Q:** "Why are Yale's two numbers so different?"

Follow `reading_a_difference.md`. The components query:

```sql
SELECT hospital_name,
       sched_h_financial_assistance_gross          AS irs_7a_c_total_expense,
       sched_h_financial_assistance_offset_revenue AS irs_7a_d_offsetting_revenue,
       sched_h_financial_assistance_at_cost        AS irs_7a_e_net,
       hcris_charity_care_cost_uninsured           AS cms_line23_col1_uninsured,
       hcris_charity_care_cost_insured             AS cms_line23_col2_insured,
       hcris_charity_care_cost                     AS cms_line23_col3,
       hcris_medicaid_dsh_supplemental             AS cms_line5,
       charity_gap                                 AS cms_minus_irs_net,
       charity_gap_gross                           AS cms_minus_irs_gross,
       sched_h_fa_7a_consistent, period_aligned, sched_h_object_id
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE ein = '060646652';
```

Say what the components show, label it as a reconciliation from the filings, and give the links to both filings.

## 3. The ranked index, filtered

**Q:** "Which Florida hospitals in the index differ by more than 50%?"

```sql
WITH idx AS (
  SELECT UNNEST(rows) AS r
  FROM read_json('https://troveproject.com/data/charity_care_gap_index_2022.json', maximum_object_size = 50000000)
)
SELECT r.name, r.city, r.irs_7a, r.cms_s10, r.gap AS cms_minus_irs,
       ROUND(r.gap_pct * 100, 1) AS pct_of_larger,
       r.irs_7a_offset, r.cms_s10_line5
FROM idx
WHERE r.state = 'FL' AND r.gap_pct > 0.5
ORDER BY r.gap_pct DESC;
```

Give the count out of the state's index rows (`SELECT COUNT(*) ... WHERE r.state = 'FL'`), and remind the user what the index is: one hospital with a cost report under the EIN, same fiscal period on both filings, both figures at least $1M, total expenses within 5%. A difference over 50% is a reason to read the components, not a finding about the hospital.

## 4. The funnel and the headline counts

**Q:** "How many hospitals are in the index, and how many differ by more than half?"

Read them from the index file; do not quote them from memory.

```sql
SELECT counts.matched, counts.computable, counts.aligned, counts.aligned_single_facility,
       counts.clean_aligned AS in_index, counts.clean_states AS states,
       counts.clean_aligned_over_50pct AS over_50pct
FROM read_json('https://troveproject.com/data/charity_care_gap_index_2022.json', maximum_object_size = 50000000);
```

Direction and median, from the same file:

```sql
WITH idx AS (
  SELECT UNNEST(rows) AS r
  FROM read_json('https://troveproject.com/data/charity_care_gap_index_2022.json', maximum_object_size = 50000000)
)
SELECT COUNT(*) FILTER (WHERE r.gap > 0) AS cms_figure_larger,
       COUNT(*) FILTER (WHERE r.gap < 0) AS irs_figure_larger,
       COUNT(*) FILTER (WHERE r.gap = 0) AS same_amount,
       ROUND(MEDIAN(r.gap_pct) * 100, 1) AS median_pct_of_larger
FROM idx;
```

## 5. A hospital with no CMS figure

**Q:** "Why does Johns Hopkins show no CMS charity care figure?"

```sql
SELECT hospital_name, state, ein, ccn_list,
       sched_h_financial_assistance_at_cost AS irs_7a_net,
       hcris_charity_care_cost              AS cms_s10_line23,
       hcris_s10_filed, hcris_ccns_missing_charity,
       hcris_uncompensated_care_cost, hcris_report_status, charity_gap
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE LOWER(hospital_name) LIKE '%johns hopkins hospital%';
```

Read the result literally. `cms_s10_line23` null with `hcris_s10_filed` true: the cost report includes a Worksheet S-10 and line 23 has no value. `hcris_s10_filed` false: the cost report has no Worksheet S-10. Either way the answer is "not reported on this line", with no difference computed. Do not supply a reason the filings do not give. You can add context that the data supports, for example how many rows in the same state are null on this line:

```sql
SELECT state, COUNT(*) AS matched_rows,
       COUNT(*) FILTER (WHERE hcris_charity_care_cost IS NULL) AS no_line23_value,
       COUNT(*) FILTER (WHERE hcris_charity_care_cost IS NULL AND hcris_s10_filed) AS of_which_s10_filed
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE state = 'MD'
GROUP BY state;
```

## 6. A multi-hospital system

**Q:** "Show Cleveland Clinic's two figures."

```sql
SELECT hospital_name, sched_h_organization_name, ein, ccn_count, crosswalk_ccn_count,
       sched_h_financial_assistance_at_cost   AS irs_7a_net,
       hcris_charity_care_cost                AS cms_s10_line23_all_ccns,
       hcris_ccns_missing_charity,
       hcris_charity_care_cost_reporting_ccns AS cms_partial_sum,
       charity_gap, period_aligned
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE LOWER(sched_h_organization_name) LIKE '%cleveland clinic foundation%';
```

One return covers several cost reports. When `hcris_ccns_missing_charity` is above 0, the system total is null and `cms_partial_sum` covers only the CCNs that report the line: quote it as a partial sum over N of M cost reports and give no difference. When it is 0 (Mayo Clinic's group return, EIN 383952644, is an example), the total is a sum across all the system's cost reports. Either way, say the row is a system and is not in the ranked index. The per-CCN breakdown is the join in `parquet_layout.md`.

## 7. A hospital's cost-report profile

**Q:** "Show me a profile of NewYork-Presbyterian."

```sql
SELECT hcris_file_fy, prvdr_num, hospital_name, fy_bgn_dt, fy_end_dt, rpt_status,
       ownership_type, total_beds, icu_beds, total_discharges,
       net_patient_revenue, total_operating_expenses,
       charity_care_cost, uncompensated_care_cost, s10_filed
FROM (
  SELECT * FROM read_parquet('https://troveproject.com/data/hcris_2022_wide.parquet')
  UNION ALL BY NAME
  SELECT * FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
)
WHERE prvdr_num = '330101'
   OR LOWER(hospital_name) LIKE '%new york presbyterian%'
   OR LOWER(hospital_name) LIKE '%newyork-presbyterian%'
ORDER BY prvdr_num, fy_bgn_dt;
```

Several CCNs can match a name, and each usually has two rows, one per reporting period. Show the period on every row. If the user wants "the 2022 figure", say which period that is. The figure shown next to the tax year 2022 Form 990 on troveproject.com is the report whose period ends closest to the 990's.

## 8. Field glossary

**Q:** "What does Worksheet S-10 line 23 column 1 mean?"

Look it up in `dictionary.md` (`charity_care_cost_uninsured`: cost of charity care for uninsured patients). If the cell is not one of the dictionary's variables, say trove does not extract it and point to the CMS Provider Reimbursement Manual, Part 2, chapter 40, which defines every line of form 2552-10.

## 9. Every return on file for an EIN

**Q:** "Did Long Island Jewish amend its tax year 2022 return?"

```sql
SELECT ein, organization_name, tax_period_end, release_year, amended_return,
       return_ts::VARCHAR AS e_filed, object_id,
       financial_assistance_at_cost AS line_7a_e, total_community_benefit AS line_7k_e
FROM read_parquet('https://troveproject.com/data/schedule_h_2022.parquet')
WHERE ein = '112241326'
ORDER BY return_ts;
```

More than one row means more than one return was released. `amended_return` marks an amended one. The matched table uses the latest full-year return (see `schedule_h.md`), and its `sched_h_object_id` says which.

## 10. Largest uncompensated care in one CMS file

**Q:** "Which hospitals reported the most uncompensated care cost in the fiscal year 2023 file?"

```sql
SELECT prvdr_num, hospital_name, fy_bgn_dt, fy_end_dt, ownership_type, total_beds,
       charity_care_cost, non_medicare_bad_debt_cost, uncompensated_care_cost
FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
WHERE uncompensated_care_cost IS NOT NULL
ORDER BY uncompensated_care_cost DESC
LIMIT 10;
```

This is a cost-report-only question; it covers every hospital type, not only nonprofits. Name the file and the periods it holds (beginning 2022-10-01 through 2023-09-30).

## 11. Which index rows list offsetting revenue on line 7a

**Q:** "Which hospitals in the index report offsetting revenue on line 7a, and how much?"

```sql
WITH idx AS (
  SELECT UNNEST(rows) AS r
  FROM read_json('https://troveproject.com/data/charity_care_gap_index_2022.json', maximum_object_size = 50000000)
)
SELECT r.name, r.state, r.irs_7a_gross, r.irs_7a_offset, r.irs_7a,
       ROUND(100.0 * r.irs_7a_offset / r.irs_7a_gross, 1) AS offset_pct_of_gross,
       r.cms_s10, r.cms_s10_line5
FROM idx
WHERE list_contains(r.notes, 'irs_offset_reported')
ORDER BY r.irs_7a_offset DESC
LIMIT 15;
```

## 12. Peer context

**Q:** "Show Yale New Haven next to other large nonprofit hospitals."

```sql
SELECT prvdr_num, hospital_name, fy_end_dt, total_beds, total_operating_expenses,
       charity_care_cost,
       ROUND(100 * charity_care_cost / total_operating_expenses, 2) AS charity_pct_of_expenses
FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
WHERE ownership_type IN ('1', '2')
  AND total_beds >= 1000
ORDER BY total_operating_expenses DESC
LIMIT 20;
```

State the cohort rule (nonprofit control codes 1 and 2, 1,000 beds or more, fiscal year 2023 file). Rows with a null `charity_care_cost` have no value on S-10 line 23; show them as "not reported on this line", not as zero. Teaching status is not in the bundles (see `cohorts.md`).

## 13. Charity care ratio by home-county SVI band

**Q:** "How does S-10 charity care as a share of expenses vary by home-county SVI?"

```sql
SELECT
  CASE
    WHEN svi_overall_pct >= 80 THEN '80-100'
    WHEN svi_overall_pct >= 60 THEN '60-79'
    WHEN svi_overall_pct >= 40 THEN '40-59'
    WHEN svi_overall_pct >= 20 THEN '20-39'
    WHEN svi_overall_pct IS NOT NULL THEN '0-19'
    ELSE 'no SVI value'
  END AS svi_band,
  COUNT(*) AS systems,
  COUNT(hcris_charity_care_cost) AS with_line23_value,
  ROUND(MEDIAN(100 * hcris_charity_care_cost / hcris_total_operating_expenses), 2) AS median_charity_pct_of_expenses
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE hcris_total_operating_expenses > 1e6
GROUP BY 1
ORDER BY 1;
```

Rows without a line 23 value are left out of the median, not counted as zero; report how many. SVI here is a home-county proxy, not a service area, and it says nothing about whether a hospital's charity care is adequate.

## Questions with no query

- "What is the difference between S-10 line 23 and Schedule H line 7a?" Answer from the table at the top of `reading_a_difference.md`.
- "Why are some rows not period-aligned?" The cost report closest to the 990 still ends more than a month away, usually because the hospital changed its fiscal year or the matching report is not in the two CMS files. `hcris_months_from_990` gives the distance.
- "How were CCNs matched to EINs?" The Community Benefit Insight crosswalk, December 2024. It covers nonprofit hospitals. Some CCNs it lists have no cost report in the two CMS files (`crosswalk_ccn_count` above `ccn_count`).
- "Does this cover staffing or quality?" No. Say where those live (Worksheet S-3 Parts II–V for wages and FTEs; CMS Care Compare for quality).
