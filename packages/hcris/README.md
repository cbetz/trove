# hcris

Parser for CMS Medicare Cost Reports (HCRIS), Hospital form 2552-10.

Raw HCRIS ships as three headerless CSVs per fiscal-year ZIP — `RPT`, `NMRC`, `ALPHA` — in a long-skinny `(rpt_rec_num, wksht_cd, line_num, clmn_num, value)` shape. Field semantics live in a CMS PDF (Provider Reimbursement Manual Chapter 40). This package turns the raw ZIPs into tidy DataFrames with the right dtypes and writes partitioned Parquet.

**Status:** M2 — parser plus a 15-variable semantic dictionary for the fields most people actually want (hospital name, ownership, beds, discharges, revenue, operating expenses, uncompensated care). `pivot_wide()` turns the raw long-skinny NMRC/ALPHA into one row per report with named columns.

## Usage

```python
from hcris import download_year, parse_zip, pivot_wide, write_parquet

# Fetch one fiscal-year ZIP from CMS (cached locally after first call).
zip_path = download_year(2023, cache_dir="data/raw/hcris")

# Parse into three DataFrames: report-level, numeric cells, alpha cells.
files = parse_zip(zip_path)

# Pivot wide — one row per report, one column per dictionary variable.
wide = pivot_wide(files)
wide[["prvdr_num", "hospital_name", "total_beds", "net_patient_revenue"]].head()

# Or write raw long Parquet if you want to do your own pivoting later.
write_parquet(files, year=2023, out_dir="data/parquet/hcris")
```

## Dictionary

15 seed variables covering identity (hospital name, ownership, chain), capacity (total/grand-total beds, bed days, discharges), revenue and expense (net patient revenue, operating expenses, other income/expense), and S-10 uncompensated care (charity, bad debt, total uncompensated).

The dictionary lives at `hcris/dictionaries/2552-10.yaml`. Variable codes (worksheet, line, column) come from CMS Provider Reimbursement Manual Chapter 40 — public domain. Names and descriptions are trove's authorship. Add more variables by appending entries to the YAML.

```python
from hcris import load_dictionary
for v in load_dictionary():
    print(f"{v.name}: {v.wksht_cd}/{v.line_num}/{v.clmn_num}  [{v.type}]")
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

- **Ranged dictionary variables** — dictionary entries with `line_num_end` (e.g. sum of line 2500–3099) are parsed but not yet resolved; they're skipped by `resolve_numeric`.
- **Forms other than 2552-10** (SNF 2540, HHA 1728, Hospice, RHC, Renal) and the pre-2010 2552-96 format. Adding a form is a new YAML + the same parse/resolve path.
- **Ownership-code labels** — `ownership_type` returns the raw CMS code (`"2"`, `"10"`) rather than a human label. Translation table coming.
