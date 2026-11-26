# Peer cohorts: what the bundles can and cannot support

When a user asks how a hospital looks next to similar hospitals, build the cohort from columns that exist. Say which dimensions you used. Several dimensions people expect (teaching status, children's hospitals, critical access, staffing) are not in the published bundles; say so instead of approximating silently.

## Dimensions available in the published bundles

| Dimension | Column | Where | Notes |
|---|---|---|---|
| Bed size | `total_beds` | `hcris_2022_wide`, `hcris_2023_wide` | Worksheet S-3 Part I line 14 column 2. Null on a small share of reports. Common bands: under 100, 100–299, 300–599, 600 and over. |
| Type of control | `ownership_type` | HCRIS wide | CMS code from Worksheet S-2 Part I line 21, stored as text. Table below. |
| Chain | `chain_name` | HCRIS wide | Home-office or chain name when the report gives one; null for about a third of reports. Free text, so spelling varies. |
| Size by dollars | `total_operating_expenses`, `net_patient_revenue` | HCRIS wide | Worksheet G-3. |
| State and city | `state`, `city` | `community_benefit_gap_2022` only | Lead facility of a matched nonprofit EIN. The HCRIS wide files have no state column. |
| Single hospital or system | `ccn_count` | matched table | 1 means one CCN with a cost report under the EIN. |
| Home-county SVI | `svi_overall_pct` and four theme columns | matched table | CDC/ATSDR SVI 2022 percentile, 0–100. A county-level proxy, not a service area. Null for Connecticut rows and a few others. |
| Cost report status | `rpt_status` / `hcris_report_status` | both | Useful to exclude as-submitted reports from a comparison. |

### Type of control codes (`ownership_type`)

From the CMS Provider Reimbursement Manual, Part 2, chapter 40, section 4004.1 (Worksheet S-2 Part I, line 21):

| Code | Type of control |
|---|---|
| 1 | Voluntary nonprofit, church |
| 2 | Voluntary nonprofit, other |
| 3 | Proprietary, individual |
| 4 | Proprietary, corporation |
| 5 | Proprietary, partnership |
| 6 | Proprietary, other |
| 7 | Governmental, federal |
| 8 | Governmental, city-county |
| 9 | Governmental, county |
| 10 | Governmental, state |
| 11 | Governmental, hospital district |
| 12 | Governmental, city |
| 13 | Governmental, other |

For a nonprofit cohort use `ownership_type IN ('1', '2')`. The code is what the hospital entered on its cost report; it is not the same test as "files a Form 990".

## Dimensions that need the repository clone

The CCN-to-EIN crosswalk carries per-CCN flags that are not published under `/data/`. After `git clone --depth 1 https://github.com/cbetz/trove` they are in `trove/packages/crosswalk/src/crosswalk/data/cbi.parquet`:

- `teaching_hospital`, `children_hospital`, `urban`, `church_affiliated` (boolean)
- `bed_size_band`, `bed_count`, `state`, `county_fips`

These flags come from Community Benefit Insight's December 2024 list and cover nonprofit hospitals only. Join on `ccn = prvdr_num`.

## Not available anywhere in trove

- Staffing, FTEs, wages, interns and residents counts.
- Critical access, sole community or Medicare DSH designation.
- Quality, outcomes, readmissions, patient experience.
- Payer mix beyond the Medicaid and charity lines of Worksheet S-10.

## Useful ratios

| Metric | Calculation | Notes |
|---|---|---|
| Charity care cost as a share of expenses | `charity_care_cost / total_operating_expenses` | S-10 line 23 column 3 over G-3 line 4. Null when the report has no line 23. |
| Uncompensated care as a share of expenses | `uncompensated_care_cost / total_operating_expenses` | S-10 line 30: line 23 column 3 plus line 29 (non-Medicare and non-reimbursable Medicare bad debt). |
| Occupancy | `inpatient_bed_days_utilized / total_bed_days_available` | Both from Worksheet S-3 Part I line 1 (adults and pediatrics), so it excludes special-care units. |
| Community benefit as a share of expenses | `community_benefit_pct_of_expenses` | Schedule H line 7k over the 990's own total expenses, 0–100. |

## Cautions when comparing

- **Missing is not zero.** Hospitals with no Worksheet S-10, or an S-10 with line 23 blank, have a null `charity_care_cost`. In the matched table that includes most Maryland hospitals and most children's hospitals. Leave them out of a charity-care ratio and say how many were left out; do not count them as zero and do not describe them as "low".
- **Two files, two periods.** A CCN usually has a report in each HCRIS file. Pick one period per hospital before ranking or averaging, or the same hospital is counted twice.
- **Line 7k is not charity care.** Schedule H line 7k includes Medicaid, education and research. Set line 7a, not 7k, next to S-10 line 23.
- **Unaligned periods.** For cross-form comparisons keep `period_aligned` rows only.
- **System rows.** A matched row with `ccn_count > 1` sums several cost reports. Do not rank it against single hospitals without saying so.
