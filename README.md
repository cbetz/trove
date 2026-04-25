# trove

Open-source parsers, agents, and visualizations for underused healthcare datasets. Named after the framing that started it — "Medicare Cost Reports are a treasure trove."

Phase 1 targets:

- **`hcris`** — CMS Medicare Cost Reports (2552-10 and friends) with a semantic field dictionary, because the raw format is headerless long-skinny CSVs that nobody should have to pivot by hand.
- **`form990`** — IRS Form 990 XML, scoped to Schedule H (hospital community benefit).
- **`crosswalk`** — CCN ↔ EIN linking, seeded from Sacarny + CBI and reconciled with an agent-assisted fuzzy matcher.
- **`analytics`** — composed queries: peer comparisons, margin trends, Schedule-H-vs-S-10 community-benefit discrepancy detection.

On top of those: a Claude skill bundle (`skills/hcris-analyst`) and a static Observable Framework site (`web/`).

## Status

**M3 — IRS Form 990 Schedule H parser.** Bulk-XML download (per-release-year ZIPs), index CSV reader/filter (dedupes amendments by EIN), and Schedule H extraction. Outputs one row per hospital filer with EIN, organization name, tax-period dates, total revenue/expenses, Part I line 7a-k net community benefit amounts, total community benefit ratio, Part III bad debt expense, and Part V hospital facility count. Cheap byte-level pre-filter for `IRS990ScheduleH` keeps a 100 MB ZIP iteration to under a second. Verified on real `2024_TEOS_XML_01A`: 21 hospital filers extracted, including Corewell Health (21 facilities, $823M community benefit) and Hennepin Healthcare. TY2022 is the bootstrap year.

**M2.5 — HCRIS semantic dictionary, expanded.** 44 variables covering identity, bed capacity (ICU/CCU/burn/surgical special-care via line-range sums), discharges, revenue breakdown (G-2 inpatient/outpatient), expense, Worksheet S-10 uncompensated care in detail, and Medicare program cost/charges. Validated on FY2023; top uncompensated-care hospitals are the public safety-net systems (Harris Health, Dallas County, Grady, NYC H+H).

See `packages/hcris/README.md` and `packages/form990/README.md` for usage. `scripts/demo_hospital_summary.py` prints a full NYP profile.

## Dev setup

```bash
uv sync --all-packages
uv run pytest
uv run ruff check
```

## Layout

```
packages/         Python libraries (hcris, form990, crosswalk, analytics)
skills/           Claude skill bundles
web/              Observable Framework site (static, DuckDB-WASM)
pipelines/        ETL orchestration (Prefect/Dagster) — TBD
notebooks/        Exploratory work, not shipped
docs/             mkdocs-material site
```

## License

MIT. Source data (CMS HCRIS, IRS 990) is US government work and public domain.
