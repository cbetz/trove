"""Generate per-drug static HTML pages under web/drugs/{slug}/index.html.

Each page is a permalink for one FDA novel drug approval — its own URL,
metadata, JSON-LD, links back to the lookup index, and links to related
approvals (chronological neighbours, same sponsor, same year). Generated from
the same source JSON the /drugs/ lookup uses.

Pages for drugs no longer in the source JSON are removed, and the sitemap's
per-drug entries are regenerated; every other sitemap entry is left exactly
as it is.

Usage: ``uv run python scripts/build_drug_pages.py``
"""

from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from build_og_image import FILENAME as OG_FILENAME

SRC = Path("web/data/fda_approvals_nme_recent.json")
OUT_DIR = Path("web/drugs")
SITEMAP = Path("web/sitemap.xml")
SITE = "https://troveproject.com"
# Single-sourced from build_og_image so regenerating the per-drug pages can't
# silently revert them to a stale, cache-busted card filename.
OG_IMAGE = f"{SITE}/{OG_FILENAME}"
REPO_URL = "https://github.com/cbetz/trove"
# Keep in step with README.md "Install the skills" and web/skills/index.html.
PLUGIN_INSTALL = """/plugin marketplace add anthropics/claude-plugins-community
/plugin install trove@claude-community"""
# How many same-sponsor / same-year links to show before deferring to the index.
MAX_RELATED = 8


def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def title_case(s: str | None) -> str:
    """Match the JS titleCase on the index — convert SHOUTING sponsor names."""
    if not s:
        return ""
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return s
    upper = sum(1 for c in letters if c.isupper())
    if upper / len(letters) < 0.8:
        return s
    return re.sub(r"\w\S*", lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(), s)


def fmt_date(iso: str | None) -> str:
    """Format an ISO date for display. Raises on anything that is not a date.

    A missing or malformed approval date used to be echoed straight onto the
    page (Tzield shipped as "approved NaT"); it now stops the build instead.
    """
    if not iso:
        raise ValueError("missing approval date")
    d = datetime.strptime(iso, "%Y-%m-%d")
    return d.strftime("%b %-d, %Y")


def esc(s: str | None) -> str:
    return html.escape(s or "", quote=True)


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{og_title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{og_image}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{og_title}">
  <meta name="twitter:description" content="{description}">
  <meta name="twitter:image" content="{og_image}">
  <script type="application/ld+json">
{jsonld}
  </script>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #ffffff;
      --fg: #111111;
      --muted: #5a5a5a;
      --border: rgba(127, 127, 127, 0.3);
      --row-hover: rgba(127, 127, 127, 0.08);
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{ --bg: #111111; --fg: #f2f2f2; --muted: #adadad; }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0 auto;
      padding: 4rem 1.5rem 6rem;
      max-width: 44rem;
      font: 15px/1.6 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      background: var(--bg);
      color: var(--fg);
    }}
    .breadcrumb {{ color: var(--muted); margin: 0 0 1.25rem; font-size: 0.9em; }}
    .breadcrumb a {{ text-decoration: none; }}
    .breadcrumb a:hover {{ text-decoration: underline; }}
    h1 {{ font-size: 2.4rem; margin: 0 0 0.4rem; letter-spacing: -0.025em; font-weight: 700; }}
    .subtitle {{ color: var(--muted); margin: 0 0 0.4rem; font-size: 1.05rem; }}
    .sponsor {{ color: var(--muted); margin: 0 0 2rem; font-size: 0.95em; }}
    h2 {{ font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--muted); margin: 2.5rem 0 0.85rem; font-weight: 600; }}
    a {{ color: inherit; }}
    a:hover {{ opacity: 0.7; }}
    code {{ background: var(--border); padding: 0.05em 0.35em; border-radius: 3px; font-size: 0.9em; }}
    pre {{ background: var(--border); padding: 1rem 1.25rem; border-radius: 6px; overflow-x: auto; font-size: 0.85em; line-height: 1.5; }}

    .meta {{ border: 1px solid var(--border); border-radius: 6px; padding: 1.25rem 1.5rem; }}
    .meta-row {{ display: flex; gap: 0.8rem; align-items: baseline; padding: 0.4rem 0; border-bottom: 1px solid var(--border); }}
    .meta-row:last-child {{ border-bottom: 0; }}
    .meta-label {{ color: var(--muted); white-space: nowrap; min-width: 11rem; font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.05em; }}
    @media (max-width: 640px) {{
      h1 {{ font-size: 1.9rem; }}
      .meta-row {{ flex-direction: column; gap: 0.1rem; }}
      .meta-label {{ min-width: auto; }}
    }}

    .indication {{ border: 1px solid var(--border); border-radius: 6px; padding: 1.25rem 1.5rem; }}
    .indication p {{ margin: 0; line-height: 1.55; }}

    .links {{ list-style: none; padding: 0; margin: 0; }}
    .links li {{ padding: 0.5rem 0; border-bottom: 1px solid var(--border); }}
    .links li:last-child {{ border-bottom: 0; }}
    .links a {{ display: block; }}
    .links .when {{ color: var(--muted); font-size: 0.85em; }}
    h3 {{ font-size: 0.9rem; margin: 1.5rem 0 0.4rem; font-weight: 600; }}
    .related {{ list-style: none; padding: 0; margin: 0; }}
    .related li {{ padding: 0.3rem 0; }}
    .related .when {{ color: var(--muted); font-size: 0.85em; }}

    footer {{ margin-top: 4rem; padding-top: 1.5rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.85em; }}
    footer p {{ margin: 0 0 0.5rem; }}
  </style>
</head>
<body>
  <p class="breadcrumb"><a href="/">trove</a> / <a href="/drugs/">FDA drug approvals</a> / {drug_name}</p>

  <header>
    <h1>{drug_name}</h1>
    <p class="subtitle">{active_ingredient}</p>
    <p class="sponsor">{sponsor}</p>
  </header>

  <h2>Approval</h2>
  <div class="meta">
    <div class="meta-row"><span class="meta-label">Application</span><span>{application_type} {application_number}</span></div>
    <div class="meta-row"><span class="meta-label">Approval date</span><span>{approval_date_fmt}</span></div>
    <div class="meta-row"><span class="meta-label">Approval year</span><span>{year}</span></div>
    <div class="meta-row"><span class="meta-label">Sponsor</span><span>{sponsor}</span></div>
  </div>

  <h2>FDA-approved use</h2>
  <div class="indication"><p>{indication}</p></div>

  <h2>Approval package</h2>
  <ul class="links">
{link_items}
  </ul>

  <h2>Related approvals</h2>
{related}

  <h2>Query with Claude</h2>
  <p>The <a href="/skills/fda-analyst/"><code>fda-analyst</code> skill</a> answers natural-language questions about this approval by fetching the relevant FDA review PDFs at query time. It ships in the trove Claude Code plugin. Add Anthropic's public community marketplace, then install the plugin:</p>
<pre><code>{plugin_install}</code></pre>
  <p>Other install options are on the <a href="/skills/">skills page</a>; the source is at <a href="{repo_url}">github.com/cbetz/trove</a>.</p>
  <p>Example prompts for {drug_name}:</p>
  <ul>
    <li><em>"What was the basis for {drug_name}'s approval — what trials, what endpoints?"</em></li>
    <li><em>"What adverse events did the FDA flag in the {drug_name} medical review?"</em></li>
    <li><em>"What regulatory pathway did {drug_name} use — priority review, breakthrough, accelerated approval?"</em></li>
  </ul>

  <footer>
    <p><a href="/drugs/">← All FDA novel drug approvals</a> · <a href="/">trove home</a> · <a href="/skills/">Claude skills</a> · <a href="{repo_url}">Source on GitHub</a></p>
    <p>One record from the <a href="/drugs/">FDA novel drug approvals index</a> ({coverage}) at <a href="/">trove</a>. Built by <a href="https://github.com/cbetz">Chris Betz</a>. Not medical advice; the FDA approval package is the source of truth.</p>
    <p>Source: U.S. Food and Drug Administration, <a href="https://www.fda.gov/drugs/development-approval-process-drugs/novel-drug-approvals-fda">Novel Drug Approvals</a>; <a href="https://www.accessdata.fda.gov/scripts/cder/daf/">Drugs@FDA database</a>. US government work, public domain.</p>
    <p>More from Chris: <a href="https://cbetz.com">cbetz.com</a> · <a href="https://x.com/thechrisbetz">@thechrisbetz</a> on X · <a href="https://github.com/cbetz">github.com/cbetz</a>.</p>
  </footer>

  <script defer src="/_vercel/insights/script.js"></script>
  <script defer src="/_vercel/speed-insights/script.js"></script>
</body>
</html>
"""


def build_jsonld(r: dict, canonical: str) -> str:
    drug_node = {
        "@context": "https://schema.org",
        "@type": "Drug",
        "name": r["drug_name"],
        "url": canonical,
        "activeIngredient": r.get("active_ingredient"),
        "manufacturer": {
            "@type": "Organization",
            "name": title_case(r.get("sponsor")),
        }
        if r.get("sponsor")
        else None,
        "description": r.get("indication"),
        "isProprietary": True,
    }
    drug_node = {k: v for k, v in drug_node.items() if v is not None}

    breadcrumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "trove", "item": f"{SITE}/"},
            {
                "@type": "ListItem",
                "position": 2,
                "name": "FDA drug approvals",
                "item": f"{SITE}/drugs/",
            },
            {"@type": "ListItem", "position": 3, "name": r["drug_name"], "item": canonical},
        ],
    }

    return json.dumps([drug_node, breadcrumbs], indent=2)


def build_link_items(r: dict) -> str:
    items = []
    if r.get("drugs_at_fda_url"):
        items.append(
            f'    <li><a href="{esc(r["drugs_at_fda_url"])}" rel="noopener" target="_blank">↗ Drugs@FDA: full approval-package overview (every PDF the FDA released)</a></li>'
        )
    if r.get("label_pdf_url"):
        items.append(
            f'    <li><a href="{esc(r["label_pdf_url"])}" rel="noopener" target="_blank">↗ FDA-approved label (PDF)</a></li>'
        )
    if r.get("trials_snapshot_url"):
        items.append(
            f'    <li><a href="{esc(r["trials_snapshot_url"])}" rel="noopener" target="_blank">↗ FDA Drug Trials Snapshot</a></li>'
        )
    return (
        "\n".join(items)
        if items
        else '    <li><span style="color: var(--muted);">No FDA links available for this row.</span></li>'
    )


def _related_link(r: dict) -> str:
    return (
        f'<a href="/drugs/{slugify(r["drug_name"])}/">{esc(r["drug_name"])}</a> '
        f'<span class="when">({esc(r.get("active_ingredient") or "—")}) · '
        f"{esc(fmt_date(r.get('approval_date')))}</span>"
    )


def _related_list(rows: list[dict]) -> str:
    items = "\n".join(f"    <li>{_related_link(x)}</li>" for x in rows)
    return f'  <ul class="related">\n{items}\n  </ul>'


def build_related(r: dict, ordered: list[dict]) -> str:
    """Internal links from one drug page to other drug pages.

    ``ordered`` is every row sorted by approval date. Three groups, each
    omitted when empty: the approvals immediately before and after this one,
    other approvals held by the same sponsor, and other approvals from the
    same year and regulatory center (nearest in time first).
    """
    i = next(k for k, x in enumerate(ordered) if x is r)
    blocks: list[str] = []

    neighbours = []
    if i > 0:
        neighbours.append(f"    <li>Previous: {_related_link(ordered[i - 1])}</li>")
    if i < len(ordered) - 1:
        neighbours.append(f"    <li>Next: {_related_link(ordered[i + 1])}</li>")
    if neighbours:
        blocks.append(
            "  <h3>Approved just before and after</h3>\n"
            '  <ul class="related">\n' + "\n".join(neighbours) + "\n  </ul>"
        )
    shown = {id(x) for x in ordered[max(i - 1, 0) : i + 2]}

    sponsor = title_case(r.get("sponsor"))
    if sponsor:
        same_sponsor = [
            x for x in ordered if x is not r and title_case(x.get("sponsor")) == sponsor
        ]
        if same_sponsor:
            blocks.append(
                f"  <h3>Also from {esc(sponsor)}</h3>\n" + _related_list(same_sponsor[:MAX_RELATED])
            )
            shown |= {id(x) for x in same_sponsor[:MAX_RELATED]}

    center = r.get("regulatory_center")
    same_year = [
        (abs(k - i), x)
        for k, x in enumerate(ordered)
        if id(x) not in shown
        and x.get("year") == r.get("year")
        and x.get("regulatory_center") == center
    ]
    same_year.sort(key=lambda t: t[0])
    if same_year:
        kind = (
            "cell and gene therapy approvals (CBER)" if center == "CBER" else "novel drug approvals"
        )
        nearest = sorted((x for _, x in same_year[:MAX_RELATED]), key=lambda x: x["approval_date"])
        blocks.append(
            f"  <h3>More {esc(str(r.get('year')))} {kind}</h3>\n" + _related_list(nearest)
        )

    blocks.append(
        '  <p><a href="/drugs/">Search all FDA novel drug approvals in the index →</a></p>'
    )
    return "\n".join(blocks)


def build_page(r: dict, ordered: list[dict], coverage: str) -> tuple[str, str]:
    slug = slugify(r["drug_name"])
    canonical = f"{SITE}/drugs/{slug}/"
    sponsor = title_case(r.get("sponsor")) or "Sponsor not identified"
    active = r.get("active_ingredient") or "—"
    indication = r.get("indication") or "Indication not summarized in the FDA annual page."
    approval_date_fmt = fmt_date(r.get("approval_date"))

    title = f"{r['drug_name']} ({active}) FDA approval — trove"
    og_title = f"{r['drug_name']} — FDA approval package"
    description = (
        f"FDA novel drug approval for {r['drug_name']} ({active}), {r.get('application_type', '')} "
        f"{r.get('application_number', '')}, approved {approval_date_fmt} for {sponsor}. "
        f"Direct links to the FDA approval package."
    ).strip()

    page = PAGE_TEMPLATE.format(
        title=esc(title),
        description=esc(description),
        canonical=canonical,
        og_title=esc(og_title),
        og_image=OG_IMAGE,
        jsonld=build_jsonld(r, canonical),
        drug_name=esc(r["drug_name"]),
        active_ingredient=esc(active),
        sponsor=esc(sponsor),
        application_type=esc(r.get("application_type") or ""),
        application_number=esc(r.get("application_number") or "—"),
        approval_date_fmt=esc(approval_date_fmt),
        year=esc(str(r.get("year") or "")),
        indication=esc(indication),
        link_items=build_link_items(r),
        related=build_related(r, ordered),
        plugin_install=esc(PLUGIN_INSTALL),
        repo_url=REPO_URL,
        coverage=esc(coverage),
    )
    return slug, page


_DRUG_URL_BLOCK_RE = re.compile(
    r"[ \t]*<url>\s*<loc>" + re.escape(SITE) + r"/drugs/[a-z0-9-]+/</loc>.*?</url>[ \t]*\n?",
    re.S,
)


def update_sitemap(slugs: list[str]) -> int:
    """Regenerate only the per-drug ``<url>`` entries of the sitemap.

    Every other entry is kept byte-for-byte: the rest of the sitemap is
    maintained elsewhere, and this script used to overwrite it wholesale from
    a hard-coded list. Returns the number of per-drug entries written.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    drug_blocks = "".join(
        "  <url>\n"
        f"    <loc>{SITE}/drugs/{slug}/</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        "    <changefreq>yearly</changefreq>\n"
        "    <priority>0.7</priority>\n"
        "  </url>\n"
        for slug in sorted(slugs)
    )
    text = SITEMAP.read_text()
    if "</urlset>" not in text:
        raise SystemExit(f"{SITEMAP} has no </urlset>; refusing to rewrite it")
    text = _DRUG_URL_BLOCK_RE.sub("", text)
    text = text.replace("</urlset>", drug_blocks + "</urlset>", 1)
    SITEMAP.write_text(text)
    return len(slugs)


def prune_stale_pages(slugs: set[str]) -> list[str]:
    """Delete generated pages for drugs that are no longer in the index.

    Only touches a directory that holds nothing but a generated ``index.html``.
    """
    removed = []
    for d in sorted(OUT_DIR.iterdir()):
        if not d.is_dir() or d.name in slugs:
            continue
        if [f.name for f in d.iterdir()] != ["index.html"]:
            continue
        (d / "index.html").unlink()
        d.rmdir()
        removed.append(d.name)
    return removed


def main() -> None:
    data = json.loads(SRC.read_text())
    rows = data["rows"]
    totals = data["totals"]
    coverage = f"{totals['year_min']}–{totals['year_max']}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bad = [
        r["drug_name"]
        for r in rows
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", r.get("approval_date") or "")
    ]
    if bad:
        raise SystemExit(f"Rows without a valid approval date: {', '.join(bad)}")
    slugs = [slugify(r["drug_name"]) for r in rows]
    if len(set(slugs)) != len(slugs):
        raise SystemExit("Two drugs map to the same page slug")
    ordered = sorted(rows, key=lambda r: (r["approval_date"], r["drug_name"]))

    for r in rows:
        slug, page = build_page(r, ordered, coverage)
        dir_out = OUT_DIR / slug
        dir_out.mkdir(parents=True, exist_ok=True)
        (dir_out / "index.html").write_text(page)

    print(f"  → wrote {len(slugs)} per-drug pages under {OUT_DIR}/")
    removed = prune_stale_pages(set(slugs))
    if removed:
        print(f"  → removed {len(removed)} stale page(s): {', '.join(removed)}")

    n = update_sitemap(slugs)
    print(f"  → updated {n} per-drug URLs in {SITEMAP} (other entries untouched)")


if __name__ == "__main__":
    main()
