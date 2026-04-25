# Community Benefit Gap — TY2022 (HCRIS FY2023 × IRS 990 Schedule H TY2022)

Second published version. Adds late-filed and amended TY2022 990s from the IRS 2025 and 2026 release-year ZIPs to the 2024 release ingest, and prefers the most recent release per EIN when amendments exist.

## Method

For every nonprofit hospital system whose EIN appears in both the CBI crosswalk and the IRS 990 Schedule H feed for tax year 2022, we sum the per-facility HCRIS Worksheet S-10 charity care cost across all CCNs that share an EIN, then compare it to that system's Schedule H Part I line 7a "financial assistance at cost" — the figure each form reports for the same underlying concept.

`charity_gap = HCRIS S-10 charity care cost − Schedule H 7a financial assistance at cost`

Positive gap → the hospital reports more charity care to CMS than to the IRS.

## Headline numbers

- **1,334 hospital systems** matched (from 1,481 unique TY2022 990 EINs and 1,730 CCNs in the join)
- **$60.54B** total community benefit reported on Schedule H (Part I 7k, sum across systems)
- **$5.14B** total absolute charity-care gap
- **807 systems (60%)** report MORE charity care to CMS than to the IRS
- **477 systems (36%)** report MORE financial assistance to the IRS than charity care to CMS
- Median absolute gap: $0.84M (the long tail dominates)

## Top 10 absolute gap

| EIN | Hospital | CCNs | HCRIS S-10 charity | 990 Sched H 7a | Gap |
|-----|----------|------|--------------------|----------------|-----|
| 741152597 | Memorial Hermann Health System | 8 | $428.0M | $307.2M | **+$120.8M** |
| 620646012 | St Jude Children's Research Hospital | 1 | $0.0M | $112.1M | **−$112.1M** |
| 741109643 | Ascension Seton | 11 | $223.9M | $132.5M | **+$91.4M** |
| 060646652 | Yale New Haven Hospital | 1 | $35.6M | $113.1M | **−$77.5M** |
| 941196203 | Dignity Health | 22 | $210.3M | $136.9M | **+$73.5M** |
| 591479658 | Adventist Health System/Sunbelt Inc | 3 | $227.9M | $156.5M | **+$71.5M** |
| 364724966 | Northwestern Memorial HealthCare Group | 8 | $138.9M | $67.5M | **+$71.4M** |
| 591726273 | Orlando Health Inc | 2 | $143.2M | $72.6M | **+$70.6M** |
| 314394942 | OhioHealth Corporation | 5 | $136.8M | $68.4M | **+$68.4M** |
| 751837454 | Baylor University Medical Center | 15 | $109.1M | $42.3M | **+$66.8M** |

## How to read the gap

A positive gap (HCRIS > 990) doesn't automatically mean a hospital is hiding community benefit. Plausible reasons the same hospital reports different numbers on each form:

- **Definitional differences.** Schedule H 7a excludes some categories that HCRIS S-10 may include (Medicaid shortfall handling, partial-payment netting, charity vs. uninsured discount classification).
- **Time alignment.** Hospitals' fiscal years often don't match calendar tax years; we use the latest 990 per EIN by release-year then `tax_period_end`, but mismatch up to ~12 months is common.
- **Cost-to-charge ratio (CCR) handling.** HCRIS S-10 applies a hospital-wide CCR; Schedule H allows different cost-step-down approaches.
- **Charity care policy boundaries.** Hospitals can categorize the same patient case as charity care, bad debt, or contractual allowance — this changes which line each cost appears on.

A negative gap (990 > HCRIS) is often legitimate when a hospital files Schedule H but doesn't bill Medicare in volume — children's hospitals (St Jude, Texas Children's, Driscoll, Children's Mercy), specialty cancer centers (City of Hope), and major teaching hospitals with disproportionate non-Medicare populations all show this pattern.

The data is a **starting point** for review, not a definitive accusation. The value is making the comparison computable at scale, where previously every researcher had to reconstruct it from raw filings.

## Files

- [`community_benefit_gap_2022.csv`](community_benefit_gap_2022.csv) — full 1,334-row table, sorted by absolute gap
- [`community_benefit_gap_2022_top50.csv`](community_benefit_gap_2022_top50.csv) — leaderboard

## Coverage and caveats

- **Crosswalk coverage:** ~3,079 of 6,042 HCRIS hospitals appear in the CBI Dec 2024 crosswalk; the other ~50% are mostly for-profit and government hospitals (no 990) or hospitals not in CBI's frozen vintage. 1,334 of 1,481 unique TY2022 990 EINs match the crosswalk.
- **Release-year scope:** TY2022 ingest now spans the 2024, 2025, and 2026 IRS release years (29 ZIPs total). TY2022 amendments filed after the 2026 quarterly cutoff aren't ingested.
- **Amendment handling:** When a TY2022 990 appears in multiple release years, the most recent release-year version wins. 29 Schedule H filers had a TY2022 return in both the 2024 and 2025 releases; we keep the 2025 version.
- **No reconciliation pass:** Hospitals with EINs not yet in CBI's crosswalk aren't matched at all. A self-built CCN↔EIN reconciliation against IRS BMF would close this gap.

Reproduce with `uv run python scripts/build_gap_dataset.py`.
