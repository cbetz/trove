# hcris

Parser for CMS Medicare Cost Reports (HCRIS), Hospital form 2552-10.

Raw HCRIS ships as three headerless CSVs per fiscal-year ZIP — `RPT`, `NMRC`, `ALPHA` — in a long-skinny `(rpt_rec_num, wksht_cd, line_num, clmn_num, value)` shape. Field semantics live in a CMS PDF (Provider Reimbursement Manual Chapter 40). This package turns the raw ZIPs into tidy DataFrames with the right dtypes and writes partitioned Parquet.

**Status:** M1 — parser works, no semantic dictionary yet. Columns are still worksheet-coded (`S300001`/`14`/`2`) rather than human-readable names; that's M2.

## Usage

```python
from hcris import download_year, parse_zip, write_parquet

# Fetch one fiscal-year ZIP from CMS (cached locally after first call).
zip_path = download_year(2023, cache_dir="data/raw/hcris")

# Parse into three DataFrames: report-level, numeric cells, alpha cells.
files = parse_zip(zip_path)
print(files.rpt.columns.tolist())    # 18 report-level fields
print(len(files.nmrc), "numeric cells")
print(len(files.alpha), "alpha cells")

# Write to {out_dir}/{rpt,nmrc,alpha}/year=2023/part.parquet.
write_parquet(files, year=2023, out_dir="data/parquet/hcris")
```

## Invariants enforced (from Sacarny's R pipeline)

- `RPT.rpt_rec_num` is unique within a year (reports are identified by this key).
- Every `rpt_rec_num` in NMRC and ALPHA appears in RPT.
- `NMRC.itm_val_num` is never null.
- Worksheet codes (`wksht_cd`) are whitespace-stripped so `"S300001"` and `"S300001  "` compare equal.
- Column numbers (`clmn_num`) are preserved as strings so alpha-suffixed values like `"01A"` survive.

## Known footguns

- `rpt_rec_num` is **not** unique across fiscal years — a late-filed or amended report appears in multiple yearly ZIPs with the same ID. Always qualify queries by `year`.
- CMS rebuilds every yearly ZIP on each quarterly release. The local cache is keyed by filename only; call `download_year(year, force=True)` to refresh.
- `itm_val_str` in ALPHA sometimes has embedded quotes and multi-line values. Read as-is; don't assume single-line records if you do your own parsing.

## Not yet supported

Forms other than 2552-10 (SNF 2540, HHA 1728, Hospice, RHC, Renal), and the pre-2010 2552-96 format. Adding a form is mostly YAML + column lists — see the M-plan.
