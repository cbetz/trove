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
- **Which period you're looking at.** CMS groups cost reports into fiscal-year files by
  the date the reporting period begins, and the matched dataset already selects, per CCN,
  the report ending closest to the 990's period. Check `period_aligned` on the row first:
  when it is false, the two figures cover different years. Also check whether the line is
  empty. A hospital with no value on S-10 line 23 is published as empty, never `0`.

A difference between two filings is not itself an error. Schedule H line 7a and S-10
line 23 are defined differently (see the method summary in `artifacts/`), and a hospital
can file both correctly and still show a large difference. If you think trove has
mischaracterized a difference, or that a caveat is missing or misleading, that's also a
valid issue — file it as a methodology question. If you know what is in a difference that
the published components do not show, that is especially welcome.

## Methodology disagreements

Welcome, and best raised as an issue rather than a PR, so the reasoning is in public
where the next reader can find it. The filters behind the ranked index (single facility,
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
