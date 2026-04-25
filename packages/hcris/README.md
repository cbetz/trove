# hcris

Parser for CMS Medicare Cost Reports (HCRIS), Hospital form 2552-10.

Raw HCRIS ships as three headerless CSVs per fiscal-year ZIP — `RPT`, `NMRC`, `ALPHA` — in a long-skinny `(rpt_rec_num, wksht_cd, line_num, clmn_num, value)` shape. Field semantics live in a CMS PDF (Provider Reimbursement Manual Chapter 40). This package turns the raw ZIPs into tidy DataFrames with the right dtypes and writes partitioned Parquet.

**Status:** M2.5 — parser plus a 44-variable semantic dictionary. `pivot_wide()` turns the raw long-skinny NMRC/ALPHA into one row per report with named columns. Covers identity (name, ownership, chain), bed capacity (total, ICU/CCU/burn/surgical/other special-care via line-range sums), discharges and bed-days, revenue breakdown (G-2 inpatient/outpatient by line + total, G-3 net patient revenue, donations, investment income), expense (operating and other), Worksheet S-10 uncompensated care in detail (charity care charges/cost/partial payments, Medicare bad debt vs. non-Medicare, cost-to-charge ratio), and Medicare program cost and charges (D-series ranges).

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

44 variables in `hcris/dictionaries/2552-10.yaml`. Variable codes (worksheet, line, column) come from CMS Provider Reimbursement Manual Chapter 40 — public domain. Names and descriptions are trove's authorship. Add more by appending entries to the YAML.

Scalar entries reference a single cell:

```yaml
- name: total_beds
  source: nmrc
  wksht_cd: S300001
  line_num: 1400
  clmn_num: 200
```

Range entries sum across a line range (used for ICU/CCU bed sub-categories and Medicare program charge rollups):

```yaml
- name: icu_beds
  source: nmrc
  wksht_cd: S300001
  line_num: 800
  line_num_end: 899
  clmn_num: 200
  aggregation: sum
```

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

- **Forms other than 2552-10** (SNF 2540, HHA 1728, Hospice, RHC, Renal) and the pre-2010 2552-96 format. Adding a form is a new YAML + the same parse/resolve path.
- **Ownership-code labels** — `ownership_type` returns the raw CMS code (`"2"`, `"10"`) rather than a human label. Translation table coming.
- **Aggregations other than `sum`** — `mean`, `max`, `first`, etc. would let us express other range semantics. Not needed yet; add when a variable calls for it.
