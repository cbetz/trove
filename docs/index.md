# trove

Open-source parsers, data bundles, and Claude Code skills for underused U.S. public
healthcare datasets. Live at [troveproject.com](https://troveproject.com).

The plain-language explainers for each dataset live on the site rather than here:
[what is HCRIS](https://troveproject.com/docs/hcris/) ·
[what is IRS 990 Schedule H](https://troveproject.com/docs/schedule-h/) ·
[what is an FDA novel drug approval](https://troveproject.com/docs/fda-nme/).

## Packages

| Package | What it parses |
|---|---|
| [`hcris`](../packages/hcris/) | CMS Medicare Cost Reports (Hospital 2552-10), with a 52-variable semantic dictionary |
| [`form990`](../packages/form990/) | IRS Form 990 Schedule H, from the bulk-XML ZIPs |
| [`crosswalk`](../packages/crosswalk/) | CCN ↔ EIN linking (3,523 hospitals, 2,385 EINs) |
| [`analytics`](../packages/analytics/) | Composed queries — `community_benefit_gap()` is the cross-form primitive |
| [`sdoh`](../packages/sdoh/) | CDC Social Vulnerability Index; UW Area Deprivation Index (local only) |
| [`fda_sba`](../packages/fda_sba/) | FDA novel drug approvals across CDER and CBER |

## Published data

- **Ranked index** — IRS Schedule H line 7a and CMS Worksheet S-10 line 23 side by side
  for the 493 hospitals, in 48 states, where one facility files both for the same fiscal
  period, with the components from each filing:
  [`artifacts/charity_care_gap_index_2022.md`](../artifacts/charity_care_gap_index_2022.md)
- **Full matched dataset** — 2,099 systems, 1,904 with both figures; a missing line is
  empty, never `0`:
  [`artifacts/community_benefit_gap_2022.csv`](../artifacts/community_benefit_gap_2022.csv)
- **Method, funnel and caveats** —
  [`artifacts/community_benefit_gap_2022_summary.md`](../artifacts/community_benefit_gap_2022_summary.md)
- **FDA novel drug approvals** — 331 approvals, 2021–2026 (295 CDER + 36 CBER):
  [`artifacts/fda_approvals_nme_recent.csv`](../artifacts/fda_approvals_nme_recent.csv)
- **Parquet files over HTTPS**, queryable directly from DuckDB — see the
  [README](../README.md).

## Status

See [`CHANGELOG.md`](../CHANGELOG.md) for release history. Current: 1.3.0 (2026-11-28),
which added 2026 FDA approvals to date and re-read every FDA document link. 1.1.0
(2026-11-19) rebuilt the hospital data (missing values no longer published as zero, the 2023
IRS release and the CMS FY2022 file added, component columns added) and revised how the two
figures are described: they are defined differently and are shown side by side with their
components.
