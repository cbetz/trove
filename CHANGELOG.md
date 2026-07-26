# Changelog

Milestone history for [trove](https://github.com/cbetz/trove). Dates are approximate to the
month; see `git log` for exact commits.

## M7 — the Charity Care Gap Index (July 2026)

The site leads with the finding instead of a shelf label. New `scripts/build_gap_index.py`
derives a credibility-hardened ranking from the full matched dataset — the subset where a
cross-form difference is genuinely apples-to-apples: single reporting facility (one CCN under
one EIN), filing periods ending within one month of each other, both figures ≥ $1M, and total
expenses agreeing within 5%. **99 of 1,295 computable systems clear that bar; 22 differ by
more than 50%.**

Deliberately *not* a naive top-N: the largest raw gaps are dominated by multi-CCN systems
filing under one EIN with misleading single-facility names, and by rows whose two filings
cover different fiscal years.

- `/hospitals/` — ranked index as the default view, search second, per-hospital shareable
  `#h=<einKey>` links
- `/notes/charity-care-gap/` — the finding written up, with why the two numbers legitimately
  differ and links to both source filings
- `/notes/` — hub for findings
- New outputs: `artifacts/charity_care_gap_index_2022.md`,
  `web/data/charity_care_gap_index_2022.json`

**Fixed:** `community_benefit_pct_of_expenses` was `0` for 1,320 of 1,334 rows and `inf` for 8.
The ratio was emitted as a fraction and the published CSV's blanket `float_format="%.0f"`
then rounded every float column to zero decimals; the corruption had propagated to the live
site. Ratios are now percentages (0–100) with guarded denominators, and the metric is split
into a same-form measure (`community_benefit_pct_of_expenses`, the one to quote) and a
cross-form sanity check (`community_benefit_pct_of_hcris_expenses`). No dollar figure changed.

## M6 — multi-area site (May 2026)

Two live areas at troveproject.com — `/drugs` and `/hospitals` — each with its own
search-first lookup page, methodology, and Claude skill. New `fda_sba` package indexes FDA
Novel Drug Approvals 2021–2024; new `fda-analyst` skill reads approval-package PDFs at query
time. Adding an area is now a package + a page + a skill.

- **v0.3** — CBER cell and gene therapy approvals ingested (26 products: Lenmeldy, Casgevy,
  Lyfgenia, and others), bringing coverage to 218 drugs across both regulatory centers
- **v0.2** — sponsor extraction from the drugs@FDA overview
- Per-drug static pages (218), sitemap, `/docs/` glossary, `/skills/` hub

## M5.2 — CDC Social Vulnerability Index (May 2026)

SVI 2022 county-level added to `sdoh` and wired through to the public bundles and the site's
detail card. Each row shows a service-area signal — e.g. *"81st national percentile — high
social vulnerability in the system's home county"*. SVI is fully public domain, so unlike ADI
it ships in the public CSV / Parquet / JSON. Home-county proxy only, not a service-area
measure.

## M5.1 — `sdoh` package (May 2026)

`county_adi_from_block_group()` added. ADI flows through the *local* pipeline only — UW's
non-sublicensable terms mean it cannot appear in the public bundles.

## M5 — `hcris-analyst` Claude skill (May 2026)

Natural-language queries against HCRIS + 990 + the matched dataset, powered by
DuckDB-over-HTTPS against three Parquet bundles served from troveproject.com. The skill
bundle at `skills/hcris-analyst/` ships SKILL.md plus reference docs: field dictionary,
peer-cohort definitions, Schedule H map, and runnable example queries.

## M4.3 — validation and alignment signals (May 2026)

Validation pass against IRS source XML (6 spot-checks, all exact). Per-row alignment signals
(HCRIS fiscal-year end vs. 990 tax-period end). Default view filtered to the aligned and
material subset. ProPublica deep links per row.

This milestone retired a structurally invalid headline: HCRIS names its files by federal
*reporting cycle*, not by the period covered, so for July–June filers the "FY2023" file holds
a report ending June 2024 — 12 months later than the TY2022 990. 64% of matched systems are
12 months apart. Period alignment became a first-class, surfaced signal.

## M4.2 — full TY2022 coverage (May 2026)

Ingest expanded to the 2024 + 2025 + 2026 IRS release years to capture late filers and
amendments (latest release wins per EIN). The `form990` parser gained DEFLATE64 support —
the IRS switched to `compress_type=9` in the 2025 release, which Python's stdlib `zipfile`
can index but not decompress.

## M4.1 — first published matched dataset (April 2026)

TY2022 matched hospital dataset from the 2024 release year alone: 1,317 systems.

## M4 — the cross-form primitive (April 2026)

`crosswalk` package and `analytics.community_benefit_gap()`.

## M3 — Schedule H parser (April 2026)

`form990` Schedule H parser and full TY2022 ingest.

## M2.5 — dictionary expansion (April 2026)

HCRIS semantic dictionary expanded to 44 variables.

## M2 — wide pivot (April 2026)

`hcris.pivot_wide()` and semantic dictionary v1 — the YAML mapping from
`(wksht_cd, line_num, clmn_num)` to named, described, unit-carrying variables.

## M1 — HCRIS parser (April 2026)

`hcris` parser for Hospital form 2552-10.
