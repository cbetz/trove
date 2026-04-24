# trove

Open-source parsers, agents, and visualizations for underused healthcare datasets. Named after the framing that started it — "Medicare Cost Reports are a treasure trove."

Phase 1 targets:

- **`hcris`** — CMS Medicare Cost Reports (2552-10 and friends) with a semantic field dictionary, because the raw format is headerless long-skinny CSVs that nobody should have to pivot by hand.
- **`form990`** — IRS Form 990 XML, scoped to Schedule H (hospital community benefit).
- **`crosswalk`** — CCN ↔ EIN linking, seeded from Sacarny + CBI and reconciled with an agent-assisted fuzzy matcher.
- **`analytics`** — composed queries: peer comparisons, margin trends, Schedule-H-vs-S-10 community-benefit discrepancy detection.

On top of those: a Claude skill bundle (`skills/hcris-analyst`) and a static Observable Framework site (`web/`).

## Status

**M0 — Scaffold.** Workspace, CI, license, docs skeleton. No parsers yet.

See milestone plan in the repo root issue tracker (or the original design doc).

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
