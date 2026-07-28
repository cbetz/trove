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
| [`hcris`](../packages/hcris/) | CMS Medicare Cost Reports (Hospital 2552-10), with a 44-variable semantic dictionary |
| [`form990`](../packages/form990/) | IRS Form 990 Schedule H, from the bulk-XML ZIPs |
| [`crosswalk`](../packages/crosswalk/) | CCN ↔ EIN linking (3,523 hospitals, 2,385 EINs) |
| [`analytics`](../packages/analytics/) | Composed queries — `community_benefit_gap()` is the cross-form primitive |
| [`sdoh`](../packages/sdoh/) | CDC Social Vulnerability Index; UW Area Deprivation Index (local only) |
| [`fda_sba`](../packages/fda_sba/) | FDA novel drug approvals across CDER and CBER |

## Published data

- **Charity Care Gap Index** — the 99 hospitals where the CMS and IRS charity-care
  figures are cleanly comparable:
  [`artifacts/charity_care_gap_index_2022.md`](../artifacts/charity_care_gap_index_2022.md)
- **Full matched dataset** — 1,334 systems:
  [`artifacts/community_benefit_gap_2022.csv`](../artifacts/community_benefit_gap_2022.csv)
- **Method and caveats** —
  [`artifacts/community_benefit_gap_2022_summary.md`](../artifacts/community_benefit_gap_2022_summary.md)
- **Parquet bundles over HTTPS**, queryable directly from DuckDB — see the
  [README](../README.md).

## Status

See [`CHANGELOG.md`](../CHANGELOG.md) for milestone history. Current: M7 — the ranked
Charity Care Gap Index, with the finding on the front page of the site.
