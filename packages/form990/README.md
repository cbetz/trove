# form990

Parser for IRS Form 990 XML filings.

Scope is Schedule H: financial assistance and other community benefit, bad debt, facility count.

**Status:** bulk-ZIP discovery and download, a Schedule H XML parser, and return-of-record selection. Output is one row per return with a Schedule H: EIN, organization name, filer city and state, tax period, total revenue and expenses (from the main 990), Part I lines 7a to 7k in three columns each (total expense, direct offsetting revenue, net), the line 7k percentage, Part III bad debt expense, Part V facility count, and provenance (IRS object id, e-file timestamp, amended-return flag, release year, ZIP).

## Usage

```python
from form990 import discover_batches, parse_tax_year, latest_return_per_ein, write_parquet

# Every ZIP the IRS serves for one release year, found by asking the server.
batches = discover_batches(2024)          # ["2024_TEOS_XML_01A", "2024_TEOS_XML_02A", ...]

# Parse tax year 2022 Schedule H returns out of every ZIP in that release.
# ZIPs are handled one at a time; keep_zips=False deletes each after parsing.
df = parse_tax_year(
    2022, 2024,
    keep_zips=False,
    batch_cache_dir="data/parquet/form990/batches",   # resume an interrupted run
    xml_dir="data/raw/form990/xml_ty2022",            # keep each return's XML
)

# Repeat for each release year and concatenate, then pick one return per EIN.
one_per_ein = latest_return_per_ein(df)
write_parquet(df, tax_year=2022)
```

`parse_zip(path)` parses a single ZIP you already have. The parser checks each member for the bytes `IRS990ScheduleH` before invoking lxml, so most of a ZIP is skipped quickly: most filers are not hospitals.

## Finding returns: ZIP discovery, not the index

Returns are located by opening every ZIP in a release and reading each return's own `TaxYr`. The IRS index CSVs are not used to locate them:

- the 2023 index has no batch column at all;
- the 2025 and 2026 indexes label every May return `05A`, although the returns are split across `05A` and `05B` on the server.

`discover_batches(release_year)` probes the server for each month and letter and stops at the first 404. Any other failure (403 when throttled, 429, 5xx, a dropped connection) is retried with a back-off and then raised, so a throttled probe cannot silently shorten the list. `download_index`, `read_index` and `filter_990s_for_tax_year` remain for completeness checks; `tax_periods_for_tax_year` gives the period-end window for a tax year (2022 covers periods ending 2022-12 through 2023-11).

**Tax year 2022 across releases.** The published `schedule_h_2022.parquet` was built from the 2023, 2024, 2025 and 2026 releases (51 ZIPs, about 17 GB, processed one at a time): 849 returns in 2023, 1,464 in 2024, 47 in 2025 and none in 2026. It is not deduplicated; 2,360 returns cover 2,295 EINs.

## Fields

- `ein`, `organization_name`, `filer_city`, `filer_state`, `tax_period_begin`, `tax_period_end`, `tax_year`, `return_version`
- `total_revenue`, `total_expenses`
- For each Part I line 7 row (`financial_assistance_at_cost` 7a, `unreimbursed_medicaid` 7b, `unreimbursed_other_means_tested` 7c, `total_financial_assistance` 7d, `community_health_services` 7e, `health_professions_education` 7f, `subsidized_health_services` 7g, `research` 7h, `cash_and_in_kind_contributions` 7i, `total_other_benefits` 7j, `total_community_benefit` 7k): the bare name is column (e) net, `_gross` is column (c) total expense, `_offset_revenue` is column (d) direct offsetting revenue
- `total_community_benefit_pct` (line 7k column (f), a fraction), `bad_debt_expense`, `hospital_facility_count`
- `object_id` (the IRS e-file object id, from the ZIP member name), `return_ts`, `amended_return`
- `release_year`, `batch_id` (added by `parse_tax_year`)

A blank element on the return is missing in the output; a reported 0 is 0.

## Which return counts: `latest_return_per_ein`

An EIN can have more than one return for a tax year: an amended return, the same return in two releases, or a short-year return next to a full-year one. `latest_return_per_ein` prefers a full-year return (at least 330 days), then the latest period end, then the latest e-file timestamp, then the newest release. `analytics` imports this function, so there is one implementation.

## Schema scope

XPaths target the `http://www.irs.gov/efile` namespace. The Schedule H element names used here have been stable since the 2013v3.0 schema; earlier schemas are not supported.

## ZIP compression

The IRS started using DEFLATE64 (`compress_type=9`) for the 2025 release year. Python's stdlib `zipfile` can index these archives but can't decompress them. The parser falls back to manual local-header reading + `inflate64` for any entry with `compress_type=9`. Earlier releases (DEFLATE, `compress_type=8`) go through stdlib unchanged.
