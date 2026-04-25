# trove

Open-source parsers, agents, and visualizations for underused healthcare datasets. Named after the framing that started it — "Medicare Cost Reports are a treasure trove."

Phase 1 targets:

- **`hcris`** — CMS Medicare Cost Reports (2552-10 and friends) with a semantic field dictionary, because the raw format is headerless long-skinny CSVs that nobody should have to pivot by hand.
- **`form990`** — IRS Form 990 XML, scoped to Schedule H (hospital community benefit).
- **`crosswalk`** — CCN ↔ EIN linking, seeded from Sacarny + CBI and reconciled with an agent-assisted fuzzy matcher.
- **`analytics`** — composed queries: peer comparisons, margin trends, Schedule-H-vs-S-10 community-benefit discrepancy detection.

On top of those: a Claude skill bundle (`skills/hcris-analyst`) and a static Observable Framework site (`web/`).

## Status

**M4.1 — Full TY2022 gap dataset published.** `form990.parse_tax_year()` orchestrates the full ingest (download all relevant ZIPs from the IRS index, parse Schedule H, concat). Run end-to-end against FY2023 HCRIS + TY2022 990s + CBI crosswalk to produce a 1,317-system table covering ~$58.7B of reported community benefit. **61% of systems report more charity care to CMS than to the IRS**; total absolute gap is $5.02B. Top gap: Memorial Hermann Kingwood at +$120.8M. Committed CSV artifacts at `artifacts/`; reproduce with `uv run python scripts/build_gap_dataset.py`.

**M4 — Community benefit gap.** `crosswalk` package ships the bundled CBI CCN↔EIN mapping (3,523 hospitals, 2,385 EINs, frozen at Dec 6 2024); `analytics.community_benefit_gap()` joins HCRIS S-10 to 990 Schedule H by EIN.

**M3 — IRS Form 990 Schedule H parser.** Bulk-XML download, index CSV reader, and Schedule H extraction with cheap byte-level pre-filter. 19 fields per filing including Part I line 7a-k net community benefit amounts, Part III bad debt, and Part V hospital facility count. Verified on `2024_TEOS_XML_01A`: 21 hospital filers extracted including Corewell Health (21 facilities, $823M community benefit). TY2022 bootstrap.

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
