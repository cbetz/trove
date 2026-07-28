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
| `index.html` | Homepage — leads with the current finding, then the dataset areas |
| `notes/` | Findings, written from the published tables. `notes/index.html` is the hub |
| `hospitals/` | The Charity Care Gap Index (ranked) plus a lookup over every matched system |
| `drugs/` | FDA novel approvals: search page plus 218 generated per-drug pages |
| `docs/` | Plain-language explainers — HCRIS, 990 Schedule H, FDA NMEs |
| `skills/` | Install pages for the two Claude Code skills |
| `data/` | Published JSON/CSV/Parquet bundles the pages and skills read over HTTPS |
| `sitemap.xml`, `robots.txt` | Generated — see below |

## Regenerating

Anything under `data/`, all of `drugs/`, and `sitemap.xml` are **generated**. Don't hand-edit them.

```bash
uv run python scripts/build_gap_dataset.py   # artifacts CSV + parquet (source of truth)
uv run python scripts/build_gap_index.py     # ranked Gap Index: artifacts MD + data/*.json
uv run python scripts/build_web_data.py      # data/community_benefit_gap_2022.json (site search)
uv run python scripts/build_web_bundles.py   # data/*.parquet + the CSV copy for the site
uv run python scripts/build_drug_pages.py    # drugs/<slug>/ pages AND sitemap.xml
uv run python scripts/build_og_image.py      # og.jpg social card
```

Run them in that order — each reads the previous one's output.

Two things that bite:

- **`sitemap.xml` is written by `build_drug_pages.py`.** A hand-edit gets erased the next
  time that script runs. To add a page to the sitemap, add it to the `top_level` list in
  that script.
- **The site's CSV download is a copy.** `build_web_bundles.py` copies
  `artifacts/community_benefit_gap_2022.csv` into `data/` so the published download can't
  drift from the committed artifact.

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
schema.org JSON-LD. Titles lead with the topic and end with `— trove` (the brand is not
the search term). Light and dark are both handled via `color-scheme` plus a
`prefers-color-scheme` block. Vercel Web Analytics and Speed Insights load at the bottom
of each page.
