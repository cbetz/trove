# Changelog

Release and milestone history for [trove](https://github.com/cbetz/trove). Milestone dates
are approximate to the month; see `git log` for exact commits.

## Unreleased

FDA section, driven by what the site's search queries were asking for.

**Data (additive).** `fda_approvals_nme_recent` gains 14 columns for CDER rows. From the
drugs@FDA application page: `approval_letter_url`, `review_url` (the approval package's table
of contents) and `submission_classification`; `label_pdf_url` is now filled from the
original-approval row when FDA's annual list did not link a label (159 → 216 of 217 rows).
From FDA's Compilation of CDER NME and New Biologic Approvals: `review_designation`,
`orphan_drug_designation`, `accelerated_approval`, `breakthrough_therapy_designation`,
`fast_track_designation`, `qualified_infectious_disease_product`, the two priority review
voucher columns, `fda_receipt_date`, `dosage_form` and `route_of_administration`. No existing
value changed. CBER rows have none of these.

**New dataset.** FDA's compilation itself, 1,387 CDER novel approvals from 1985 through 2025,
converted from FDA's Excel workbook to `web/data/fda_nme_compilation.csv` and `.parquet`
(`packages/fda_sba/src/fda_sba/compilation.py`, standard-library XLSX reader, no new
dependency). `fda_nme_compilation_source.json` records FDA's file name, date and SHA-256.

**Site.** A page for every approval year 1985–2025 (`/drugs/2023/`), an approval statistics
page (`/drugs/statistics/`), a download page for the compilation (`/drugs/compilation/`),
and three explainers: new molecular entity (NME vs NCE), FDA approval package, Drug Trials
Snapshot. Drug pages open with a plain-language answer and link the label, approval letter
and review documents directly. `/drugs/` now carries a static list of every year and drug
(the search box alone was invisible to crawlers that do not run JavaScript). The Schedule H
explainer gained a section on the IRS instructions and their worksheets.

**For crawlers and agents.** Markdown twins (`index.md`) of every generated page, `llms.txt`,
an explicit `robots.txt`, `dateModified` and sitemap `lastmod` that change only when a page's
content does.

**Known, not fixed here.** The indication text scraped from CBER product pages can start or
end with stray fragments; drug pages now trim it for display and keep it out of the summary
sentence, but `indication` in the data is unchanged. The cached FDA pages behind the per-drug
index were read in May 2026. The index still covers 2021–2024; 2025 approvals appear in the
year list and the compilation but have no per-drug page yet.

## 1.1.0 — 2026-11-19

A correction release. The hospital data was rebuilt, and the way the two figures are
described was revised. Column names are additive: nothing was renamed or removed.

**Corrected: the headline framing.** Earlier versions described IRS Schedule H line 7a and
CMS Worksheet S-10 line 23 as directly comparable ("apples-to-apples", "net-to-net") and
presented a difference as two reports of the same thing that did not match. That was
wrong. The two lines are defined differently:

- Line 7a is financial assistance at cost: column (c) total expense, column (d) direct
  offsetting revenue, column (e) net. The Schedule H instructions (Worksheet 1, line 4)
  have a filer include Medicaid or provider taxes in the line 7a cost when payments from
  an uncompensated care pool or DSH program in its state are intended primarily to offset
  the cost of financial assistance, with the pool revenue reported in column (d).
- S-10 line 23 column 3 is the cost of charity care after patient payments, uninsured
  (column 1) plus insured (column 2). Medicaid DSH and supplemental payments net of
  provider taxes are on S-10 line 5, which is not part of line 23.

The site, README, notes and skills now present the two figures side by side with the
components from each filing, and say that a difference is not by itself evidence that
either filing is incorrect. For the earlier lead example, Yale New Haven Hospital, about
$71.5M of the $77.5M difference is the size of the amount on S-10 line 5; this is a
reconciliation from the filings, not a figure the hospital has stated. Unverified
citations of earlier literature were removed.

**Corrected: hospital data.**

- **Missing is no longer zero.** A hospital with no value on S-10 line 23, or no
  Worksheet S-10 at all, was published with `hcris_charity_care_cost = 0` and a
  difference computed from it (100 rows in the previous release, including The Johns
  Hopkins Hospital). Those values are now empty, with no difference. 159 matched systems
  have no S-10 line 23 figure and 53 have a blank line 7a column (e).
- **The IRS 2023 e-file release is now ingested.** It was skipped before because its index
  has a different layout. The ingest now scans every ZIP of the 2023–2026 releases rather
  than relying on the index: 2,360 tax-year-2022 Schedule H returns.
- **Fiscal periods are matched across the HCRIS FY2022 and FY2023 files.** CMS files a
  cost report under the fiscal year in which its period *begins*. The earlier build
  loaded only the FY2023 file, so a hospital whose year began before October 2022 was set
  against its following year's cost report. Each CCN now gets the report ending closest
  to the 990's period, and `period_aligned` records whether that is within one month.
  (The M4.3 entry below described the CMS file layout incorrectly.)
- **Worksheet S-10 layout change handled.** S-10 is filed as `S100000` for periods
  beginning before 2022-10-01 and as `S100001` (Part I) after; both map to the same
  variables.
- **New component columns** (20 → 51 in the matched table): line 7a columns (c) and (d),
  the S-10 uninsured and insured columns, S-10 line 5, charges and payments, line 7b,
  both fiscal periods, cost report status, the return's object id, release year and
  amended flag, `ccn_list`, `city`, `state`, `crosswalk_ccn_count`, a gross-basis
  difference, and a flag for returns where (c) − (d) does not equal (e).
- **Multi-CCN systems.** A system total is computed only when every CCN has the line;
  otherwise the total is empty and the partial sum is published separately.
- **Return of record.** Where an EIN has several tax-year-2022 returns: a full-year
  return first, then the latest period end, then the latest e-file timestamp.
- **Counts.** Matched 1,334 → 2,099; with both figures 1,295 → 1,904; period-aligned
  372 → 1,797; ranked index 99 → 493 hospitals (48 states); index rows differing by more
  than 50%, 22 → 107. All 99 earlier index rows are still in the index.
- New published files: `hcris_2022_wide.parquet`, and
  `artifacts/community_benefit_gap_2022_sources.json` (CMS extract date 2026-10-02,
  posted 2026-10-05; ZIP hashes; IRS returns by release). The index JSON gained the
  component fields and per-row note codes.
- Smaller fixes: the $500K floor in the summary statistics no longer counts a negative
  figure as passing; a tie between two equally distant cost reports is resolved the same
  way for every CCN under an EIN; the IRS download probe retries on 403/429/5xx instead
  of treating them as "does not exist".

**Corrected: FDA approval dates.** The index is by original approval date, 2021–2024:
217 drugs (192 CDER + 25 CBER), down from 218.

- Tzield: the date was missing (shown as "NaT"); now 2022-11-17.
- Xdemvy: 2023-07-25 → 2023-07-24.
- Elevidys: 2024-01-10 (a supplement approval) → 2023-06-22.
- Ryoncil: 2024-12-19 → 2024-12-18.
- Imlygic removed: its original approval was 2015-10-27. `/drugs/imlygic` redirects to
  `/drugs/`.
- An unparseable or out-of-range date now stops the build instead of being published.

**Skills** (plugin 1.1.0).

- `hcris-analyst` rewritten for the rebuilt data: it uses `period_aligned`, reports a
  missing line as "not reported on this line" rather than zero or "near zero", documents
  the component columns and the FY2022 file, and has a new reference on reading a
  difference from the components. Earlier text that explained missing S-10 values as
  hospitals reporting near-zero charity care was removed.
- `fda-analyst`: fetch helpers that send a descriptive User-Agent (FDA's document host
  redirects default clients to an error page), guidance for reading large review PDFs in
  page ranges, a note for sandboxed environments, and the corrected coverage.

**Site.**

- `/hospitals/` rewritten: both figures with components on every card, state filter,
  search across all 2,099 systems including those with a missing line, links to each
  return on ProPublica and each cost report record on data.cms.gov.
- `/notes/charity-care-gap/` rewritten, with a dated correction note.
- Phone layouts for the tables, keyboard access to index rows, visible focus, a search
  label, and a no-JavaScript fallback with links to the data files.
- `/drugs/` showed approval dates one day early in US time zones; fixed. Per-drug pages
  link to related approvals and show the plugin install.
- The chart is redrawn for 493 hospitals. New social card; the old cards are deleted.
- `vercel.json` sets CORS headers on `/data/` (see `web/README.md`).

## M7 — the Charity Care Gap Index (July 2026)

*The framing and counts in this entry were corrected in 1.1.0; it is kept as history.*

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
