# IRS 990 Schedule H field dictionary

The fields trove extracts from Schedule H, with their location on the form and notes.

**Parquet bundle:** `https://troveproject.com/data/schedule_h_2022.parquet` — one row per filing. When an EIN appears in multiple IRS release-year ZIPs (originals + amendments), all versions are present; downstream code should `ORDER BY release_year DESC, tax_period_end DESC` and dedupe per EIN if it wants the latest version.

## Identity and timing

| Variable | Source | Notes |
|----------|--------|-------|
| `ein` | Header / Filer / EIN | Zero-padded 9-char string. The join key against the CCN crosswalk. |
| `organization_name` | Header / Filer / BusinessName | Often all-caps. Use case-insensitive search. |
| `tax_period_begin` | Header / TaxPeriodBeginDt | Start of the fiscal period this filing covers. |
| `tax_period_end` | Header / TaxPeriodEndDt | End of the fiscal period. The alignment-against-HCRIS metric uses this. |
| `tax_year` | Header / TaxYr | The IRS tax-year label. **Note:** for fiscal-year filers, this is the year the period *began*, not ended. A "TY2022" 990 from a July–June filer covers Jul 2022 – Jun 2023. |
| `return_version` | Root attribute `returnVersion` | e.g. `2022v5.0`. Schema element names have been stable since 2013v3.0. |
| `release_year` | (added by `parse_tax_year`) | Which IRS bulk-XML release-year ZIP this filing came from. Used to prefer amendments over originals. |

## Main 990 financials

These come from the parent 990, not Schedule H — they're useful as denominators.

| Variable | Source | Notes |
|----------|--------|-------|
| `total_revenue` | IRS990 / CYTotalRevenueAmt | Current-year total revenue, all activities. |
| `total_expenses` | IRS990 / CYTotalExpensesAmt | Current-year total expenses. The denominator for the Schedule H 7k community benefit %. |

## Schedule H Part I line 7 — community benefit (NET column)

Schedule H Part I has eleven line-7 categories, each broken into columns (a) activities, (b) persons served, (c) total expense, (d) offsetting revenue, (e) **net expense**, (f) percent of total expense. trove extracts column (e), the net amount, for every line — that's the figure used for cross-form context.

| Variable | Schedule H line | Notes |
|----------|-----------------|-------|
| `financial_assistance_at_cost` | **7a** | Charity-care cost. **The cross-reference against HCRIS Worksheet S-10 charity care.** This is the field that powers `analytics.community_benefit_gap()`. |
| `unreimbursed_medicaid` | 7b | Medicaid shortfall — Medicaid payments minus Medicaid cost. |
| `unreimbursed_other_means_tested` | 7c | Other means-tested government programs (CHIP, etc.) net of payments. |
| `total_financial_assistance` | 7d | Sum of 7a + 7b + 7c. |
| `community_health_services` | 7e | Community health improvement services and community-benefit operations. |
| `health_professions_education` | 7f | Education of health professionals (residencies etc., to the extent not reimbursed). |
| `subsidized_health_services` | 7g | Services run at a financial loss to meet community need. |
| `research` | 7h | Research conducted. |
| `cash_and_in_kind_contributions` | 7i | Cash + in-kind contributions for community benefit. |
| `total_other_benefits` | 7j | Sum of 7e + 7f + 7g + 7h + 7i. |
| `total_community_benefit` | **7k** | Total community benefit. Sum of 7d + 7j. The "headline" Schedule H number that appears in benchmarking and PR. |
| `total_community_benefit_pct` | 7k column (f) | Total community benefit as % of total expenses (the same ratio the IRS publishes). |

## Schedule H Part III — bad debt

| Variable | Source | Notes |
|----------|--------|-------|
| `bad_debt_expense` | Part III / BadDebtExpenseAmt | Bad-debt expense reported on Schedule H Part III line 2. Distinct from charity-care cost — bad debt is care provided where collection was attempted but failed; charity care is care provided where the patient was determined unable to pay before collection. |

## Schedule H Part V Section A — facility count

| Variable | Source | Notes |
|----------|--------|-------|
| `hospital_facility_count` | Part V / HospitalFacilitiesCnt | Number of hospital facilities operated under this EIN. The "system size" denominator when comparing per-facility HCRIS numbers up to the system-level 990. |

## How the line-7 fields relate

```
7d = 7a + 7b + 7c   (financial assistance to means-tested patients)
7j = 7e + 7f + 7g + 7h + 7i   (other community benefit)
7k = 7d + 7j   (total community benefit)
```

When the public discourse says "X reported $Y in community benefit," they almost always mean 7k. When they say "X reported $Y in charity care," they mean 7a. These are very different numbers — a teaching hospital can have small 7a and large 7k because of research and education.

## Tax-year-2022 vs. fiscal-period-2022

The IRS labels filings by the year the tax period *began*. A "TY2022" filing from a July–June fiscal-year filer covers July 2022 – June 2023. Most TY2022 returns appear in the IRS 2024 release-year ZIPs; late filers and amendments trickle into 2025/2026 release ZIPs. trove ingests all three.
