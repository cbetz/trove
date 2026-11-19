# Reading a difference between the two figures

Use this when a user asks "why are these two numbers different?" or "what is in the difference?" for one hospital. The answer is a walk through the components that the two filings publish. It is not a verdict on either filing.

## What the two lines are

| | IRS Form 990, Schedule H, Part I, line 7a | CMS cost report (2552-10), Worksheet S-10, line 23 |
|---|---|---|
| What it is | Financial assistance at cost | Cost of charity care after patient payments |
| Columns | (c) total expense, (d) direct offsetting revenue, (e) net = (c) − (d) | col 1 uninsured, col 2 insured, col 3 = col 1 + col 2 |
| Filed by | The legal entity (EIN) | The provider (CCN) |
| Costing | The filer's most accurate costing method | Charges times the worksheet's cost-to-charge ratio |
| Provider taxes and state pool payments | Under the Schedule H instructions (Worksheet 1), a filer may include Medicaid or provider taxes in the line 7a cost when payments from its state's uncompensated care pool or DSH program are intended primarily to offset the cost of financial assistance, and reports that pool revenue in column (d). Otherwise both go on line 7b. | Medicaid DSH and supplemental payments "net of associated provider taxes or assessments" are on S-10 line 5, which is not part of line 23. |
| Insured patients | Depends on the filer's financial assistance policy | Column 2 counts deductibles and coinsurance written off |

So the two can differ for definitional reasons when both are filed correctly.

## Step 1: get the row with its components

```sql
SELECT
  hospital_name, city, state, ein, ccn_list, ccn_count,
  -- periods and status
  sched_h_tax_period_begin, sched_h_tax_period_end,
  hcris_fy_bgn_dt, hcris_fy_end_dt, period_aligned, hcris_months_from_990,
  hcris_report_status, hcris_s10_filed, sched_h_amended_return, sched_h_release_year,
  -- IRS Schedule H Part I line 7a
  sched_h_financial_assistance_gross          AS irs_7a_c_total_expense,
  sched_h_financial_assistance_offset_revenue AS irs_7a_d_offsetting_revenue,
  sched_h_financial_assistance_at_cost        AS irs_7a_e_net,
  sched_h_fa_7a_consistent,
  -- CMS Worksheet S-10
  hcris_charity_care_cost_uninsured AS cms_line23_col1_uninsured,
  hcris_charity_care_cost_insured   AS cms_line23_col2_insured,
  hcris_charity_care_cost           AS cms_line23_col3,
  hcris_medicaid_dsh_supplemental   AS cms_line5,
  -- differences, always CMS minus IRS
  charity_gap       AS cms_minus_irs_net,
  charity_gap_gross AS cms_minus_irs_gross,
  -- links
  sched_h_object_id, hcris_rpt_rec_num
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE ein = '060646652';
```

## Step 2: check that a difference can be read at all

Stop and say so if any of these hold:

- `cms_line23_col3` is null. The cost report has no value on line 23. If `hcris_s10_filed` is false the report has no Worksheet S-10 at all; if true, the S-10 is there and line 23 is blank. Say "not reported on this line". There is no difference to discuss.
- `irs_7a_e_net` is null. Line 7a column (e) is blank on the return. Same treatment.
- `period_aligned` is false. The cost report used ends `hcris_months_from_990` months from the 990's period end, so the two figures describe different fiscal periods.
- `ccn_count` > 1. The CMS side is a sum over several cost reports under one EIN. You can still show the components, but say the row is a system total and is not in the ranked index.
- `sched_h_fa_7a_consistent` is false. On the return itself (c) − (d) does not equal (e). Show all three and say the difference rests on a figure that does not add up on the return.

## Step 3: lay out the components and compare sizes

The difference is always CMS minus IRS. Compare its size with each component the filings publish:

```sql
SELECT
  hospital_name,
  charity_gap AS cms_minus_irs_net,
  sched_h_financial_assistance_offset_revenue AS irs_7a_d,
  hcris_medicaid_dsh_supplemental             AS cms_line5,
  hcris_charity_care_cost_insured             AS cms_col2_insured,
  ROUND(sched_h_financial_assistance_offset_revenue / charity_gap, 2) AS d_over_difference,
  ROUND(hcris_medicaid_dsh_supplemental / charity_gap, 2)             AS line5_over_difference,
  ROUND(hcris_charity_care_cost_insured / charity_gap, 2)             AS insured_over_difference,
  ROUND(sched_h_financial_assistance_at_cost / hcris_charity_care_cost_uninsured, 2) AS irs_net_over_cms_uninsured
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE ein = '060646652';
```

How to read the ratios (a ratio near 1 means that component is about the size of the difference; a negative ratio means the component points the other way):

- **CMS figure larger (difference positive).**
  - `d_over_difference` near 1: the IRS net figure is after subtracting offsetting revenue of about that size. On a gross basis (`charity_gap_gross`) the two are much closer.
  - `insured_over_difference` near 1 with `irs_net_over_cms_uninsured` near 1: the IRS figure is close to the CMS uninsured-only column, and the S-10 insured column is about the size of the difference.
- **IRS figure larger (difference negative).**
  - `line5_over_difference` near 1 with line 5 negative: the cost report shows provider taxes exceeding the DSH and supplemental payments by about the size of the difference. The Schedule H instructions permit provider taxes in line 7a cost under the condition above. This is consistent with that classification; the filings do not state it.
- **Line 5 positive and column (d) positive.** The cost report shows net pool payments received and the return shows offsetting revenue. Compare the two amounts and say what each is.
- **None of the ratios is near 1.** Neither filing shows a mechanism. Say that, and pose the question: what is in one figure that is not in the other?

## Step 4: say it carefully

Template:

> [Hospital] reports $X on Schedule H line 7a column (e) and $Y on S-10 line 23 column 3 for the fiscal year ending [date] (both filings cover the same period). The difference is $Z. The return lists $C of total expense and $D of offsetting revenue on line 7a. The cost report lists $U for uninsured and $I for insured patients on line 23, and $L on line 5. Of the $Z difference, about $L appears to be [component]. This is a reconciliation from the two filings, not a figure the hospital has stated; the worksheet behind the IRS line is not public.

Never write that a hospital overstated, understated, inflated or double-counted anything. If the user asks whether a hospital is "lying" or which figure is "right", answer that the two lines are defined differently, show the components, and say the filings alone cannot settle more than that.

## Worked example: Yale New Haven Hospital

EIN 06-0646652, CCN 070022, fiscal year ending 2023-09-30 on both filings. Values from the November 2026 build; re-run the query before quoting.

| Component | Amount |
|---|--:|
| IRS 7a (c) total expense | $257,262,512 |
| IRS 7a (d) offsetting revenue | $144,162,000 |
| IRS 7a (e) net | $113,100,512 |
| CMS S-10 line 23 col 3 | $35,568,680 |
| CMS S-10 line 23 col 1 / col 2 | $30,287,094 / $5,281,586 |
| CMS S-10 line 5 | −$71,469,000 |
| (e) minus line 23 | $77,531,832 |

Approved wording:

> Of the $77.5M difference, about $71.5M appears to be Connecticut's hospital provider tax net of the state supplemental payments it funds: the amount on S-10 line 5, which the cost report keeps separate from charity care. The worksheet behind the IRS line is not public, so this is a reconciliation from the hospital's own filings, not a figure the hospital has stated.

Supporting detail from the same filings:

- The return's Schedule H narrative (Part III, line 4) describes the Connecticut Disproportionate Share Hospital Program as funded in part by an assessment on hospital net patient service revenue, and says the system paid $317.9M into it and received $198.2M in distributions for the year ended September 30, 2023. The narrative does not say what is in line 7a.
- The system's four Connecticut hospitals in the data are Yale New Haven, Bridgeport, Greenwich and Lawrence + Memorial. Their line 7a column (d) amounts sum to $198.2M, and their S-10 line 5 amounts sum to −$119.7M, which is $198.2M minus $317.9M.
- For the three sister hospitals, line 5 against the difference: Greenwich −$19.84M against −$19.58M; Lawrence + Memorial −$16.32M against −$16.31M; Bridgeport −$12.08M against −$13.16M.
- Other Connecticut hospitals in the matched table show a negative line 5 with column (d) blank or zero and a much smaller difference, for example St. Vincent's Medical Center (line 5 −$10.90M, difference −$0.82M) and Midstate Medical Center (line 5 −$9.69M, difference −$0.01M). That is what the filings show; it does not say which classification any hospital chose.

Query for the Connecticut rows:

```sql
SELECT hospital_name,
       sched_h_financial_assistance_offset_revenue AS irs_7a_d,
       hcris_medicaid_dsh_supplemental AS cms_line5,
       charity_gap AS cms_minus_irs_net
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE state = 'CT' AND charity_gap IS NOT NULL AND hcris_medicaid_dsh_supplemental IS NOT NULL
ORDER BY ABS(charity_gap) DESC;
```

## The top 25 of the ranked index

A hand reading of the 25 largest dollar differences in the index, from the two filings alone, sorted them this way. These are reconciliations from the filings, not statements by the hospitals.

- **9** where column (d) or S-10 line 5 is at least half the size of the difference and points the same way: offsetting revenue in column (d) where the CMS figure is the larger (it is subtracted on the IRS line only), or a negative line 5 where the IRS figure is the larger: Yale New Haven, Tampa General, St. Peter's University Hospital, St. Joseph's Hospital (FL), St. Joseph's University Medical Center (NJ), Greenwich, Ascension Providence, Lawrence + Memorial, Bayfront Health St. Petersburg.
- **3** where the IRS figure is nearer the CMS uninsured-only column than the total: Saint Thomas West, Baptist Medical Center (FL), Saint Thomas Rutherford. The insured column is 44%, 75% and 71% of the difference for these three.
- **2** where a filing is hard to read at face value. On the Hendrick Medical Center return, line 7a (c) − (d) does not equal (e). For Western Regional Medical Center (AZ), the S-10 lists all of its charity care in the insured column, and the return's Medicaid line (7b column c) is larger than the total expenses on the same return.
- **11** where neither filing shows a mechanism: Long Island Jewish, North Shore University, Maimonides, Methodist Healthcare Memphis, NorthBay, Lehigh Valley, Lenox Hill, Martin Luther King Jr. Community, Cook Children's, Montefiore, Flagstaff. These are open questions. Present them as questions. Five of these show a positive line 5 at least half the size of the difference (Long Island Jewish: line 5 +$35.8M, difference −$36.1M). A positive line 5 is payments received net of taxes; neither filing shows it entering either figure, so it is not counted as accounting for the difference.

This classification is hand-written for the November 2026 build. If the index order has changed, re-derive it from the components instead of repeating the list.

## Links to the two filings

**IRS return (ProPublica Nonprofit Explorer).** Use the EIN without leading zeros and the row's `sched_h_object_id`:

```
https://projects.propublica.org/nonprofits/organizations/{ein without leading zeros}/{sched_h_object_id}/IRS990ScheduleH
```

Example: `https://projects.propublica.org/nonprofits/organizations/60646652/202422269349301652/IRS990ScheduleH`

**CMS cost report record (data.cms.gov, Hospital Provider Cost Report).** One dataset per fiscal-year file, chosen by the date the report's period begins (`hcris_fy_bgn_dt`):

| Period begins | Dataset id |
|---|---|
| 2021-10-01 through 2022-09-30 (FY2022 file) | `8457c184-a531-40db-8597-2497fec80c7a` |
| 2022-10-01 through 2023-09-30 (FY2023 file) | `f08d4c46-c0e4-4bcb-a54a-c62c87d59251` |

```
https://data.cms.gov/data-api/v1/dataset/{dataset id}/data?filter[Provider CCN]={ccn}
```

Example: `https://data.cms.gov/data-api/v1/dataset/f08d4c46-c0e4-4bcb-a54a-c62c87d59251/data?filter[Provider CCN]=070022`

That dataset is a summary CMS derives from the same cost reports; its "Cost of Charity Care" field is S-10 line 23 column 3. CMS refreshes it on its own schedule, so a figure there can differ slightly from the file used here. If a dataset id stops resolving, link the landing page instead: https://data.cms.gov/provider-compliance/cost-reports/hospital-provider-cost-report

For a multi-CCN row, give one CMS link per CCN in `ccn_list`; a single CCN's report can be in the other fiscal-year file.
