# Community Benefit Gap — TY2022 (HCRIS FY2023 × IRS 990 Schedule H TY2022)

Third published version (M4.3). Adds source-XML validation, per-row fiscal-year alignment signals, and an aligned-only default view at troveproject.com.

## Headline caveat — read this first

The full dataset includes **1,334 matched systems** at the EIN level. Of those:

- **1,295 are computable** — both Schedule H 7a (financial assistance at cost) and HCRIS S-10 (charity care cost) are present so a `charity_gap` is defined. The other 39 have a blank 990 7a and are matched but not compared.
- **370 of the 1,295 (29%) are period-aligned** within 1 month — HCRIS fiscal-year end ≈ 990 tax-period end. Alignment is what establishes that the two filings cover the same fiscal year; without it, you're comparing different years. The remaining ~64% of computable rows are exactly 12 months apart because HCRIS uses the federal-fiscal-year reporting cycle as its file naming, not the underlying period covered.
- **228 of the 370 also have both filings ≥ $500K**. This is a *materiality / noise floor*, not a comparability test — the 142 aligned-but-sub-$500K systems are equally comparable, just smaller in dollar terms.

The full CSV below contains every matched row, computable and not; use `hcris_fy_end_dt`, `sched_h_tax_period_end`, and the presence/absence of `sched_h_financial_assistance_at_cost` to filter as appropriate.

## Method

For every nonprofit hospital system whose EIN appears in both the CBI crosswalk and the IRS 990 Schedule H feed for tax year 2022, we sum the per-facility HCRIS Worksheet S-10 charity care cost across all CCNs that share an EIN, then compare it to that system's Schedule H Part I line 7a "financial assistance at cost" — the figure each form reports for the same underlying concept.

`charity_gap = HCRIS S-10 charity care cost − Schedule H 7a financial assistance at cost`

Positive gap → the hospital reports more charity care to CMS than to the IRS.

## Headline numbers

**Aligned + material subset (228 systems — the apples-to-apples view):**

- HCRIS and 990 fiscal periods overlap within 1 month, and both filings ≥ $500K
- Median absolute proportional gap: **25.1%** (typical disagreement is large)
- **53 systems (23%)** disagree by more than 50% — the cases worth a closer look
- **$1.08B** total absolute gap on this subset against **$14.21B** Schedule H community benefit reported (7.6% in dispute)

**Aligned-only subset (370 systems, including 142 below the $500K materiality floor):**

- HCRIS and 990 periods within 1 month
- 27.7% of the 1,334 matched / 28.6% of the 1,295 computable

**Full matched set (1,334 systems, mostly misaligned by 12 months):**

- 1,334 matched (from 1,481 unique TY2022 990 EINs and 1,730 CCNs in the join)
- 1,295 computable; 39 have a blank Schedule H 7a
- 855 of the computable set are 11–13 months off — comparing different years
- $60.54B total Schedule H community benefit reported across all matched
- The "$5B absolute gap on the full set" figure that earlier versions of this dataset published is structurally misleading because most of those dollars come from misaligned-period comparisons. The aligned-subset $1.08B / 7.6%-of-CB figure is the defensible version.

## Top 10 — aligned periods, ranked by absolute dollar gap

These are the cases where HCRIS and 990 cover the same fiscal year and both reported ≥ $500K. Largest absolute disagreements (signed):

| EIN | Hospital | CCNs | HCRIS S-10 charity | 990 Sched H 7a | Gap |
|-----|----------|------|--------------------|----------------|-----|
| 060646652 | Yale New Haven Hospital | 1 | $35.6M | $113.1M | **−$77.5M** |
| 591726273 | Orlando Health Inc | 2 | $143.2M | $72.6M | **+$70.6M** |
| 581954432 | Northside Hospital Inc | 5 | $293.1M | $358.6M | **−$65.5M** |
| 593458145 | Florida Health Sciences Center (Tampa General) | 1 | $102.4M | $51.0M | **+$51.3M** |
| 590910342 | Baptist Hospital of Miami | 1 | $27.3M | $69.1M | **−$41.8M** |
| 900656139 | Mass General Brigham | 10 | $76.5M | $110.9M | **−$34.4M** |
| 811723202 | Prisma Health-Upstate | 7 | $143.2M | $109.1M | **+$34.0M** |
| 592650456 | Lakeland Regional Medical Center | 1 | $49.3M | $15.6M | **+$33.6M** |
| 566017737 | WakeMed | 2 | $89.4M | $116.0M | **−$26.7M** |
| 912155626 | UMass Memorial Health Care | 4 | $27.8M | $6.4M | **+$21.4M** |

## Top 10 — aligned periods, ranked by proportional gap

| EIN | Hospital | CCNs | HCRIS S-10 charity | 990 Sched H 7a | % gap |
|-----|----------|------|--------------------|----------------|-------|
| 320197974 | Western Regional Medical Center | 1 | $18.1M | $1.1M | **+93.7%** |
| 941634554 | Oroville Hospital | 1 | $1.1M | $8.8M | **−87.4%** |
| 721025017 | Baton Rouge General Medical Center | 1 | $1.8M | $12.1M | **−85.1%** |
| 060646844 | Saint Mary's Hospital | 1 | $3.4M | $0.5M | **+84.7%** |
| 060646659 | Greenwich Hospital | 1 | $4.0M | $23.6M | **−83.1%** |
| 951903935 | PIH Health Downey Hospital | 1 | $2.8M | $0.6M | **+80.0%** |
| 060646704 | Lawrence Memorial Hospital | 1 | $4.8M | $21.1M | **−77.3%** |
| 912155626 | UMass Memorial Health Care | 4 | $27.8M | $6.4M | **+77.0%** |
| 222674014 | Exeter Hospital | 1 | $2.5M | $0.6M | **+76.8%** |
| 010211501 | Eastern Maine Medical Center | 1 | $7.6M | $1.8M | **+76.6%** |

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

- **Fiscal-year alignment:** The biggest caveat. HCRIS labels reports by federal fiscal reporting cycle, not fiscal period. Of 1,295 computable systems, 370 (29%) have HCRIS and 990 periods within 1 month; 855 (66%) are exactly 12 months apart because their HCRIS "FY2023" report covers the year following their TY2022 990. The alignment heuristic is end-date-based — a proxy for period overlap, not a proof of it. The site at troveproject.com surfaces this per-row and defaults to the aligned subset. **v2 (planned):** per-hospital matching across HCRIS reporting cycles 2022/2023/2024 to expand the well-aligned set substantially.
- **Validation:** spot-checked 6 EINs (Memorial Hermann, St Jude, Yale, Western Regional, UVA Prince William, CHI St Vincent) against the source IRS XML — exact-to-the-dollar matches in all cases. Parser is verified clean. Bug reports welcome at github.com/cbetz/trove/issues.
- **Crosswalk coverage:** ~3,079 of 6,042 HCRIS hospitals appear in the CBI Dec 2024 crosswalk; the other ~50% are mostly for-profit and government hospitals (no 990) or hospitals not in CBI's frozen vintage. 1,334 of 1,481 unique TY2022 990 EINs match the crosswalk.
- **Release-year scope:** TY2022 ingest now spans the 2024, 2025, and 2026 IRS release years (29 ZIPs total). TY2022 amendments filed after the 2026 quarterly cutoff aren't ingested.
- **Amendment handling:** When a TY2022 990 appears in multiple release years, the most recent release-year version wins. 29 Schedule H filers had a TY2022 return in both the 2024 and 2025 releases; we keep the 2025 version.
- **No reconciliation pass:** Hospitals with EINs not yet in CBI's crosswalk aren't matched at all. A self-built CCN↔EIN reconciliation against IRS BMF would close this gap.

Reproduce with `uv run python scripts/build_gap_dataset.py`.
