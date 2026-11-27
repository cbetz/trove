"""Shared pieces for the scripts that write the FDA section of the site.

Used by ``build_drug_pages.py`` (one page per drug) and ``build_fda_lists.py``
(per-year lists, statistics, the compilation download page). Standard library
only, so the pages can be regenerated without the data toolchain.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path

from build_og_image import FILENAME as OG_FILENAME

SITE = "https://troveproject.com"
REPO_URL = "https://github.com/cbetz/trove"
# Single-sourced from build_og_image so regenerating pages can't silently
# revert them to a stale, cache-busted card filename.
OG_IMAGE = f"{SITE}/{OG_FILENAME}"
SITEMAP = Path("web/sitemap.xml")
DRUGS_DIR = Path("web/drugs")

COMPILATION_PAGE_URL = (
    "https://www.fda.gov/drugs/drug-approvals-and-databases/"
    "compilation-cder-new-molecular-entity-nme-drug-and-new-biologic-approvals"
)
NOVEL_APPROVALS_URL = (
    "https://www.fda.gov/drugs/development-approval-process-drugs/novel-drug-approvals-fda"
)
DRUGS_AT_FDA_URL = "https://www.accessdata.fda.gov/scripts/cder/daf/"
CBER_PRODUCTS_URL = (
    "https://www.fda.gov/vaccines-blood-biologics/cellular-gene-therapy-products/"
    "approved-cellular-and-gene-therapy-products"
)

PERSON = {
    "@type": "Person",
    "name": "Chris Betz",
    "url": "https://cbetz.com",
    "sameAs": ["https://cbetz.com", "https://x.com/thechrisbetz", "https://github.com/cbetz"],
}
PUBLISHER = {"@type": "Organization", "name": "trove", "url": f"{SITE}/"}


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


def fmt_date_long(iso: str | None) -> str:
    """``2023-12-18`` -> ``December 18, 2023``, for running prose."""
    if not iso:
        raise ValueError("missing date")
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%B %-d, %Y")


def esc(s: object) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def url_attr(url: str) -> str:
    """Escape a URL for an href. A few FDA document URLs contain spaces."""
    return esc(url.replace(" ", "%20"))


def is_yes(value: str | None) -> bool:
    return bool(value) and value.strip().lower().startswith("yes")


def is_priority(value: str | None) -> bool:
    return bool(value) and value.strip().lower().startswith("priority")


def _qualifier(value: str) -> str:
    """``Yes (indication [A] only)`` -> `` (indication [A] only)``."""
    m = re.search(r"\(.*\)", value)
    return f" {m.group(0)}" if m else ""


def designations(r: dict) -> list[str]:
    """The expedited programs FDA recorded for an approval, as short phrases.

    Reads the columns of FDA's NME compilation, which describe the application
    at the time of original approval. Empty when the row has no compilation
    data (CBER products). Qualified values keep FDA's qualifier, for example
    ``accelerated approval (indication [A] only)``.
    """
    out: list[str] = []
    review = r.get("review_designation")
    if is_priority(review):
        out.append("priority review" + _qualifier(review))
    for column, label in (
        ("orphan_drug_designation", "orphan drug designation"),
        ("accelerated_approval", "accelerated approval"),
        ("breakthrough_therapy_designation", "breakthrough therapy designation"),
        ("fast_track_designation", "fast track designation"),
        (
            "qualified_infectious_disease_product",
            "qualified infectious disease product designation",
        ),
    ):
        value = r.get(column)
        if is_yes(value):
            out.append(label + _qualifier(value))
    return out


_CBER_LEAD_RE = re.compile(r"^s\s*:\s*", re.I)
_CBER_TAIL_RE = re.compile(r"\s*Produc\w+ Information Package.*$", re.S)


def cber_use(text: str | None) -> str:
    """Tidy the indication text scraped from a CBER product page for display.

    The parser now reads the indication from the page's markup, so this is a
    safety net for a page it has to read as flat text: it drops a stray "s:"
    left from "Indications:" and a "Product Information" heading run on to the
    end, and capitalises the first letter. It does not rewrite the indication.
    """
    if not text:
        return ""
    text = _CBER_TAIL_RE.sub("", _CBER_LEAD_RE.sub("", text.strip())).strip()
    return text[:1].upper() + text[1:]


def join_words(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def days_between(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    a = datetime.strptime(start, "%Y-%m-%d")
    b = datetime.strptime(end, "%Y-%m-%d")
    return (b - a).days


_DATE_MODIFIED_RE = re.compile(r'"dateModified": "(\d{4}-\d\d-\d\d)"')


def write_page(path: Path, render, today: str) -> str:
    """Write ``render(date)`` to ``path`` and return the page's modified date.

    ``render`` takes the date to stamp into the page (JSON-LD ``dateModified``
    and the visible "page updated" line). If the page already exists and
    rendering it with its current date reproduces it byte for byte, nothing
    changed, so the old date is kept. That keeps ``dateModified`` and the
    sitemap ``lastmod`` meaning "the content changed", not "the script ran".
    """
    if path.exists():
        old = path.read_text()
        m = _DATE_MODIFIED_RE.search(old)
        if m and render(m.group(1)) == old:
            return m.group(1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(today))
    return today


def jsonld(nodes: list[dict]) -> str:
    return json.dumps(nodes, indent=2, ensure_ascii=False)


def breadcrumbs(items: list[tuple[str, str]]) -> dict:
    """``[(name, path), ...]`` -> a schema.org BreadcrumbList node."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": f"{SITE}{path}"}
            for i, (name, path) in enumerate(items, start=1)
        ],
    }


_FDA_URL_BLOCK_RE = re.compile(
    r"[ \t]*<url>\s*<loc>" + re.escape(SITE) + r"/drugs/[a-z0-9-]+/</loc>.*?</url>[ \t]*\n?",
    re.S,
)


def update_sitemap(entries: list[tuple[str, str, str, str]]) -> int:
    """Regenerate the sitemap entries under ``/drugs/<something>/``.

    ``entries`` is ``(path, lastmod, changefreq, priority)`` for every page the
    FDA scripts generate: per-drug pages, per-year lists, statistics and the
    compilation page. Every other entry, ``/drugs/`` itself included, is kept
    byte for byte: the rest of the sitemap is maintained by hand.
    """
    blocks = "".join(
        "  <url>\n"
        f"    <loc>{SITE}{path}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        "  </url>\n"
        for path, lastmod, changefreq, priority in sorted(entries)
    )
    text = SITEMAP.read_text()
    if "</urlset>" not in text:
        raise SystemExit(f"{SITEMAP} has no </urlset>; refusing to rewrite it")
    text = _FDA_URL_BLOCK_RE.sub("", text)
    text = text.replace("</urlset>", blocks + "</urlset>", 1)
    SITEMAP.write_text(text)
    return len(entries)


def splice(text: str, marker: str, replacement: str) -> str:
    """Replace what is between ``<!-- marker:start -->`` and ``<!-- marker:end -->``."""
    start, end = f"<!-- {marker}:start -->", f"<!-- {marker}:end -->"
    if text.count(start) != 1 or text.count(end) != 1 or text.index(start) > text.index(end):
        raise SystemExit(f"expected exactly one {start} … {end} pair")
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{start}\n{replacement}\n{end}{tail}"


# Shared look: the same variables and type as the hand-written pages.
BASE_CSS = """
    :root { color-scheme: light dark; --bg: #ffffff; --fg: #111111; --muted: #5a5a5a; --border: rgba(127, 127, 127, 0.3); --row-hover: rgba(127, 127, 127, 0.08); }
    @media (prefers-color-scheme: dark) { :root { --bg: #111111; --fg: #f2f2f2; --muted: #adadad; } }
    * { box-sizing: border-box; }
    body { margin: 0 auto; padding: 4rem 1.5rem 6rem; max-width: 44rem; font: 15px/1.6 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background: var(--bg); color: var(--fg); }
    body.wide { max-width: 68rem; }
    .breadcrumb { color: var(--muted); margin: 0 0 1.25rem; font-size: 0.9em; }
    .breadcrumb a { text-decoration: none; }
    .breadcrumb a:hover { text-decoration: underline; }
    h1 { font-size: 2.1rem; line-height: 1.2; margin: 0 0 0.6rem; letter-spacing: -0.025em; font-weight: 700; }
    .subtitle { color: var(--muted); margin: 0 0 1.5rem; font-size: 1.05rem; }
    .lead { font-size: 1.02rem; margin: 0 0 1rem; }
    h2 { font-size: 1.15rem; margin: 2.5rem 0 0.7rem; font-weight: 700; letter-spacing: -0.005em; }
    h3 { font-size: 0.95rem; margin: 1.5rem 0 0.4rem; font-weight: 600; }
    p, li, h1, h2, h3, dd { overflow-wrap: anywhere; }
    td, th { overflow-wrap: break-word; }
    td.use { min-width: 16rem; }
    td.flags { min-width: 9rem; }
    a { color: inherit; }
    a:hover { opacity: 0.7; }
    code { background: var(--border); padding: 0.05em 0.35em; border-radius: 3px; font-size: 0.9em; }
    pre { background: var(--border); padding: 1rem 1.25rem; border-radius: 6px; overflow-x: auto; font-size: 0.85em; line-height: 1.5; }
    pre code { background: none; padding: 0; }
    .muted { color: var(--muted); }
    .note { color: var(--muted); font-size: 0.9em; }
    .callout { border: 1px solid var(--border); border-radius: 6px; padding: 1rem 1.25rem; margin: 1.5rem 0; background: var(--row-hover); }
    .callout p:first-child { margin-top: 0; }
    .callout p:last-child { margin-bottom: 0; }
    .facts { border: 1px solid var(--border); border-radius: 6px; padding: 0.6rem 1.5rem; margin: 0; }
    .facts div { display: flex; gap: 0.8rem; align-items: baseline; padding: 0.4rem 0; border-bottom: 1px solid var(--border); }
    .facts div:last-child { border-bottom: 0; }
    .facts dt { color: var(--muted); min-width: 13rem; font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.05em; }
    .facts dd { margin: 0; }
    .links { list-style: none; padding: 0; margin: 0; }
    .links li { padding: 0.55rem 0; border-bottom: 1px solid var(--border); }
    .links li:last-child { border-bottom: 0; }
    .links .what { display: block; color: var(--muted); font-size: 0.85em; }
    .related { list-style: none; padding: 0; margin: 0; }
    .related li { padding: 0.3rem 0; }
    .when { color: var(--muted); font-size: 0.85em; }
    .scroll { overflow-x: auto; margin: 1rem 0; border: 1px solid var(--border); border-radius: 6px; }
    table { border-collapse: collapse; width: 100%; font-size: 0.88em; }
    caption { caption-side: top; text-align: left; padding: 0.6rem 0.75rem; color: var(--muted); font-size: 0.95em; }
    th, td { text-align: left; vertical-align: top; padding: 0.45rem 0.75rem; border-bottom: 1px solid var(--border); }
    th { font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); font-weight: 600; white-space: nowrap; }
    tbody tr:last-child td { border-bottom: 0; }
    tbody tr:hover { background: var(--row-hover); }
    td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
    td.nowrap { white-space: nowrap; }
    .yearnav { display: flex; flex-wrap: wrap; gap: 0.35rem 0.9rem; padding: 0; margin: 0.5rem 0 0; list-style: none; font-size: 0.92em; }
    footer { margin-top: 4rem; padding-top: 1.5rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.85em; }
    footer p { margin: 0 0 0.5rem; }
    @media (max-width: 640px) {
      body { padding-top: 2.5rem; }
      h1 { font-size: 1.65rem; }
      .facts div { flex-direction: column; gap: 0.1rem; }
      .facts dt { min-width: auto; }
    }
"""


def page_shell(
    *,
    title: str,
    description: str,
    path: str,
    og_title: str,
    nodes: list[dict],
    crumbs_html: str,
    body: str,
    footer: str,
    markdown_path: str | None = None,
    wide: bool = False,
) -> str:
    """One complete HTML document in the site's shared look."""
    canonical = f"{SITE}{path}"
    alt = (
        f'\n  <link rel="alternate" type="text/markdown" href="{esc(markdown_path)}">'
        if markdown_path
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="canonical" href="{canonical}">{alt}
  <meta property="og:type" content="article">
  <meta property="og:title" content="{esc(og_title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{OG_IMAGE}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(og_title)}">
  <meta name="twitter:description" content="{esc(description)}">
  <meta name="twitter:image" content="{OG_IMAGE}">
  <script type="application/ld+json">
{jsonld(nodes)}
  </script>
  <style>{BASE_CSS}  </style>
</head>
<body{' class="wide"' if wide else ""}>
  <p class="breadcrumb">{crumbs_html}</p>

{body}

  <footer>
{footer}
  </footer>

  <script defer src="/_vercel/insights/script.js"></script>
  <script defer src="/_vercel/speed-insights/script.js"></script>
</body>
</html>
"""


def standard_footer(modified: str, extra: str = "") -> str:
    return f"""    <p><a href="/drugs/">← FDA drug approvals</a> · <a href="/drugs/statistics/">Approval statistics</a> · <a href="/drugs/compilation/">Download the data</a> · <a href="/">trove home</a> · <a href="{REPO_URL}">Source on GitHub</a></p>
{extra}    <p>Page updated {esc(fmt_date_long(modified))}. Built by <a href="https://github.com/cbetz">Chris Betz</a> on personal time. Not medical advice; FDA's own documents are the source of truth. Corrections: <a href="{REPO_URL}/issues">github.com/cbetz/trove/issues</a>.</p>
    <p>Source: U.S. Food and Drug Administration. U.S. government work, public domain.</p>"""
