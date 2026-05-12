"""Generate per-drug static HTML pages under web/drugs/{slug}/index.html.

Each page is a permalink for one FDA novel drug approval — its own URL,
metadata, JSON-LD, and links back to the lookup index. Generated from the
same source JSON the /drugs/ lookup uses.

Usage: ``uv run python scripts/build_drug_pages.py``
"""

from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path

SRC = Path("web/data/fda_approvals_nme_recent.json")
OUT_DIR = Path("web/drugs")
SITEMAP = Path("web/sitemap.xml")
SITE = "https://troveproject.com"
OG_IMAGE = f"{SITE}/og-20260505c.jpg"


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
    if not iso:
        return "—"
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return d.strftime("%b %-d, %Y")
    except ValueError:
        return iso


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

  <h2>Query with Claude</h2>
  <p>The <code>fda-analyst</code> skill answers natural-language questions about this approval by fetching the relevant FDA review PDFs at query time.</p>
<pre><code>git clone https://github.com/cbetz/trove
cp -r trove/skills/fda-analyst ~/.claude/skills/</code></pre>
  <p>Example prompts for {drug_name}:</p>
  <ul>
    <li><em>"What was the basis for {drug_name}'s approval — what trials, what endpoints?"</em></li>
    <li><em>"What adverse events did the FDA flag in the {drug_name} medical review?"</em></li>
    <li><em>"What regulatory pathway did {drug_name} use — priority review, breakthrough, accelerated approval?"</em></li>
  </ul>

  <footer>
    <p>One record from the <a href="/drugs/">FDA novel drug approvals index</a> at <a href="/">trove</a>. Built by <a href="https://github.com/cbetz">Chris Betz</a>. Not medical advice; the FDA approval package is the source of truth.</p>
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


def build_page(r: dict) -> tuple[str, str]:
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
    )
    return slug, page


def main() -> None:
    data = json.loads(SRC.read_text())
    rows = data["rows"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    slugs: list[str] = []
    for r in rows:
        slug, page = build_page(r)
        dir_out = OUT_DIR / slug
        dir_out.mkdir(parents=True, exist_ok=True)
        (dir_out / "index.html").write_text(page)
        slugs.append(slug)
        written += 1

    print(f"  → wrote {written} per-drug pages under {OUT_DIR}/")

    # Regenerate sitemap with top-level + per-drug URLs
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    top_level = [
        ("", "1.0"),
        ("drugs/", "0.9"),
        ("hospitals/", "0.9"),
        ("skills/", "0.9"),
        ("skills/fda-analyst/", "0.8"),
        ("skills/hcris-analyst/", "0.8"),
        ("docs/", "0.8"),
        ("docs/hcris/", "0.8"),
        ("docs/schedule-h/", "0.8"),
        ("docs/fda-nme/", "0.8"),
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, priority in top_level:
        lines += [
            "  <url>",
            f"    <loc>{SITE}/{path}</loc>",
            f"    <lastmod>{today}</lastmod>",
            "    <changefreq>monthly</changefreq>",
            f"    <priority>{priority}</priority>",
            "  </url>",
        ]
    for slug in sorted(slugs):
        lines += [
            "  <url>",
            f"    <loc>{SITE}/drugs/{slug}/</loc>",
            f"    <lastmod>{today}</lastmod>",
            "    <changefreq>yearly</changefreq>",
            "    <priority>0.7</priority>",
            "  </url>",
        ]
    lines.append("</urlset>")
    SITEMAP.write_text("\n".join(lines) + "\n")
    print(f"  → wrote {SITEMAP} ({len(slugs) + len(top_level)} URLs)")


if __name__ == "__main__":
    main()
