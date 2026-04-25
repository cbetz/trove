# Community Benefit Gap — TY2022 (HCRIS FY2023 × IRS 990 Schedule H TY2022)

The first published version of this dataset.

## Method

For every nonprofit hospital system whose EIN appears in both the CBI crosswalk and the IRS 990 Schedule H feed for tax year 2022, we sum the per-facility HCRIS Worksheet S-10 charity care cost across all CCNs that share an EIN, then compare it to that system's Schedule H Part I line 7a "financial assistance at cost" — the figure each form reports for the same underlying concept.

`charity_gap = HCRIS S-10 charity care cost − Schedule H 7a financial assistance at cost`

Positive gap → the hospital reports more charity care to CMS than to the IRS.

## Headline numbers

- **1,317 hospital systems** matched (from 1,459 unique 990 EINs and 3,079 CCNs in the crosswalk)
- **$58.71B** total community benefit reported on Schedule H (Part I 7k, sum across systems)
- **$5.02B** total absolute charity-care gap
- **799 systems (61%)** report MORE charity care to CMS than to the IRS
- **470 systems (36%)** report MORE financial assistance to the IRS than charity care to CMS
- Median absolute gap: $0.16M (the long tail dominates)

## Top 10 absolute gap

| EIN | Hospital | CCNs | HCRIS S-10 charity | 990 Sched H 7a | Gap |
|-----|----------|------|--------------------|----------------|-----|
| 741152597 | Memorial Hermann Kingwood | 8 | $428.0M | $307.2M | **+$120.8M** |
| 620646012 | St Jude Children's Research | 1 | $0.0M | $112.1M | -$112.1M |
| 741109643 | Ascension Seton Edgar B Davis | 11 | $223.9M | $132.5M | +$91.4M |
| 060646652 | Yale New Haven Hospital | 1 | $35.6M | $113.1M | -$77.5M |
| 941196203 | Arizona Orthopedic Surgical | 22 | $210.3M | $136.9M | +$73.5M |
| 591479658 | AdventHealth Wauchula | 3 | $227.9M | $156.5M | +$71.5M |
| 364724966 | Valley West Community Hospital | 8 | $138.9M | $67.5M | +$71.4M |
| 591726273 | Orlando Health | 2 | $143.2M | $72.6M | +$70.6M |
| 314394942 | Riverside Methodist Hospital | 5 | $136.8M | $68.4M | +$68.4M |
| 751837454 | Texas Spine and Joint Hospital | 15 | $109.1M | $42.3M | +$66.8M |

## How to read the gap

A positive gap (HCRIS > 990) doesn't automatically mean a hospital is hiding community benefit. Plausible reasons the same hospital reports different numbers on each form:

- **Definitional differences.** Schedule H 7a excludes some categories that HCRIS S-10 may include (Medicaid shortfall handling, partial-payment netting, charity vs. uninsured discount classification).
- **Time alignment.** Hospitals' fiscal years often don't match calendar tax years; we use the latest 990 per EIN by `tax_period_end`, but mismatch up to ~12 months is common.
- **Cost-to-charge ratio (CCR) handling.** HCRIS S-10 applies a hospital-wide CCR; Schedule H allows different cost-step-down approaches.
- **Charity care policy boundaries.** Hospitals can categorize the same patient case as charity care, bad debt, or contractual allowance — this changes which line each cost appears on.

A negative gap (990 > HCRIS) is often legitimate when a hospital files Schedule H but doesn't bill Medicare in volume — children's hospitals (St Jude, Texas Children's, Driscoll, Children's Mercy), specialty cancer centers (City of Hope), and major teaching hospitals with disproportionate non-Medicare populations all show this pattern.

The data is a **starting point** for review, not a definitive accusation. The value is making the comparison computable at scale, where previously every researcher had to reconstruct it from raw filings.

## Files

- [`community_benefit_gap_2022.csv`](community_benefit_gap_2022.csv) — full 1,317-row table, sorted by absolute gap
- [`community_benefit_gap_2022_top50.csv`](community_benefit_gap_2022_top50.csv) — leaderboard

## Caveats and known gaps

- **Coverage:** 3,079 of 6,042 HCRIS hospitals appear in the CBI crosswalk; the other ~50% are mostly for-profit and government hospitals (no 990) or niche hospitals not in CBI's 2024 vintage. 1,329 of 1,459 990 EINs match the crosswalk.
- **Bootstrap pair only:** This is HCRIS FY2023 vs. 990 TY2022 from one IRS release year. Late-filed TY2022 990s in 2025/2026 release ZIPs aren't yet ingested.
- **No reconciliation pass:** Hospitals with EINs not yet in CBI's crosswalk aren't matched at all. A self-built CCN↔EIN reconciliation against IRS BMF would close this gap.

Reproduce with `uv run python scripts/build_gap_dataset.py`.
