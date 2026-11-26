# HCRIS 2552-10 field dictionary

Every variable trove exposes from the Medicare Cost Report Hospital form, with the canonical (worksheet, line, column) source and a short description. Generated from `packages/hcris/src/hcris/dictionaries/2552-10.yaml`.

**Pivoted Parquet bundles:** `https://troveproject.com/data/hcris_2022_wide.parquet` and `https://troveproject.com/data/hcris_2023_wide.parquet` (CMS fiscal-year files, keyed on the date the reporting period begins; one row per cost report, every variable below as a named column, plus `hcris_file_fy`, `rpt_rec_num`, `prvdr_num`, `fy_bgn_dt`, `fy_end_dt`, `rpt_stus_cd`, `rpt_status`, `proc_dt` and `s10_filed`).

A null value means the cell is blank or zero on the form: CMS's numeric file stores no zeros. It is not a reported $0.

Total: **52 variables** across 7 worksheets.

## Worksheet `D10A181`

| Variable | Line | Column | Source | Type | Description |
|----------|------|--------|--------|------|-------------|
| `medicare_inpatient_operating_cost` | 5300 | 100 | nmrc | currency_usd | Medicare inpatient program operating cost (Worksheet D-1 Part II). |

## Worksheet `D30A180`

| Variable | Line | Column | Source | Type | Description |
|----------|------|--------|--------|------|-------------|
| `medicare_inpatient_routine_charges` | 3000–3599 (sum) | 200 | nmrc | currency_usd | Medicare inpatient program routine service charges, summed across department lines. |
| `medicare_inpatient_ancillary_net_charges` | 20200 | 200 | nmrc | currency_usd | Medicare inpatient program ancillary service net charges (Worksheet D-3). |

## Worksheet `G200000`

| Variable | Line | Column | Source | Type | Description |
|----------|------|--------|--------|------|-------------|
| `inpatient_revenue_hospital` | 100 | 100 | nmrc | currency_usd | Inpatient hospital revenue (acute-care component of the facility). |
| `inpatient_revenue_general` | 1000 | 100 | nmrc | currency_usd | Inpatient general service revenue (hospital + IPF + IRF + SNF + subproviders). |
| `inpatient_revenue_intensive_care` | 1600 | 100 | nmrc | currency_usd | Inpatient intensive-care-type revenue (ICU, CCU, burn, surgical IC, and others). |
| `inpatient_revenue_routine` | 1700 | 100 | nmrc | currency_usd | Inpatient routine-care revenue (sum of general and intensive-care routine revenue). |
| `inpatient_revenue_ancillary` | 1800 | 100 | nmrc | currency_usd | Inpatient ancillary services revenue. |
| `inpatient_revenue_other` | 1900 | 100 | nmrc | currency_usd | Inpatient outpatient-services revenue (services rendered to inpatients through outpatient departments). |
| `inpatient_total_revenue` | 2800 | 100 | nmrc | currency_usd | Inpatient total patient revenue across all service lines. |
| `outpatient_revenue_ancillary` | 1800 | 200 | nmrc | currency_usd | Outpatient ancillary services revenue. |
| `outpatient_revenue_other` | 1900 | 200 | nmrc | currency_usd | Outpatient outpatient-services revenue (non-ancillary outpatient visits). |
| `outpatient_total_revenue` | 2800 | 200 | nmrc | currency_usd | Outpatient total patient revenue. |
| `total_patient_revenue` | 2800 | 300 | nmrc | currency_usd | Grand total patient revenue (sum of inpatient and outpatient). |

## Worksheet `G300000`

| Variable | Line | Column | Source | Type | Description |
|----------|------|--------|--------|------|-------------|
| `net_patient_revenue` | 300 | 100 | nmrc | currency_usd | Net patient revenue — total patient revenues minus allowances and discounts. |
| `total_operating_expenses` | 400 | 100 | nmrc | currency_usd | Total operating expenses. |
| `other_income` | 2500 | 100 | nmrc | currency_usd | Total other operating income. |
| `total_other_expenses` | 2800 | 100 | nmrc | currency_usd | Total other expenses. |
| `donations` | 600 | 100 | nmrc | currency_usd | Charitable donations reported on Worksheet G-3. |
| `investment_income` | 700 | 100 | nmrc | currency_usd | Investment income reported on Worksheet G-3. |

## Worksheet `S100001`

Also read from worksheet code `S100000` at the same line and column. CMS files Worksheet S-10 as `S100000` for cost reporting periods beginning before 2022-10-01 and S-10 Part I as `S100001` after; the bundles map both to the variables below.

| Variable | Line | Column | Source | Type | Description |
|----------|------|--------|--------|------|-------------|
| `total_bad_debt` | 2600 | 100 | nmrc | currency_usd | Total bad debt expense reported on Worksheet S-10 (whole hospital complex). |
| `charity_care_cost` | 2300 | 300 | nmrc | currency_usd | Cost of charity care reported on Worksheet S-10 (whole hospital complex). |
| `uncompensated_care_cost` | 3000 | 100 | nmrc | currency_usd | Total cost of uncompensated care reported on Worksheet S-10 (whole hospital complex). |
| `charity_care_cost_uninsured` | 2300 | 100 | nmrc | currency_usd | Cost of charity care for uninsured patients (S-10 line 23 column 1). |
| `charity_care_cost_insured` | 2300 | 200 | nmrc | currency_usd | Cost of charity care for insured patients (S-10 line 23 column 2). |
| `medicaid_net_revenue` | 200 | 100 | nmrc | currency_usd | Net revenue from Medicaid (S-10 line 2), net of provider taxes; includes DSH/supplemental payments when not separately identifiable. |
| `medicaid_dsh_supplemental_payments` | 500 | 100 | nmrc | currency_usd | Medicaid DSH and supplemental payments not already in line 2, net of associated provider taxes or assessments (S-10 line 5). Negative when provider taxes exceed the payments. |
| `medicaid_cost` | 700 | 100 | nmrc | currency_usd | Medicaid cost, the cost-to-charge ratio times Medicaid charges (S-10 line 7). |
| `medicaid_shortfall` | 800 | 100 | nmrc | currency_usd | Medicaid cost minus Medicaid net revenue and DSH/supplemental payments, floored at zero (S-10 line 8). |
| `unreimbursed_means_tested_cost` | 1900 | 100 | nmrc | currency_usd | Total unreimbursed cost for Medicaid, CHIP and state/local indigent care programs (S-10 line 19). |
| `unreimbursed_and_uncompensated_care_cost` | 3100 | 100 | nmrc | currency_usd | Total unreimbursed and uncompensated care cost, line 19 plus line 30 (S-10 line 31). |
| `charity_care_initial_charges` | 2000 | 300 | nmrc | currency_usd | Initial obligation-of-patients charges for charity care and uninsured discounts. |
| `charity_care_cost_before_payments` | 2100 | 300 | nmrc | currency_usd | Cost of charity care and uninsured discounts before subtracting partial patient payments. |
| `charity_care_partial_payments` | 2200 | 300 | nmrc | currency_usd | Partial payments received from patients approved for charity care. |
| `medicare_bad_debt_reimbursable` | 2700 | 100 | nmrc | currency_usd | Portion of bad debt that is Medicare-reimbursable. |
| `non_medicare_bad_debt_expense` | 2800 | 100 | nmrc | currency_usd | Non-Medicare bad debt expense (total bad debt minus Medicare-reimbursable portion). |
| `non_medicare_bad_debt_cost` | 2900 | 100 | nmrc | currency_usd | Cost of non-Medicare bad debt after applying the cost-to-charge ratio. |
| `cost_to_charge_ratio` | 100 | 100 | nmrc | ratio | Hospital-wide cost-to-charge ratio used to translate Worksheet S-10 charges into costs. |

## Worksheet `S200001`

| Variable | Line | Column | Source | Type | Description |
|----------|------|--------|--------|------|-------------|
| `hospital_name` | 300 | 100 | alpha | string | Legal name of the hospital. |
| `ownership_type` | 2100 | 100 | alpha | string | Type of ownership/control (e.g. voluntary nonprofit, for-profit, government). |
| `chain_name` | 14100 | 100 | alpha | string | Name of the parent chain organization, if the hospital is part of one. |

## Worksheet `S300001`

| Variable | Line | Column | Source | Type | Description |
|----------|------|--------|--------|------|-------------|
| `total_beds` | 1400 | 200 | nmrc | int | Total beds including swing beds and special-care units (ICU, CCU, NICU, etc.). |
| `total_beds_grand` | 2700 | 200 | nmrc | int | Grand total beds including subprovider, SNF, nursing facility, and hospice beds. |
| `total_discharges` | 100 | 1500 | nmrc | int | Total inpatient discharges for adults, pediatrics, and specialty units. |
| `total_bed_days_available` | 100 | 300 | nmrc | int | Total bed-days available during the reporting period. |
| `inpatient_bed_days_utilized` | 100 | 800 | nmrc | int | Total inpatient bed-days utilized during the reporting period. |
| `beds_adult_and_pediatric` | 100 | 200 | nmrc | int | Adult and pediatric beds (Worksheet S-3 Part I line 1). |
| `icu_beds` | 800–899 (sum) | 200 | nmrc | int | Total intensive-care-unit beds, summed across all ICU subcategory lines. |
| `ccu_beds` | 900–999 (sum) | 200 | nmrc | int | Total coronary-care-unit beds, summed across all CCU subcategory lines. |
| `burn_icu_beds` | 1000–1099 (sum) | 200 | nmrc | int | Total burn-intensive-care-unit beds. |
| `surgical_icu_beds` | 1100–1199 (sum) | 200 | nmrc | int | Total surgical-intensive-care-unit beds. |
| `other_special_care_beds` | 1200–1299 (sum) | 200 | nmrc | int | Total other special-care beds (NICU, pediatric ICU, trauma, etc.). |

