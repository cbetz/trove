# Data layout — Parquet bundles served from troveproject.com

DuckDB can query Parquet files over HTTPS natively. Treat each URL below as a virtual table.

## Bundles

| URL | Description | Rows × cols |
|-----|-------------|-------------|
| `https://troveproject.com/data/hcris_2023_wide.parquet` | HCRIS Hospital 2552-10, FY2023, pivoted wide. One row per CCN-keyed facility, every dictionary variable as a named column. | ~6,100 × 48 |
| `https://troveproject.com/data/schedule_h_2022.parquet` | IRS 990 Schedule H filings for tax year 2022. One row per filing (originals + amendments — dedupe per EIN if needed). | ~1,500 × 23 |
| `https://troveproject.com/data/community_benefit_gap_2022.parquet` | Pre-joined gap dataset: HCRIS S-10 charity care summed per EIN, joined to Schedule H 7a, with `charity_gap` and `hcris_fy_end_dt` for alignment filtering. | 1,334 × 14 |
| `https://troveproject.com/data/community_benefit_gap_2022.json` | Same gap dataset, JSON (UI-shaped — non-computable rows excluded, includes `gap_pct`). Use the Parquet for analysis; this is for the web UI. | 1,295 |

## Query patterns

**Bash (DuckDB CLI):**

```bash
duckdb -c "SELECT prvdr_num, hospital_name, total_beds, charity_care_cost
FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
WHERE prvdr_num = '330101'"
```

**Python:**

```python
import duckdb

duckdb.sql("""
    SELECT system, hcris_charity, fa_990, charity_gap
    FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
    WHERE ABS(EXTRACT(EPOCH FROM (hcris_fy_end_dt - sched_h_tax_period_end))/2629800) <= 1
      AND ABS(hcris_charity_care_cost) >= 500000
      AND ABS(sched_h_financial_assistance_at_cost) >= 500000
    ORDER BY ABS(charity_gap) DESC
    LIMIT 10
""").df()
```

**Pre-joining HCRIS to crosswalk and Schedule H in DuckDB:**

```sql
WITH cw AS (
  SELECT DISTINCT ccn, ein FROM 'https://troveproject.com/data/community_benefit_gap_2022.parquet'
),
hcris AS (
  SELECT prvdr_num, hospital_name, total_beds, charity_care_cost, fy_end_dt
  FROM read_parquet('https://troveproject.com/data/hcris_2023_wide.parquet')
)
SELECT cw.ein, hcris.*
FROM hcris JOIN cw ON hcris.prvdr_num = cw.ccn
WHERE hcris.charity_care_cost > 1e7
ORDER BY hcris.charity_care_cost DESC
LIMIT 20;
```

(The full CCN↔EIN crosswalk is bundled inside the `crosswalk` Python package — see "Local Python access" below — but the gap dataset already does the join for you.)

## Key joins

- **HCRIS to crosswalk:** join `hcris_2023_wide.prvdr_num` to crosswalk `ccn`. Multi-facility systems will produce multiple rows per EIN.
- **Schedule H to crosswalk:** join `schedule_h_2022.ein` to crosswalk `ein`.
- **Closing the gap:** the pre-joined `community_benefit_gap_2022.parquet` already does both joins and aggregates HCRIS to the EIN level. Use that table for cross-form questions; use the raw HCRIS or Schedule H tables for facility-level or filing-level questions.

## Important columns on the gap dataset

| Column | What it means |
|--------|---------------|
| `ein` | IRS EIN (zero-padded 9-char). The system-level identifier. |
| `ccn_count` | How many HCRIS-reporting facilities are rolled up under this EIN. >1 means a multi-facility system; aggregation can smooth or amplify per-facility differences. |
| `hospital_name` | Lead facility name from HCRIS (the first CCN's name). |
| `sched_h_organization_name` | The 990 filer name (system parent — usually mixed case). |
| `hcris_charity_care_cost` | Sum of HCRIS Worksheet S-10 charity-care cost across all CCNs sharing this EIN. |
| `hcris_uncompensated_care_cost` | Sum of HCRIS uncompensated-care cost (charity + Medicare bad debt + non-Medicare bad debt). |
| `hcris_total_operating_expenses` | Sum of HCRIS total operating expenses. Use as denominator. |
| `hcris_fy_end_dt` | The latest fiscal-year end across the system's CCNs. Use this against `sched_h_tax_period_end` to gauge alignment. |
| `sched_h_financial_assistance_at_cost` | Schedule H Part I line 7a (financial assistance at cost). |
| `sched_h_total_community_benefit` | Schedule H Part I line 7k (total community benefit). |
| `sched_h_total_expenses` | Total expenses from main 990 (denominator for the 7k ratio). |
| `sched_h_tax_period_end` | End date of the 990 tax period. |
| `charity_gap` | `hcris_charity_care_cost - sched_h_financial_assistance_at_cost`. NULL if either side is blank. |
| `community_benefit_pct_of_expenses` | `sched_h_total_community_benefit / hcris_total_operating_expenses` — sanity check on the 7k ratio against HCRIS expenses. |

## The alignment filter

For most cross-form questions, you want to filter to systems where HCRIS and 990 cover the same fiscal year. The `community_benefit_gap_2022.parquet` table includes both `hcris_fy_end_dt` and `sched_h_tax_period_end`. A row is "aligned" when `|hcris_fy_end_dt - sched_h_tax_period_end| ≤ 1 month`; ~28% of rows pass this filter.

```sql
SELECT *,
  ROUND(ABS(EXTRACT(EPOCH FROM (hcris_fy_end_dt - sched_h_tax_period_end))) / 2629800) AS months_apart
FROM read_parquet('https://troveproject.com/data/community_benefit_gap_2022.parquet')
WHERE ROUND(ABS(EXTRACT(EPOCH FROM (hcris_fy_end_dt - sched_h_tax_period_end))) / 2629800) <= 1
```

## Local Python access (alternative to HTTPS)

If you have the `trove` repo cloned and `uv sync --all-packages` has been run, you can also import the Python packages directly:

```python
from hcris import parse_zip, pivot_wide, load_dictionary
from form990 import parse_zip as parse_990
from crosswalk import load_seed
from analytics import community_benefit_gap

wide = pivot_wide(parse_zip("data/raw/hcris/HOSP10FY2023.zip"))
crosswalk = load_seed()  # 3,523 rows, bundled with the package
gap = community_benefit_gap(wide, sched_h, crosswalk)
```

This is faster for repeated queries and gives you full pandas dataframes; the HTTPS path is for environments without the repo (Claude.ai, ad-hoc analysis from another machine).
