# Example queries for hcris-analyst

Each example shows a natural-language question, the right approach, and a runnable DuckDB query. Use these as templates.

## 1. Hospital profile

**Q:** "Show me a profile of New York-Presbyterian."

```sql
SELECT
  prvdr_num, hospital_name, ownership_type, total_beds, icu_beds,
  total_discharges, inpatient_bed_days_utilized,
  net_patient_revenue, total_operating_expenses,
  charity_care_cost, uncompensated_care_cost
FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
WHERE prvdr_num = '330101'  -- NYP's CCN
   OR LOWER(hospital_name) LIKE '%new york presbyterian%'
ORDER BY net_patient_revenue DESC
LIMIT 5;
```

If the user gives a name only and there are multiple matches, surface the candidates with bed counts and revenue and ask which one.

## 2. Peer context

**Q:** "Show Yale-New Haven alongside similar major teaching hospitals."

```sql
WITH yale AS (
  SELECT * FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
  WHERE prvdr_num = '070022'
),
peers AS (
  SELECT * FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
  WHERE total_beds BETWEEN 800 AND 2000
    AND ownership_type IN ('1', '2')  -- voluntary nonprofit
    AND prvdr_num != '070022'
)
SELECT
  prvdr_num, hospital_name, total_beds, net_patient_revenue,
  charity_care_cost,
  charity_care_cost / total_operating_expenses AS charity_care_ratio
FROM peers
UNION ALL SELECT prvdr_num, hospital_name, total_beds, net_patient_revenue,
  charity_care_cost, charity_care_cost / total_operating_expenses
FROM yale
ORDER BY charity_care_ratio DESC NULLS LAST;
```

## 3. Aligned-period cross-form differences

**Q:** "Show the aligned-period CMS and IRS charity-care fields for Yale-New Haven."

```sql
SELECT
  ein,
  sched_h_organization_name AS system,
  hospital_name AS lead_facility,
  ccn_count,
  hcris_charity_care_cost,
  sched_h_financial_assistance_at_cost AS fa_990,
  charity_gap AS cross_form_difference,
  charity_gap / GREATEST(ABS(hcris_charity_care_cost), ABS(sched_h_financial_assistance_at_cost)) AS difference_pct
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE ROUND(ABS(EXTRACT(EPOCH FROM (hcris_fy_end_dt - sched_h_tax_period_end))) / 2629800) <= 1
  AND ABS(hcris_charity_care_cost) >= 500000
  AND ABS(sched_h_financial_assistance_at_cost) >= 500000
  AND (
    LOWER(sched_h_organization_name) LIKE '%yale%'
    OR LOWER(hospital_name) LIKE '%yale%'
  )
ORDER BY system;
```

## 4. Field glossary lookup

**Q:** "What does Worksheet S-10 line 23 column 1 mean?"

Look it up in `dictionary.md`. If the variable is in the 44-variable trove dictionary, return the human name + description. If not, explain that the variable isn't in the trove dictionary but is documented in CMS Provider Reimbursement Manual Chapter 40 — point to the worksheet/line in the source document and offer to help characterize the field if the user can describe what they're trying to compute.

## 5. Schedule H amendments per EIN

**Q:** "Did Memorial Hermann amend their TY2022 990?"

```sql
SELECT
  ein, organization_name, tax_period_end, release_year,
  financial_assistance_at_cost, total_community_benefit
FROM read_parquet('https://troveproject.com/data/schedule_h_2022.parquet')
WHERE ein = '741152597'
ORDER BY release_year DESC, tax_period_end DESC;
```

(Multiple rows = multiple filings. The `analytics.community_benefit_gap()` function prefers the highest `release_year`.)

## 6. Top safety-net hospitals by uncompensated care

**Q:** "Which hospitals provided the most uncompensated care in FY2023?"

```sql
SELECT prvdr_num, hospital_name, total_beds,
       charity_care_cost, medicare_bad_debt_reimbursable, non_medicare_bad_debt_cost,
       uncompensated_care_cost
FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
WHERE uncompensated_care_cost IS NOT NULL
ORDER BY uncompensated_care_cost DESC
LIMIT 10;
```

Use this as a descriptive HCRIS-only query. Do not mix it with Schedule H fields unless the question specifically requires cross-form context.

## 7. Rows where Schedule H 7k is high relative to HCRIS operating expenses

**Q:** "Show rows where Schedule H total community benefit is high relative to HCRIS operating expenses."

```sql
SELECT ein, sched_h_organization_name,
       sched_h_total_community_benefit AS cb_990,
       hcris_total_operating_expenses AS hcris_opex,
       sched_h_total_community_benefit / hcris_total_operating_expenses AS ratio
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE hcris_total_operating_expenses > 0
  AND sched_h_total_community_benefit / hcris_total_operating_expenses > 0.30
ORDER BY ratio DESC
LIMIT 10;
```

Often this reflects a children's/specialty hospital where 7k is dominated by research+education, or a rollup mismatch (multi-CCN system whose HCRIS reports are partial). Treat it as a data-context question, not a conclusion.

## 8. Charity-care cost ratio by home-county SVI band

**Q:** "How do charity-care cost ratios vary by home-county SVI band?"

```sql
WITH banded AS (
  SELECT
    CASE
      WHEN svi_overall_pct >= 80 THEN 'high (80-100)'
      WHEN svi_overall_pct >= 60 THEN 'moderately above (60-79)'
      WHEN svi_overall_pct >= 40 THEN 'near median (40-59)'
      WHEN svi_overall_pct >= 20 THEN 'below average (20-39)'
      WHEN svi_overall_pct IS NOT NULL THEN 'low (1-19)'
      ELSE 'unknown'
    END AS svi_band,
    hcris_charity_care_cost,
    hcris_total_operating_expenses
  FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
  WHERE hcris_total_operating_expenses > 1e6
)
SELECT
  svi_band,
  COUNT(*) AS n_systems,
  ROUND(MEDIAN(hcris_charity_care_cost / hcris_total_operating_expenses) * 100, 2) AS median_charity_pct
FROM banded
GROUP BY svi_band
ORDER BY median_charity_pct DESC NULLS LAST;
```

SVI supports coarse geographic context only. This is a home-county proxy, not a service-area measure, and it should not be used to judge adequacy of charity care. Sub-theme columns (`svi_socio_pct`, `svi_minority_pct`, etc.) can explain why a county ranks high on SVI overall.

## When the question doesn't have a SQL answer

Some questions are about the data structure or method, not the data values. Examples:

- "What's the difference between Worksheet S-10 charity care and Schedule H 7a?" → answer from `schedule_h.md` and the methodology section, no query.
- "Why are most rows misaligned by 12 months?" → answer from `parquet_layout.md` alignment discussion.
- "How is the crosswalk built?" → describe CBI's December 2024 vintage; point to `packages/crosswalk/README.md`.
