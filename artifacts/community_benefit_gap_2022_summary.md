# Community Benefit Gap — TY2022 (HCRIS FY2023 × IRS 990 Schedule H TY2022)

Third published version (M4.3). Adds source-XML validation, per-row fiscal-year alignment signals, and an aligned-only default view at troveproject.com.

## Headline caveat — read this first

The full dataset includes **1,334 matched systems** at the EIN level. Of those:

- **1,295 are computable** — both Schedule H 7a (financial assistance at cost) and HCRIS S-10 (charity care cost) are present so a `charity_gap` is defined. The other 39 have a blank 990 7a and are matched but not compared.
- **372 of the 1,295 (29%) are period-aligned** within 1 month — HCRIS fiscal-year end ≈ 990 tax-period end. Alignment is what establishes that the two filings cover the same fiscal year; without it, you're comparing different years. About 65% of computable rows are exactly 12 months apart because HCRIS uses the federal-fiscal-year reporting cycle as its file naming, not the underlying period covered.
- **228 of the 372 also have both filings ≥ $500K**. This is a *materiality / noise floor*, not a comparability test — the 144 aligned-but-sub-$500K systems are equally comparable, just smaller in dollar terms.

The full CSV below contains every matched row, computable and not; use `hcris_fy_end_dt`, `sched_h_tax_period_end`, and the presence/absence of `sched_h_financial_assistance_at_cost` to filter as appropriate.

## Method

For every nonprofit hospital system whose EIN appears in both the CBI crosswalk and the IRS 990 Schedule H feed for tax year 2022, we sum the per-facility HCRIS Worksheet S-10 charity care cost across all CCNs that share an EIN, then compare it to that system's Schedule H Part I line 7a "financial assistance at cost" — the related figure each form reports for the same underlying activity.

`charity_gap = HCRIS S-10 charity care cost − Schedule H 7a financial assistance at cost`

Positive gap → the hospital reports more charity care to CMS than to the IRS.

## Headline numbers

**Aligned + material subset (228 systems — the apples-to-apples view):**

- HCRIS and 990 fiscal periods overlap within 1 month, and both filings ≥ $500K
- Median absolute proportional gap: **25.1%** (typical disagreement is large)
- **53 systems (23%)** disagree by more than 50% — the cases worth a closer look
- **$1.08B** total absolute gap on this subset against **$14.21B** Schedule H community benefit reported (a 7.6% reconciliation delta)

**Aligned-only subset (372 systems, including 144 below the $500K materiality floor):**

- HCRIS and 990 periods within 1 month
- 27.9% of the 1,334 matched / 28.7% of the 1,295 computable

**Full matched set (1,334 systems, mostly misaligned by 12 months):**

- 1,334 matched (from 1,481 unique TY2022 990 EINs and 1,730 CCNs in the join)
- 1,295 computable; 39 have a blank Schedule H 7a
- 835 of the computable set are exactly 12 months off — comparing different years
- $60.54B total Schedule H community benefit reported across all matched
- The "$5B absolute gap on the full set" figure that earlier versions of this dataset published is structurally misleading because most of those dollars come from misaligned-period comparisons. The aligned-subset $1.08B / 7.6%-of-CB figure is the defensible version.

## Distribution of disagreement on the aligned + material subset (228 systems)

This is a lookup tool, not a leaderboard — the per-row data is in the CSV, but we don't publish a curated "top hospitals by gap" ranking. Distribution of the disagreement instead:

**Absolute dollar gap (`|charity_gap|`):**

| P25 | P50 (median) | P75 | P90 | Max |
|-----|--------------|-----|-----|-----|
| $0.3M | $1.2M | $4.3M | $12.4M | $77.5M |

**Proportional gap (`|charity_gap| / max(HCRIS, 990)`):**

| P25 | P50 (median) | P75 | P90 | Max |
|-----|--------------|-----|-----|-----|
| 12.0% | 25.1% | 46.7% | 62.8% | 93.7% |

The full per-system data is in `community_benefit_gap_2022.csv` for anyone who wants to compute their own top-N or filter to a specific cohort. The site at troveproject.com lets you look up any specific hospital by name or EIN to see its detail card.

## How to read the gap

A positive gap (HCRIS > 990) doesn't automatically mean a hospital is hiding community benefit. Plausible reasons the same hospital reports different numbers on each form:

- **Definitional differences.** Schedule H 7a excludes some categories that HCRIS S-10 may include (Medicaid shortfall handling, partial-payment netting, charity vs. uninsured discount classification).
- **Time alignment.** Hospitals' fiscal years often don't match calendar tax years; we use the latest 990 per EIN by release-year then `tax_period_end`, but mismatch up to ~12 months is common.
- **Cost-to-charge ratio (CCR) handling.** HCRIS S-10 applies a hospital-wide CCR; Schedule H allows different cost-step-down approaches.
- **Charity care policy boundaries.** Hospitals can categorize the same patient case as charity care, bad debt, or contractual allowance — this changes which line each cost appears on.

A negative gap (990 > HCRIS) is often legitimate when a hospital files Schedule H but doesn't bill Medicare in volume — children's hospitals (St Jude, Texas Children's, Driscoll, Children's Mercy), specialty cancer centers (City of Hope), and major teaching hospitals with disproportionate non-Medicare populations all show this pattern.

The data is a **starting point** for review, not a definitive accusation. The value is making the comparison computable at scale, where previously every researcher had to reconstruct it from raw filings.

## Files

- [`community_benefit_gap_2022.csv`](community_benefit_gap_2022.csv) — full 1,334-row table (alphabetical by system name)

## Home-county SVI columns (proxy)

Each row carries `svi_overall_pct` (0-100 overall summary) plus four sub-theme percentiles: `svi_socio_pct`, `svi_household_pct`, `svi_minority_pct`, `svi_housing_pct`. These are county-level CDC/ATSDR Social Vulnerability Index 2022 ranks, joined onto the system via the home county of each HCRIS-reporting facility, then aggregated via median across the system's facility-county SVI values for multi-county systems. Coverage: ~98% of matched systems (the unmatched fraction lacks a `county_fips` in the crosswalk).

This is a **home-county proxy**, not a true catchment-area measure. Hospital service areas typically extend beyond the home county, and within-county variation is invisible at this resolution. Treat as a directional indicator of the population the hospital is most likely serving.

CDC SVI is US government work, public-domain. Source: https://www.atsdr.cdc.gov/place-health/php/svi/index.html.

## Coverage and caveats

- **Fiscal-year alignment:** The biggest caveat. HCRIS labels reports by federal fiscal reporting cycle, not fiscal period. Of 1,295 computable systems, 372 (29%) have HCRIS and 990 periods within 1 month; 835 (64%) are exactly 12 months apart because their HCRIS "FY2023" report covers the year following their TY2022 990. The alignment heuristic is end-date-based — a proxy for period overlap, not a proof of it. The site at troveproject.com surfaces this per-row and defaults to the aligned subset. **v2 (planned):** per-hospital matching across HCRIS reporting cycles 2022/2023/2024 to expand the well-aligned set substantially.
- **Validation:** spot-checked 6 EINs (Memorial Hermann, St Jude, Yale, Western Regional, UVA Prince William, CHI St Vincent) against the source IRS XML — exact-to-the-dollar matches in all cases. Parser is verified clean. Bug reports welcome at github.com/cbetz/trove/issues.
- **Crosswalk coverage:** ~3,079 of 6,042 HCRIS hospitals appear in the CBI Dec 2024 crosswalk; the other ~50% are mostly for-profit and government hospitals (no 990) or hospitals not in CBI's frozen vintage. 1,334 of 1,481 unique TY2022 990 EINs match the crosswalk.
- **Release-year scope:** TY2022 ingest now spans the 2024, 2025, and 2026 IRS release years (29 ZIPs total). TY2022 amendments filed after the 2026 quarterly cutoff aren't ingested.
- **Amendment handling:** When a TY2022 990 appears in multiple release years, the most recent release-year version wins. 29 Schedule H filers had a TY2022 return in both the 2024 and 2025 releases; we keep the 2025 version.
- **No reconciliation pass:** Hospitals with EINs not yet in CBI's crosswalk aren't matched at all. A self-built CCN↔EIN reconciliation against IRS BMF would close this gap.

Reproduce with `uv run python scripts/build_gap_dataset.py`.
