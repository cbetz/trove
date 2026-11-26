# hcris

Parser for CMS Medicare Cost Reports (HCRIS), Hospital form 2552-10.

Raw HCRIS ships as three headerless CSVs per fiscal-year ZIP — `RPT`, `NMRC`, `ALPHA` — in a long-skinny `(rpt_rec_num, wksht_cd, line_num, clmn_num, value)` shape. Field semantics live in a CMS PDF (Provider Reimbursement Manual Chapter 40). This package turns the raw ZIPs into tidy DataFrames with the right dtypes and writes partitioned Parquet.

**Status:** parser plus a 52-variable dictionary. `pivot_wide()` turns the long NMRC/ALPHA files into one row per cost report with named columns, and adds the report's status, processing date and an `s10_filed` flag. The dictionary covers identity (name, type of control, home office), beds (total, ICU/CCU/burn/surgical/other special-care via line-range sums), discharges and bed-days, revenue (G-2 inpatient/outpatient, G-3 net patient revenue, donations, investment income), expenses, Medicare program cost and charges (D-series), and Worksheet S-10: Medicaid net revenue, cost and shortfall (lines 2, 7, 8), Medicaid DSH and supplemental payments net of provider taxes (line 5), unreimbursed means-tested cost (line 19), charity care charges, cost and patient payments (lines 20 to 22), cost of charity care for uninsured and insured patients and in total (line 23 columns 1, 2, 3), bad debt (lines 26 to 29), uncompensated care cost (line 30) and line 31.

## Usage

```python
from hcris import download_year, parse_zip, pivot_wide, write_parquet

# Fetch one fiscal-year ZIP from CMS (cached locally after first call).
zip_path = download_year(2023, cache_dir="data/raw/hcris")

# Parse into three DataFrames: report-level, numeric cells, alpha cells.
files = parse_zip(zip_path)

# Pivot wide — one row per report, one column per dictionary variable, plus
# rpt_rec_num, prvdr_num, fy_bgn_dt, fy_end_dt, rpt_stus_cd, rpt_status, proc_dt, s10_filed.
wide = pivot_wide(files)
wide[["prvdr_num", "hospital_name", "fy_bgn_dt", "fy_end_dt", "rpt_status", "charity_care_cost"]].head()

# Or write raw long Parquet if you want to do your own pivoting later.
write_parquet(files, year=2023, out_dir="data/parquet/hcris")
```

## Fiscal-year files

CMS groups cost reports into fiscal-year files by the date the reporting period **begins**: `HOSP10FY2023.zip` holds periods beginning 2022-10-01 through 2023-09-30. A calendar-2022 report is in the FY2022 file. To pair a hospital's cost report with another filing for a given year, load the neighbouring files and choose by period end (`analytics.select_period_matched_reports` does this for Form 990 tax periods). The published bundles are `hcris_2022_wide.parquet` and `hcris_2023_wide.parquet`, each with an added `hcris_file_fy` column.

## Report status and `s10_filed`

`pivot_wide` carries `rpt_stus_cd` from the RPT file and a readable `rpt_status`: 1 `as_submitted`, 2 `settled_without_audit`, 3 `settled_with_audit`, 4 `reopened`, 5 `amended`. `proc_dt` is CMS's processing date.

CMS's numeric file stores no zero values, so a missing dollar value means the cell was blank or zero, not a reported $0. `s10_filed` is true when the report has any Worksheet S-10 cell; false means the hospital filed no S-10 at all. Keep missing values missing downstream.

## Dictionary

52 variables in `hcris/dictionaries/2552-10.yaml`. Variable codes (worksheet, line, column) come from CMS Provider Reimbursement Manual Chapter 40 — public domain. Names and descriptions are trove's authorship. Add more by appending entries to the YAML.

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

### Worksheet aliases (S-10)

CMS renumbered Worksheet S-10 in Transmittal 18 (December 2022). Cost reports for periods beginning before 2022-10-01 carry it as `S100000`; later periods carry S-10 Part I as `S100001` (the whole hospital complex, the same scope as the old worksheet) and a new Part II as `S100002`. The line and column numbers of the variables used here are the same in both, so each S-10 variable lists the old code as an alias:

```yaml
- name: charity_care_cost
  source: nmrc
  wksht_cd: S100001
  wksht_cd_aliases: [S100000]
  line_num: 2300
  clmn_num: 300
```

A report is expected to use exactly one of the codes. If one ever carries a variable under both, the resolver keeps the primary code only and raises a `RuntimeWarning`; it never adds them. Part II is not mapped.

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

- Do not assume `rpt_rec_num` identifies a report across fiscal-year files or across CMS re-issues of a file; qualify by file year. (In the FY2022 and FY2023 files as of October 2026 no record number repeats.)
- CMS rebuilds every yearly ZIP on each quarterly release. The local cache is keyed by filename only; call `download_year(year, force=True)` to refresh.
- `itm_val_str` in ALPHA sometimes has embedded quotes and multi-line values. Read as-is; don't assume single-line records if you do your own parsing.

## Not yet supported

- **Forms other than 2552-10** (SNF 2540, HHA 1728, Hospice, RHC, Renal) and the pre-2010 2552-96 format. Adding a form is a new YAML + the same parse/resolve path.
- **Type-of-control labels** — `ownership_type` returns the raw CMS code from Worksheet S-2 Part I line 21 (`"2"`, `"10"`) rather than a label. Per PRM 15-2 §4004.1: 1 voluntary nonprofit, church; 2 voluntary nonprofit, other; 3 proprietary, individual; 4 proprietary, corporation; 5 proprietary, partnership; 6 proprietary, other; 7 governmental, federal; 8 city-county; 9 county; 10 state; 11 hospital district; 12 city; 13 governmental, other.
- **State, teaching status, FTE and wage data** — not extracted.
- **Aggregations other than `sum`** — `mean`, `max`, `first`, etc. would let us express other range semantics. Not needed yet; add when a variable calls for it.
