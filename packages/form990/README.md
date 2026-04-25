# form990

Parser for IRS Form 990 XML filings.

Scope for v1 is Schedule H — hospital community benefit, charity care, bad debt. Handles schema drift across filing years.

**Status:** M3 — index reader, bulk-ZIP downloader, and Schedule H XML parser shipped. Outputs one row per Schedule H filer with EIN, organization name, tax-period dates, total revenue/expenses (from the main 990 body), Part I line 7a–k net community benefit amounts, total community benefit ratio, Part III bad debt expense, and Part V hospital facility count.

## Usage

```python
from form990 import (
    download_index, read_index, filter_990s_for_tax_year,
    download_zip, parse_zip, write_parquet,
)

# Step 1: read the per-release-year index and filter to 990s for the tax year you want.
idx = read_index(download_index(2024))
filings = filter_990s_for_tax_year(idx, tax_year=2022)
batches = filings["XML_BATCH_ID"].unique()  # which ZIPs to pull

# Step 2: download + parse one or more ZIPs.
df = parse_zip(download_zip(2024, "2024_TEOS_XML_01A"))

# Step 3: persist as Parquet partitioned by tax year.
write_parquet(df, tax_year=2022)
```

The parser short-circuits on a cheap byte-level check for `IRS990ScheduleH` before invoking lxml, so iterating a 100 MB ZIP takes well under a second on a laptop — most filers in the bulk feed are not hospitals.

## Schema and tax-year scope

XPaths target the `http://www.irs.gov/efile` namespace. Element names (`FinancialAssistanceAtCostTyp`, `TotalCommunityBenefitsGrp`, etc.) have been stable since TY2013 schema 2013v3.0; pre-2013 paths used a different shape and aren't supported.

**Bootstrap year:** TY2022. Most TY2022 returns appear in the `2024_TEOS_XML_*.zip` release; late filers and amendments trickle into 2025 and 2026 ZIPs. Concat parses across release years and dedup downstream — `parse_tax_year` attaches a `release_year` column so the analytics layer can prefer the most recent version per EIN.

## ZIP compression

The IRS started using DEFLATE64 (`compress_type=9`) for the 2025 release year. Python's stdlib `zipfile` can index these archives but can't decompress them. The parser falls back to manual local-header reading + `inflate64` for any entry with `compress_type=9`. Earlier releases (DEFLATE, `compress_type=8`) go through stdlib unchanged.
