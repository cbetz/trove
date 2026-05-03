# Peer cohort definitions

When the user asks for "peer comparisons" or "how does X stack up," construct a cohort along one or more of these dimensions. None of these are universally right — pick the dimensions that match the question.

## Common cohort dimensions

| Dimension | HCRIS column / source | Notes |
|-----------|------------------------|-------|
| **Bed-size band** | `total_beds` | Common bands: `<100`, `100–299`, `300–599`, `600+`. Bed count is reported on Worksheet S-3 Part I. |
| **State** | `state_code` (HCRIS RPT) | The pivoted bundle doesn't yet expose state directly; join to `crosswalk` (the bundled CBI rows include `state`) or pull from the raw RPT table. |
| **Ownership type** | `ownership_type` | CMS code: `1` voluntary nonprofit church, `2` voluntary nonprofit other, `3` proprietary individual, `4` proprietary partnership, `5` proprietary corporation, `6`–`12` government. For "nonprofit peer comparison" filter to `1` or `2`. |
| **Teaching status** | `teaching_hospital` (CBI crosswalk), or HCRIS Worksheet S-3 line 26 column 14 (intern + resident FTE) | Boolean from the crosswalk is easier; the raw FTE count gives you a more granular signal. |
| **Children's hospital** | `children_hospital` (CBI crosswalk) | Important — children's hospitals don't bill Medicare in volume, so HCRIS S-10 charity care will read near-zero. Don't include them in general charity-care comparisons. |
| **Critical access** | (HCRIS Worksheet S-2) | A small-rural designation — different reimbursement rules. Exclude from large-hospital benchmarks. |
| **Urban / rural** | `urban` (CBI crosswalk) | Boolean. |
| **System chain** | `chain_name` (HCRIS, when present) | For "how does this hospital compare to others in the same system" questions. |
| **Disproportionate share** | (HCRIS Worksheet S-2) | DSH-eligible hospitals have meaningfully different patient mix. |
| **Service-area vulnerability (SVI)** | `svi_overall_pct` (0-100) on the gap dataset, with sub-themes `svi_socio_pct`, `svi_household_pct`, `svi_minority_pct`, `svi_housing_pct` | Useful as an interpretation lens for charity-care numbers — a hospital's charity-care obligation is partly a function of the population it serves. Most useful in *bands*: "low" (≤20), "moderate" (40–60), "high" (≥80). County-level aggregate; loses within-county variation in urban areas. SVI weighs minority status and housing factors more heavily than other deprivation indices, so urban diverse counties may rank "high" even when median income is decent. |

## Useful canned cohorts

- **Major safety-net hospitals**: `total_beds >= 300 AND uncompensated_care_cost > 50_000_000` — typically large public/voluntary hospitals serving low-income populations. The top of this list is well-known: Harris Health, Dallas Co. Hosp. Dist., Grady, NYC H+H, JPS.
- **Academic medical centers**: teaching status = true AND total_beds >= 500. ~150 facilities. The "famous hospital" set most public discourse focuses on.
- **Small rural / critical access**: `total_beds < 50 AND ownership_type IN ('1','2')`. Different operational economics; their charity-care cost dollar figures look small but proportions can be large.
- **Children's hospitals**: from the CBI crosswalk. About 80 facilities. Should be analyzed separately for charity-care because they don't bill Medicare in volume.
- **Hospitals serving high-vulnerability areas**: `svi_overall_pct >= 80` on the gap dataset. Useful when looking at safety-net obligations or community-benefit profiles in context. Pair with bed count to separate "small rural hospital in vulnerable county" from "big urban safety-net hospital in vulnerable county."

## Useful HCRIS aggregate metrics for benchmarking

When showing a hospital alongside a peer cohort, useful comparison columns:

| Metric | Calculation | Why |
|--------|------------|-----|
| Operating margin | `(net_patient_revenue + other_revenue - total_operating_expenses) / (net_patient_revenue + other_revenue)` | Financial health. |
| Charity-care intensity | `charity_care_cost / total_operating_expenses` | How much of the cost base is given as charity. Normalized for size. |
| Uncompensated-care intensity | `uncompensated_care_cost / total_operating_expenses` | Similar but includes bad debt — a broader measure of care provided that didn't generate revenue. |
| Beds per million in catchment | `total_beds` / state population × 1M | Capacity vs. the area served (state-level approx). |
| Occupancy | `inpatient_bed_days_utilized / (total_beds * 365)` | How fully the hospital is used. |

## What NOT to compare across cohorts

- **HCRIS S-10 charity-care to a children's hospital's 990 7a** — HCRIS S-10 only captures Medicare-bill-related charity, which is near-zero for children's hospitals. The 990 7a captures everything. The "gap" is structural, not interesting.
- **Total community benefit (7k) to charity-care cost (S-10)** — these are different concepts. 7k includes research, education, subsidized services. Use 7a for charity-care comparisons.
- **HCRIS dollar figures across very different fiscal-year ends without alignment** — see the alignment filter discussion in `parquet_layout.md`. A hospital's HCRIS FY2023 report and 990 TY2022 may cover entirely different 12-month periods.
