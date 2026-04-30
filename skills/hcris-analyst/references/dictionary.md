# HCRIS 2552-10 field dictionary

Every variable trove exposes from the Medicare Cost Report Hospital form, with the canonical (worksheet, line, column) source and a short description. Generated from `packages/hcris/src/hcris/dictionaries/2552-10.yaml`.

**Pivoted Parquet bundle:** `https://troveproject.com/data/hcris_2023_wide.parquet` (one row per hospital, every variable below as a named column).

Total: **44 variables** across 7 worksheets.

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

| Variable | Line | Column | Source | Type | Description |
|----------|------|--------|--------|------|-------------|
| `total_bad_debt` | 2600 | 100 | nmrc | currency_usd | Total bad debt expense reported on Worksheet S-10 (2010 format only). |
| `charity_care_cost` | 2300 | 300 | nmrc | currency_usd | Cost of charity care reported on Worksheet S-10 (2010 format only). |
| `uncompensated_care_cost` | 3000 | 100 | nmrc | currency_usd | Total cost of uncompensated care reported on Worksheet S-10 (2010 format only). |
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

