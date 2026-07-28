# Contributing

Thanks for looking. trove is a personal open-source project, maintained on nights and
weekends, so response times vary — but every issue gets read.

## Reporting a number that looks wrong

**This is the most valuable kind of issue.** The data joins two federal reporting systems
with different definitions, different fiscal calendars, and self-reported inputs, so
errors are expected and finding them is a contribution.

Open a [Data question](https://github.com/cbetz/trove/issues/new?template=data-question.yml)
and include the hospital's EIN or CCN and the figure you're questioning. Two things make
a report much faster to resolve:

- **Which source you checked it against** — the filed 990 on ProPublica, the hospital's
  own audited statements, HCRIS directly.
- **Which period you're looking at.** This is the single most common source of apparent
  errors. HCRIS names its files by CMS reporting cycle, not by the period covered, so the
  FY2023 file can hold a report ending in mid-2024 — 12 months after the TY2022 990.
  Compare `hcris_fy_end_dt` to `sched_h_tax_period_end` first.

A difference between two filings is not itself an error. The two forms genuinely define
and cost charity care differently, and a hospital can report both figures correctly and
still produce a large gap. If you think trove has mischaracterized a difference, or that
a caveat is missing or misleading, that's also a valid issue — file it as a methodology
question.

## Methodology disagreements

Welcome, and best raised as an issue rather than a PR, so the reasoning is in public
where the next reader can find it. The filters behind the Gap Index (single facility,
period-aligned within a month, both figures ≥ $1M, expense bases within 5%) are judgment
calls; if you'd draw a line differently, say where and why.

## Code contributions

Small fixes — a parser edge case, a broken link, a wrong count — are welcome as PRs
directly. For anything larger, open an issue first so we don't both build it.

```bash
git clone https://github.com/cbetz/trove
cd trove && uv sync --all-packages
uv run pytest
uv run ruff check && uv run ruff format --check
```

CI runs those three commands on every push; all must pass.

A few conventions worth knowing before you edit:

- **Generated files are generated.** `web/data/*`, `web/drugs/*`, `web/sitemap.xml`,
  `artifacts/*`, and the charts injected between `<!-- GAP_CHART -->` markers all come
  from scripts in `scripts/`. Change the script, re-run it, commit the output. A
  hand-edit gets overwritten on the next build.
- **Rebuild order matters** — each script reads the previous one's output. The chain is
  in [`web/README.md`](web/README.md).
- **Parsers get golden tests.** HCRIS pivot bugs are subtle; new field mappings should
  come with a test that pins the expected value.
- **Nothing licensed goes in the public bundles.** UW's Area Deprivation Index is
  non-sublicensable, so it flows through the local pipeline only and is stripped before
  publication. If you add a data source, check its redistribution terms first — that
  filter is why HCRIS and 990 were chosen in the first place.
- **Framing.** Where the docs describe cross-form differences, they attribute each figure
  to the filing line it came from and avoid asserting that anyone misreported. Please keep
  that register; it's what makes the project safe to publish.

## Security

Nothing here handles credentials or personal data — every input is a public government
filing. If you find something that looks like a security problem anyway, email rather
than filing publicly: the address is on [cbetz.com](https://cbetz.com).
