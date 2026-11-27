# web

The static site served at [troveproject.com](https://troveproject.com). Plain HTML,
no build step, no framework — Vercel serves this directory as-is (`vercel.json` sets
`outputDirectory: web`). Data loads client-side from `web/data/`.

Observable Framework was the original plan (see the M6 notes in git history); hand-written
static pages won because the site is a handful of lookup views over pre-computed JSON,
and this way there's nothing to build and nothing to break.

## Layout

| Path | What it is |
|---|---|
| `index.html` | Homepage — leads with the hospital side-by-side, then the dataset areas |
| `notes/` | Write-ups from the published tables. `notes/index.html` is the hub |
| `hospitals/` | IRS Schedule H line 7a and CMS S-10 line 23 side by side: the ranked index (493 hospitals) plus a lookup over every matched system (2,099) |
| `drugs/` | FDA novel approvals: search page plus 268 generated per-drug pages |
| `docs/` | Plain-language explainers — HCRIS, 990 Schedule H, FDA NMEs |
| `skills/` | Install pages for the two Claude Code skills |
| `data/` | Published JSON/CSV/Parquet files the pages and skills read over HTTPS |
| `og-20261119.jpg` | The social card every page's `og:image` points at (generated, see below) |
| `sitemap.xml`, `robots.txt` | Generated — see below |

## Regenerating

Anything under `data/`, everything under `drugs/` except `drugs/index.html` (per-drug,
per-year, statistics and compilation pages, with their `index.md` twins), the `/drugs/`
entries in `sitemap.xml`, the social card, and the chart block between the `GAP_CHART` markers in
`hospitals/index.html` and `notes/charity-care-gap/index.html` are **generated**. Don't
hand-edit them. `drugs/index.html` (the search page) is hand-written.

```bash
uv run python scripts/build_gap_dataset.py   # artifacts CSV + sources JSON (source of truth)
uv run python scripts/build_gap_index.py     # ranked index + summary: artifacts MD + data/charity_care_gap_index_2022.json
uv run python scripts/build_web_data.py      # data/community_benefit_gap_2022.json (site lookup)
uv run python scripts/build_web_bundles.py   # data/*.parquet + the CSV copy for the site
uv run python scripts/build_fda_index.py     # data/fda_approvals_nme_recent.{json,parquet} + data/fda_nme_compilation.{csv,parquet}
uv run python scripts/build_drug_pages.py    # drugs/<slug>/, drugs/<year>/, drugs/statistics/, drugs/compilation/ (index.html + index.md), the static list in drugs/index.html, AND every /drugs/ entry in sitemap.xml
uv run python scripts/build_og_image.py      # the og-YYYYMMDD.jpg social card
```

Run them in that order — each reads the previous one's output. Only the first two and
`build_og_image.py` take flags; the others run as soon as they are invoked (there is no
`--help`), and rewrite their outputs.

Flags:

| Flag | What it does |
|---|---|
| `build_gap_dataset.py --refresh-hcris` | Re-download the CMS HCRIS ZIPs (FY2022 and FY2023) instead of using the cached copies |
| `build_gap_dataset.py --refresh-990` | Re-ingest every IRS e-file ZIP of the 2023–2026 releases (about 17 GB, one ZIP at a time) instead of using the per-ZIP caches |
| `build_gap_dataset.py --check-posted` | Ask CMS (one HEAD request per file) when each HCRIS ZIP on disk was posted |
| `build_gap_index.py --inject-chart` | Also rewrite the scatter chart between the `GAP_CHART:START` / `GAP_CHART:END` markers in the two pages above. Without the flag no HTML is touched. Each page must hold exactly one pair of markers, or nothing is written |
| `build_og_image.py --retarget-pages` | Rewrite `og:image` / `twitter:image` in `web/**/*.html` to the card's file name. Without the flag only the image is written |

Things that bite:

- **The numbers in the page copy are not generated.** Counts in `index.html`,
  `notes/index.html`, the prose and static tables of `notes/charity-care-gap/index.html`,
  and the static fallbacks in `hospitals/index.html` are written into the HTML. After a
  data rebuild, check them against `data/charity_care_gap_index_2022.json` (`counts`) and
  `data/community_benefit_gap_2022.json` (`totals`).
- **Every `/drugs/<something>/` entry in `sitemap.xml` is written by `build_drug_pages.py`.**
  The other entries (including `/drugs/` itself and `/docs/`) are left alone; add a new
  top-level page to the sitemap by hand. A generated page's `lastmod` and JSON-LD
  `dateModified` change only when its content changes, so re-running the script on unchanged
  data rewrites nothing.
- **Generated pages have Markdown twins.** Each `drugs/**/index.html` the scripts write has
  an `index.md` beside it with the same facts, advertised with
  `<link rel="alternate" type="text/markdown">` and served `noindex` (see `vercel.json`).
  `llms.txt` and `robots.txt` are hand-written; update the counts in `llms.txt` after a
  data rebuild.
- **The 32-character `.txt` file at the site root is the IndexNow key.** It is public by
  design: Bing and the other IndexNow engines fetch it to confirm that URL submissions come
  from this site. Don't delete or rename it. After a deploy that changes pages, run
  `uv run python scripts/indexnow_submit.py --since YYYY-MM-DD` to tell them what changed.
- **`drugs/index.html` is hand-written except between the `fda-static-list` markers,** which
  hold the crawlable year links and drug links (the search box itself needs JavaScript).
- **The docs pages quote counts.** `docs/new-molecular-entity/`, `docs/fda-approval-package/`
  and `docs/drug-trials-snapshot/` state figures from the FDA bundles (1,387 approvals,
  118 Type 1 NDAs, 232 Snapshots and so on). Check them after a rebuild.
- **The site's CSV download is a copy.** `build_web_bundles.py` copies
  `artifacts/community_benefit_gap_2022.csv` into `data/` so the published download can't
  drift from the committed artifact.
- **The social card's file name carries a date** so that link previews are not served a
  cached older card. When the card changes, change `FILENAME` in `build_og_image.py`, run
  it with `--retarget-pages`, and delete the old file.

## After a deploy: check the CORS preflight on `/data/`

`vercel.json` sets `Access-Control-*` headers on `/data/(.*)` so that browser-based tools
(DuckDB-WASM, notebooks) can read the Parquet files with range requests. A plain GET
already returns `access-control-allow-origin: *`. What is not known until a deploy is
whether Vercel applies `vercel.json` headers to the `OPTIONS` preflight for a static
file; before this change the preflight returned 204 with no `Access-Control-*` headers.
Check it after each deploy that touches `vercel.json`:

```bash
curl -si -X OPTIONS \
  -H "Origin: https://example.org" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: range" \
  https://troveproject.com/data/charity_care_gap_index_2022.json
```

The response should carry `access-control-allow-origin`, `access-control-allow-methods`
and `access-control-allow-headers` (including `range`). If it does not, `vercel.json`
headers cannot fix it: the options are a `routes` rule with `methods: ["OPTIONS"]` or a
small middleware function. In that case remove the inert headers block rather than
leaving it in, as with the www redirect below.

## Host canonicalization (a dashboard setting, not a repo setting)

`www.troveproject.com` redirects to the apex with a **307 Temporary**. It should be a
**308 Permanent**: a temporary redirect tells Google the canonical host might change
back, so it keeps the `www` variant as an index candidate instead of consolidating
signals onto one host. This is why the Page indexing report lists `www` and `http://`
variants under "Page with redirect".

**It cannot be fixed from this repo.** A domain configured as a redirect in Vercel is
handled at the edge *before* the deployment's routing config is read, so a `redirects`
entry in `vercel.json` never fires for that host (verified: the response carries
`content-type: text/plain` and no `x-vercel-cache`, and it fires for every path).

Fix it in the Vercel dashboard: **Project → Settings → Domains → `www.troveproject.com`
→ change the redirect status code from 307 to 308 (Permanent).** The `http://` hops are
already 308 and need nothing.

## Conventions

Every page is self-contained: inline `<style>`, no shared stylesheet, no JS framework.
Each carries its own `<title>`, meta description, canonical URL, OG/Twitter tags, and
schema.org JSON-LD. Titles lead with the topic and end with `| trove` or `— trove` (the brand is not
the search term). Light and dark are both handled via `color-scheme` plus a
`prefers-color-scheme` block. Vercel Web Analytics and Speed Insights load at the bottom
of each page.
