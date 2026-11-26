"""Generate the list pages of the FDA section.

- ``web/drugs/<year>/`` — every novel drug FDA approved that calendar year,
  1985 onward, as a static table.
- ``web/drugs/statistics/`` — approvals per year, review designations and
  receipt-to-approval times, computed from FDA's compilation.
- ``web/drugs/compilation/`` — download page for FDA's Compilation of CDER NME
  and New Biologic Approvals as CSV and Parquet.
- The static, crawlable list of approvals inside ``web/drugs/index.html``.

Each page also gets a Markdown twin (``index.md``) with the same facts.

Inputs are the published bundles: ``web/data/fda_approvals_nme_recent.json``
(the per-drug index) and ``web/data/fda_nme_compilation.csv``. Run through
``build_drug_pages.py``, which owns the sitemap entries for all of them.
"""

from __future__ import annotations

import csv
import json
import statistics
from email.utils import parsedate_to_datetime
from pathlib import Path

from fda_site_common import (
    CBER_PRODUCTS_URL,
    COMPILATION_PAGE_URL,
    DRUGS_AT_FDA_URL,
    DRUGS_DIR,
    NOVEL_APPROVALS_URL,
    PERSON,
    PUBLISHER,
    REPO_URL,
    SITE,
    breadcrumbs,
    cber_use,
    designations,
    esc,
    fmt_date,
    fmt_date_long,
    is_priority,
    is_yes,
    join_words,
    page_shell,
    slugify,
    splice,
    standard_footer,
    title_case,
    write_page,
)

COMPILATION_CSV = Path("web/data/fda_nme_compilation.csv")
COMPILATION_SOURCE = Path("web/data/fda_nme_compilation_source.json")
DRUGS_INDEX = Path("web/drugs/index.html")
RESERVED_SLUGS = {"statistics", "compilation"}

_FLAG_SHORT = {
    "priority review": None,  # shown in its own column
    "orphan drug designation": "Orphan",
    "accelerated approval": "Accelerated approval",
    "breakthrough therapy designation": "Breakthrough",
    "fast track designation": "Fast track",
    "qualified infectious disease product designation": "QIDP",
}


def load_compilation() -> tuple[list[dict], dict]:
    with COMPILATION_CSV.open(newline="") as f:
        rows = [{k: (v or None) for k, v in r.items()} for r in csv.DictReader(f)]
    for r in rows:
        r["approval_year"] = int(r["approval_year"])
        days = r["days_receipt_to_approval"]
        r["days_receipt_to_approval"] = int(days) if days else None
    return rows, json.loads(COMPILATION_SOURCE.read_text())


def source_date(source: dict) -> str:
    """ISO date FDA last modified the compilation file (falls back to fetch date)."""
    stamp = source["source"].get("last_modified")
    if stamp:
        return parsedate_to_datetime(stamp).date().isoformat()
    return source["source"]["fetched"]


def short_use(text: str | None, limit: int = 260) -> str:
    """First line of an indication, cut at a sentence or word boundary."""
    if not text:
        return ""
    first = text.splitlines()[0].strip()
    if len(first) <= limit:
        return first
    cut = first[:limit]
    stop = cut.rfind(". ")
    if stop > limit // 2:
        return cut[: stop + 1]
    return cut[: cut.rfind(" ")].rstrip(",;:") + "…"


def flag_labels(r: dict) -> list[str]:
    """Short designation labels for a table cell (priority review excluded)."""
    out = []
    for phrase in designations(r):
        for long, short in _FLAG_SHORT.items():
            if phrase.startswith(long):
                if short:
                    out.append(short + phrase[len(long) :])
                break
    return out


def review_label(r: dict) -> str:
    value = r.get("review_designation")
    return value or "—"


# --- statistics -------------------------------------------------------------


def _median(values: list[int]) -> int | None:
    return round(statistics.median(values)) if values else None


def summarize(rows: list[dict]) -> dict:
    """Counts for one set of compilation rows (a year, a period, everything)."""
    n = len(rows)

    def count(column: str) -> int | None:
        values = [r.get(column) for r in rows]
        # FDA writes N/A for approvals that predate a program. A set that is
        # all N/A has no count; show a dash, not a zero.
        if all((v or "N/A").strip() == "N/A" for v in values):
            return None
        return sum(1 for v in values if is_yes(v))

    days = [r["days_receipt_to_approval"] for r in rows if r["days_receipt_to_approval"]]
    return {
        "n": n,
        "nda": sum(1 for r in rows if r["application_type"] == "NDA"),
        "bla": sum(1 for r in rows if r["application_type"] == "BLA"),
        "priority": sum(1 for r in rows if is_priority(r.get("review_designation"))),
        "orphan": count("orphan_drug_designation"),
        "accelerated": count("accelerated_approval"),
        "breakthrough": count("breakthrough_therapy_designation"),
        "fast_track": count("fast_track_designation"),
        "median_days": _median(days),
    }


def pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "—"


def dash(value: int | None) -> str:
    return "—" if value is None else f"{value:,}"


def months(days: int) -> str:
    return f"{days / 30.44:.1f}"


# --- per-year pages ---------------------------------------------------------


def _year_rows(year: int, index_rows: list[dict], comp_rows: list[dict]) -> list[dict]:
    """CDER rows for ``year``: from the per-drug index when it covers the year."""
    idx = [r for r in index_rows if r["year"] == year and r["regulatory_center"] == "CDER"]
    if idx:
        return [
            {
                **r,
                "name": r["drug_name"],
                "slug": slugify(r["drug_name"]),
                "applicant": title_case(r.get("sponsor")),
                "date": r["approval_date"],
                "use": r.get("indication") or "",
            }
            for r in sorted(idx, key=lambda r: (r["approval_date"], r["drug_name"]))
        ]
    return [
        {
            **r,
            "name": r["proprietary_name"],
            "slug": None,
            "date": r["fda_approval_date"],
            "use": short_use(r.get("approved_use") or r.get("abbreviated_indication")),
        }
        for r in comp_rows
        if r["approval_year"] == year
    ]


def _drug_cell(r: dict) -> str:
    name = esc(r["name"])
    if r["slug"]:
        name = f'<a href="/drugs/{r["slug"]}/">{name}</a>'
    return f'{name}<br><span class="muted">{esc(r.get("active_ingredient") or "")}</span>'


def _year_lead(year: int, s: dict, cber_n: int) -> list[str]:
    parts = [
        f"FDA's Center for Drug Evaluation and Research (CDER) approved <strong>{s['n']} novel "
        f"drugs in {year}</strong>: {s['nda']} under new drug applications (NDAs) and {s['bla']} "
        f"under biologics license applications (BLAs)."
    ]
    facts = [f"{s['priority']} of the {s['n']} ({pct(s['priority'], s['n'])}) had priority review"]
    for key, label in (
        ("orphan", "had orphan drug designation"),
        ("accelerated", "were accelerated approvals"),
        ("breakthrough", "had breakthrough therapy designation"),
        ("fast_track", "had fast track designation"),
    ):
        if s[key] is not None:
            facts.append(f"{s[key]} {label}")
    sentence = join_words(facts) + "."
    if s["median_days"]:
        sentence += (
            f" The median time from FDA's receipt of the application to approval was "
            f"{s['median_days']:,} days (about {months(s['median_days'])} months)."
        )
    parts.append(sentence)
    if cber_n:
        parts.append(
            f"FDA's Center for Biologics Evaluation and Research (CBER) separately approved "
            f"{cber_n} cell and gene therapy product{'s' if cber_n != 1 else ''} in {year}, "
            f"listed in the second table."
        )
    return parts


def _strip_tags(s: str) -> str:
    return s.replace("<strong>", "").replace("</strong>", "")


def render_year(
    year: int,
    years: list[int],
    index_rows: list[dict],
    comp_rows: list[dict],
    vintage: str,
    modified: str,
) -> tuple[str, str]:
    """Return ``(html, markdown)`` for one year's page."""
    rows = _year_rows(year, index_rows, comp_rows)
    comp_year = [r for r in comp_rows if r["approval_year"] == year]
    s = summarize(comp_year)
    if s["n"] != len(rows):
        raise SystemExit(f"{year}: index has {len(rows)} CDER rows, FDA's compilation {s['n']}")
    cber = sorted(
        (r for r in index_rows if r["year"] == year and r["regulatory_center"] == "CBER"),
        key=lambda r: (r["approval_date"], r["drug_name"]),
    )
    has_pages = any(r["slug"] for r in rows)
    path = f"/drugs/{year}/"
    title = f"FDA novel drug approvals {year}: all {s['n']} NMEs and new biologics | trove"
    description = (
        f"Every novel drug FDA's CDER approved in {year}: {s['n']} new molecular entities and "
        f"new biologics"
        + (f", plus {len(cber)} CBER cell and gene therapies" if cber else "")
        + ". Approval date, applicant, application number, review designation and approved use."
    )
    lead = _year_lead(year, s, len(cber))

    body_rows = "\n".join(
        "        <tr>"
        f'<td class="nowrap">{esc(fmt_date(r["date"]))}</td>'
        f"<td>{_drug_cell(r)}</td>"
        f"<td>{esc(r.get('applicant') or '')}</td>"
        f'<td class="nowrap">{esc(r["application_type"])} {esc(r["application_number"])}</td>'
        f"<td>{esc(review_label(r))}</td>"
        f'<td class="flags">{esc(", ".join(flag_labels(r)) or "—")}</td>'
        f'<td class="use">{esc(r["use"])}</td>'
        "</tr>"
        for r in rows
    )
    cber_html = ""
    if cber:
        cber_rows = "\n".join(
            "        <tr>"
            f'<td class="nowrap">{esc(fmt_date(r["approval_date"]))}</td>'
            f'<td><a href="/drugs/{slugify(r["drug_name"])}/">{esc(r["drug_name"])}</a><br>'
            f'<span class="muted">{esc(r.get("active_ingredient") or "")}</span></td>'
            f"<td>{esc(title_case(r.get('sponsor')))}</td>"
            f'<td class="nowrap">BLA {esc(r.get("application_number") or "—")}</td>'
            f'<td class="use">{esc(short_use(cber_use(r.get("indication"))))}</td>'
            "</tr>"
            for r in cber
        )
        cber_html = f"""
  <h2>Cell and gene therapies approved by CBER in {year}</h2>
  <p>These {len(cber)} products are licensed by FDA's Center for Biologics Evaluation and Research. They are not part of CDER's novel drug count above, and FDA's compilation does not record review designations for them. Source: FDA, <a href="{CBER_PRODUCTS_URL}">Approved Cellular and Gene Therapy Products</a>.</p>
  <div class="scroll">
    <table>
      <caption>CBER cell and gene therapy approvals, {year}, in order of approval</caption>
      <thead><tr><th>Approved</th><th>Product</th><th>Manufacturer</th><th>Application</th><th>FDA-approved use</th></tr></thead>
      <tbody>
{cber_rows}
      </tbody>
    </table>
  </div>"""

    i = years.index(year)
    nav = []
    if i > 0:
        nav.append(f'<a href="/drugs/{years[i - 1]}/">← {years[i - 1]}</a>')
    if i < len(years) - 1:
        nav.append(f'<a href="/drugs/{years[i + 1]}/">{years[i + 1]} →</a>')
    all_years = "\n".join(
        f"    <li>{y}</li>" if y == year else f'    <li><a href="/drugs/{y}/">{y}</a></li>'
        for y in reversed(years)
    )
    use_note = (
        "The approved use is FDA's one-line summary from its annual Novel Drug Approvals list."
        if has_pages
        else "The approved use is the first sentence of the indication FDA recorded at original "
        "approval; later indications are not listed."
    )
    link_note = (
        " Each drug name links to a page with its label, approval letter and FDA review documents."
        if has_pages
        else ""
    )
    body = f"""  <header>
    <h1>FDA novel drug approvals in {year}</h1>
    <p class="subtitle">Every new molecular entity and new biologic approved by FDA's CDER in calendar year {year}.</p>
  </header>

  <p class="lead">{lead[0]}</p>
  {"".join(f"<p>{p}</p>" for p in lead[1:])}

  <h2>List of {year} novel drug approvals (CDER)</h2>
  <p class="note">In order of approval. Review designation and the expedited-program columns describe each application at the time of original approval, as FDA records them in its <a href="/drugs/compilation/">compilation of CDER NME and new biologic approvals</a>. {use_note}{link_note}</p>
  <div class="scroll">
    <table>
      <caption>CDER novel drug approvals, {year}: {s["n"]} approvals</caption>
      <thead><tr><th>Approved</th><th>Drug</th><th>Applicant</th><th>Application</th><th>Review</th><th>Expedited programs</th><th>FDA-approved use</th></tr></thead>
      <tbody>
{body_rows}
      </tbody>
    </table>
  </div>
{cber_html}

  <h2>What counts as a novel drug approval</h2>
  <p>FDA uses "novel" for drugs never before approved or marketed in the United States. This list is CDER's count of new molecular entities and new therapeutic biologics. It leaves out generics, biosimilars, new formulations and new indications of drugs already approved, and products licensed by CBER such as vaccines, blood products and cell and gene therapies. See <a href="/docs/new-molecular-entity/">what a new molecular entity is</a> and <a href="/docs/fda-nme/">what an FDA novel drug approval is</a>.</p>

  <h2>Other years</h2>
  <p>{" · ".join(nav)} · <a href="/drugs/statistics/">Approvals per year, 1985–{years[-1]}</a></p>
  <ul class="yearnav">
{all_years}
  </ul>

  <h2>Download this list</h2>
  <p>All {year} rows are in <a href="/data/fda_nme_compilation.csv">fda_nme_compilation.csv</a> and <a href="/data/fda_nme_compilation.parquet">fda_nme_compilation.parquet</a> (filter <code>approval_year = {year}</code>). Column definitions are on the <a href="/drugs/compilation/">compilation page</a>.</p>"""

    extra = (
        f'    <p>Data: FDA, <a href="{COMPILATION_PAGE_URL}">Compilation of CDER NME and New Biologic Approvals</a>, '
        f"file dated {esc(fmt_date_long(vintage))}"
        + (
            f'; <a href="{NOVEL_APPROVALS_URL}">Novel Drug Approvals</a> annual list'
            if has_pages
            else ""
        )
        + ".</p>\n"
    )
    nodes = [
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": f"FDA novel drug approvals in {year}",
            "description": description,
            "url": f"{SITE}{path}",
            "isPartOf": {"@type": "WebSite", "name": "trove", "url": f"{SITE}/"},
            "author": PERSON,
            "publisher": PUBLISHER,
            "dateModified": modified,
            "isBasedOn": COMPILATION_PAGE_URL,
        },
        breadcrumbs([("trove", "/"), ("FDA drug approvals", "/drugs/"), (str(year), path)]),
    ]
    if has_pages:
        nodes.append(
            {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "name": f"CDER novel drug approvals, {year}",
                "numberOfItems": len(rows),
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": k,
                        "name": r["name"],
                        "url": f"{SITE}/drugs/{r['slug']}/",
                    }
                    for k, r in enumerate(rows, start=1)
                ],
            }
        )
    page = page_shell(
        title=title,
        description=description,
        path=path,
        og_title=f"FDA novel drug approvals in {year}",
        nodes=nodes,
        crumbs_html=f'<a href="/">trove</a> / <a href="/drugs/">FDA drug approvals</a> / {year}',
        body=body,
        footer=standard_footer(modified, extra),
        markdown_path=f"{path}index.md",
        wide=True,
    )

    def md_cell(s: object) -> str:
        return str(s or "").replace("|", "\\|").replace("\n", " ")

    md = [
        f"# FDA novel drug approvals in {year}",
        "",
        *[_strip_tags(p) + "\n" for p in lead],
        f"## List of {year} novel drug approvals (CDER)",
        "",
        "| Approved | Drug | Active ingredient | Applicant | Application | Review | Expedited programs | FDA-approved use |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        name = (
            f"[{md_cell(r['name'])}]({SITE}/drugs/{r['slug']}/)"
            if r["slug"]
            else md_cell(r["name"])
        )
        md.append(
            f"| {r['date']} | {name} | {md_cell(r.get('active_ingredient'))} | "
            f"{md_cell(r.get('applicant'))} | {r['application_type']} {r['application_number']} | "
            f"{md_cell(review_label(r))} | {md_cell(', '.join(flag_labels(r)) or '—')} | {md_cell(r['use'])} |"
        )
    if cber:
        md += [
            "",
            f"## Cell and gene therapies approved by CBER in {year}",
            "",
            "| Approved | Product | Active ingredient | Manufacturer | Application | FDA-approved use |",
            "|---|---|---|---|---|---|",
        ]
        for r in cber:
            md.append(
                f"| {r['approval_date']} | [{md_cell(r['drug_name'])}]({SITE}/drugs/{slugify(r['drug_name'])}/) | "
                f"{md_cell(r.get('active_ingredient'))} | {md_cell(title_case(r.get('sponsor')))} | "
                f"BLA {md_cell(r.get('application_number') or '—')} | "
                f"{md_cell(short_use(cber_use(r.get('indication'))))} |"
            )
    md += [
        "",
        f"Source: FDA, Compilation of CDER NME and New Biologic Approvals ({COMPILATION_PAGE_URL}), "
        f"file dated {fmt_date_long(vintage)}. Page: {SITE}{path} (updated {modified}). "
        f"Data: {SITE}/data/fda_nme_compilation.csv",
        "",
    ]
    return page, "\n".join(md)


# --- statistics page --------------------------------------------------------


def _periods(years: list[int]) -> list[tuple[str, list[int]]]:
    out = []
    start = years[0]
    while start <= years[-1]:
        end = min(start + (9 - start % 10), years[-1])
        span = [y for y in years if start <= y <= end]
        out.append((f"{span[0]}–{span[-1]}", span))
        start = end + 1
    return out


def compute_statistics(comp_rows: list[dict]) -> dict:
    years = sorted({r["approval_year"] for r in comp_rows})
    by_year = {y: summarize([r for r in comp_rows if r["approval_year"] == y]) for y in years}
    counts = {y: by_year[y]["n"] for y in years}
    last10 = years[-10:]
    recent = [r for r in comp_rows if r["approval_year"] in last10]
    recent_priority = [r for r in recent if is_priority(r.get("review_designation"))]
    recent_standard = [r for r in recent if not is_priority(r.get("review_designation"))]

    def med(rows: list[dict]) -> int | None:
        return _median(
            [r["days_receipt_to_approval"] for r in rows if r["days_receipt_to_approval"]]
        )

    return {
        "years": years,
        "by_year": by_year,
        "all": summarize(comp_rows),
        "max_n": max(counts.values()),
        "max_years": [y for y in years if counts[y] == max(counts.values())],
        "min_n": min(counts.values()),
        "min_years": [y for y in years if counts[y] == min(counts.values())],
        "periods": [
            (label, len(span), summarize([r for r in comp_rows if r["approval_year"] in span]))
            for label, span in _periods(years)
        ],
        "last10": last10,
        "recent": summarize(recent),
        "recent_counts": [counts[y] for y in last10],
        "recent_median_priority": med(recent_priority),
        "recent_median_standard": med(recent_standard),
        "recent_n_priority": len(recent_priority),
        "recent_n_standard": len(recent_standard),
    }


def render_statistics(comp_rows: list[dict], vintage: str, modified: str) -> tuple[str, str]:
    st = compute_statistics(comp_rows)
    years, a, rec = st["years"], st["all"], st["recent"]
    y0, y1 = years[0], years[-1]
    r0, r1 = st["last10"][0], st["last10"][-1]
    latest = st["by_year"][y1]
    path = "/drugs/statistics/"
    title = f"FDA drug approval statistics: novel approvals per year, {y0}–{y1} | trove"
    description = (
        f"FDA approved {a['n']:,} novel drugs from {y0} through {y1}. Approvals per year, NDA and "
        f"BLA counts, priority review, orphan, accelerated approval, breakthrough and fast track "
        f"shares, and receipt-to-approval times, from FDA's own compilation."
    )
    mean_all = a["n"] / len(years)
    mean_recent = rec["n"] / len(st["last10"])
    lead = (
        f"FDA's Center for Drug Evaluation and Research (CDER) approved <strong>{a['n']:,} novel "
        f"drugs from {y0} through {y1}</strong>: {a['nda']:,} under new drug applications (NDAs) "
        f"and {a['bla']:,} under biologics license applications (BLAs). That is an average of "
        f"{mean_all:.1f} a year. The most in one year was {st['max_n']} "
        f"({join_words([str(y) for y in st['max_years']])}); the fewest was {st['min_n']} "
        f"({join_words([str(y) for y in st['min_years']])}). In {y1} CDER approved {latest['n']}."
    )
    q_per_year = (
        f"From {r0} through {r1}, CDER approved an average of {mean_recent:.1f} novel drugs a "
        f"year, ranging from {min(st['recent_counts'])} to {max(st['recent_counts'])}. Over the "
        f"full {y0}–{y1} record the average is {mean_all:.1f} a year."
    )
    q_time = (
        f"For the {rec['n']} novel drugs CDER approved from {r0} through {r1}, the median time "
        f"from FDA's receipt of the application to approval was {rec['median_days']:,} days "
        f"(about {months(rec['median_days'])} months). It was {st['recent_median_priority']:,} "
        f"days for the {st['recent_n_priority']} applications with priority review and "
        f"{st['recent_median_standard']:,} days for the {st['recent_n_standard']} with standard "
        f"review."
    )
    q_share = (
        f"Of the {rec['n']} novel drugs approved from {r0} through {r1}, "
        f"{rec['priority']} ({pct(rec['priority'], rec['n'])}) had priority review, "
        f"{rec['orphan']} ({pct(rec['orphan'], rec['n'])}) had orphan drug designation, "
        f"{rec['fast_track']} ({pct(rec['fast_track'], rec['n'])}) had fast track designation, "
        f"{rec['breakthrough']} ({pct(rec['breakthrough'], rec['n'])}) had breakthrough therapy "
        f"designation and {rec['accelerated']} ({pct(rec['accelerated'], rec['n'])}) were "
        f"accelerated approvals. One drug can have several of these."
    )
    q_total = (
        f"This page counts novel approvals only: {a['n']:,} new molecular entities and new "
        f"biologics approved by CDER since {y0}. It is not a count of every drug product FDA has "
        f"approved. Generics, biosimilars, new formulations, new indications and products "
        f"licensed by CBER (vaccines, blood products, cell and gene therapies) are outside it; "
        f"Drugs@FDA lists all CDER-approved products."
    )

    def year_row(y: int) -> str:
        s = st["by_year"][y]
        return (
            "        <tr>"
            f'<td><a href="/drugs/{y}/">{y}</a></td>'
            f'<td class="num">{s["n"]}</td><td class="num">{s["nda"]}</td><td class="num">{s["bla"]}</td>'
            f'<td class="num">{s["priority"]} ({pct(s["priority"], s["n"])})</td>'
            f'<td class="num">{dash(s["orphan"])}</td><td class="num">{dash(s["accelerated"])}</td>'
            f'<td class="num">{dash(s["breakthrough"])}</td><td class="num">{dash(s["fast_track"])}</td>'
            f'<td class="num">{dash(s["median_days"])}</td>'
            "</tr>"
        )

    year_rows = "\n".join(year_row(y) for y in reversed(years))
    period_rows = "\n".join(
        "        <tr>"
        f"<td>{label}</td>"
        f'<td class="num">{s["n"]:,}</td><td class="num">{s["n"] / n_years:.1f}</td>'
        f'<td class="num">{pct(s["bla"], s["n"])}</td><td class="num">{pct(s["priority"], s["n"])}</td>'
        f'<td class="num">{pct(s["orphan"] or 0, s["n"])}</td><td class="num">{dash(s["median_days"])}</td>'
        "</tr>"
        for label, n_years, s in st["periods"]
    )
    body = f"""  <header>
    <h1>FDA drug approval statistics, {y0}–{y1}</h1>
    <p class="subtitle">Novel drug approvals per year, review designations and review times, computed from FDA's own compilation.</p>
  </header>

  <p class="lead">{lead}</p>
  <p class="note">"Novel" here means new molecular entities and new therapeutic biologics approved by CDER, as listed in FDA's <a href="/drugs/compilation/">Compilation of CDER NME and New Biologic Approvals</a> (file dated {esc(fmt_date_long(vintage))}). Every figure on this page is a count over that file; the <a href="/data/fda_nme_compilation.csv">CSV</a> is one click away if you want to check one.</p>

  <h2>How many novel drugs does the FDA approve each year?</h2>
  <p>{q_per_year}</p>

  <h2>How long does FDA take to approve a novel drug?</h2>
  <p>{q_time}</p>
  <p class="note">FDA defines the receipt date as the date "the first and complete marketing application was received by FDA". The span is calendar days from that date to original approval.</p>

  <h2>How many novel approvals use priority review, orphan designation or an expedited program?</h2>
  <p>{q_share}</p>

  <h2>How many drugs has the FDA approved in total?</h2>
  <p>{q_total}</p>

  <h2>FDA novel drug approvals by year</h2>
  <div class="scroll">
    <table>
      <caption>CDER novel drug approvals by calendar year, {y1} back to {y0}. A dash means the program did not exist yet for any approval that year.</caption>
      <thead><tr><th>Year</th><th class="num">Approvals</th><th class="num">NDA</th><th class="num">BLA</th><th class="num">Priority review</th><th class="num">Orphan</th><th class="num">Accelerated approval</th><th class="num">Breakthrough</th><th class="num">Fast track</th><th class="num">Median days, receipt to approval</th></tr></thead>
      <tbody>
{year_rows}
      </tbody>
    </table>
  </div>

  <h2>Approvals by period</h2>
  <div class="scroll">
    <table>
      <caption>CDER novel drug approvals by period. The first and last periods are shorter than ten years.</caption>
      <thead><tr><th>Period</th><th class="num">Approvals</th><th class="num">Per year</th><th class="num">BLA share</th><th class="num">Priority review share</th><th class="num">Orphan share</th><th class="num">Median days, receipt to approval</th></tr></thead>
      <tbody>
{period_rows}
      </tbody>
    </table>
  </div>

  <h2>How to read these numbers</h2>
  <ul>
    <li><strong>State at original approval.</strong> FDA's compilation records each application as it stood when first approved. Indications, designations and withdrawals after that date are not reflected.</li>
    <li><strong>Programs have start dates.</strong> FDA lists accelerated approval as not applicable before April 15, 1992, fast track before November 21, 1997, and breakthrough therapy before July 9, 2012. Counts for years that straddle a start date cover only the approvals after it.</li>
    <li><strong>Priority review before 1992.</strong> The priority and standard labels date from the 1992 user-fee law. For 1985–1991 FDA maps its older A/B/C ratings onto them: types A and B count as priority, type C as standard.</li>
    <li><strong>Orphan designation</strong> means the sponsor held orphan designation for at least one of the indications approved at original approval.</li>
    <li><strong>CDER only.</strong> Vaccines, blood products, and cell and gene therapies are licensed by CBER and are not in these counts. The <a href="/drugs/">per-drug index</a> lists CBER cell and gene therapy approvals for the years it covers.</li>
  </ul>

  <h2>Get the data</h2>
  <p>Download <a href="/data/fda_nme_compilation.csv">fda_nme_compilation.csv</a> or <a href="/data/fda_nme_compilation.parquet">fda_nme_compilation.parquet</a>, or read the <a href="/drugs/compilation/">column definitions</a>. The year table above reproduces with one query:</p>
<pre><code>SELECT approval_year, count(*) AS approvals,
       count(*) FILTER (WHERE review_designation LIKE 'Priority%') AS priority,
       median(days_receipt_to_approval) AS median_days
FROM '{SITE}/data/fda_nme_compilation.parquet'
GROUP BY 1 ORDER BY 1 DESC;</code></pre>"""

    extra = (
        f'    <p>Data: FDA, <a href="{COMPILATION_PAGE_URL}">Compilation of CDER NME and New Biologic Approvals</a>, '
        f"file dated {esc(fmt_date_long(vintage))}. Counts computed by trove from that file.</p>\n"
    )
    nodes = [
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": f"FDA drug approval statistics, {y0}–{y1}",
            "description": description,
            "url": f"{SITE}{path}",
            "author": PERSON,
            "publisher": PUBLISHER,
            "dateModified": modified,
            "isBasedOn": [COMPILATION_PAGE_URL, f"{SITE}/drugs/compilation/"],
        },
        breadcrumbs([("trove", "/"), ("FDA drug approvals", "/drugs/"), ("Statistics", path)]),
    ]
    page = page_shell(
        title=title,
        description=description,
        path=path,
        og_title=f"FDA drug approval statistics, {y0}–{y1}",
        nodes=nodes,
        crumbs_html='<a href="/">trove</a> / <a href="/drugs/">FDA drug approvals</a> / Statistics',
        body=body,
        footer=standard_footer(modified, extra),
        markdown_path=f"{path}index.md",
        wide=True,
    )
    md = [
        f"# FDA drug approval statistics, {y0}–{y1}",
        "",
        _strip_tags(lead),
        "",
        "## How many novel drugs does the FDA approve each year?",
        "",
        q_per_year,
        "",
        "## How long does FDA take to approve a novel drug?",
        "",
        q_time,
        "",
        "## How many novel approvals use priority review, orphan designation or an expedited program?",
        "",
        q_share,
        "",
        "## How many drugs has the FDA approved in total?",
        "",
        q_total,
        "",
        "## FDA novel drug approvals by year",
        "",
        "| Year | Approvals | NDA | BLA | Priority review | Orphan | Accelerated approval | Breakthrough | Fast track | Median days, receipt to approval |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for y in reversed(years):
        s = st["by_year"][y]
        md.append(
            f"| {y} | {s['n']} | {s['nda']} | {s['bla']} | {s['priority']} | {dash(s['orphan'])} | "
            f"{dash(s['accelerated'])} | {dash(s['breakthrough'])} | {dash(s['fast_track'])} | "
            f"{dash(s['median_days'])} |"
        )
    md += [
        "",
        f"Source: FDA, Compilation of CDER NME and New Biologic Approvals ({COMPILATION_PAGE_URL}), "
        f"file dated {fmt_date_long(vintage)}; counts computed by trove. Page: {SITE}{path} "
        f"(updated {modified}). Data: {SITE}/data/fda_nme_compilation.csv",
        "",
    ]
    return page, "\n".join(md)


# --- compilation download page ----------------------------------------------

# (column, what it holds). Summarised from FDA's data dictionary.
_COLUMN_NOTES = [
    ("approval_year", "Calendar year of the FDA approval date."),
    (
        "proprietary_name",
        'Brand name. FDA writes "[drug marketed without a proprietary name]" when there is none.',
    ),
    (
        "active_ingredient",
        "Active ingredient or active moiety, named as in structured product labeling.",
    ),
    ("applicant", "The company named in the approval letter. FDA may simplify the name."),
    ("application_type", "NDA (new drug application) or BLA (biologics license application)."),
    (
        "application_number, _2, _3",
        "FDA application numbers, zero-padded to the six digits Drugs@FDA uses. A product approved in more than one dosage form can have several.",
    ),
    (
        "dosage_form, route_of_administration (and _2, _3)",
        "Dosage form and route for each application number, in the same order.",
    ),
    ("fda_receipt_date", "Date FDA received the first complete marketing application (ISO date)."),
    ("fda_approval_date", "Date FDA originally approved the application (ISO date)."),
    (
        "days_receipt_to_approval",
        "Added by trove: calendar days from fda_receipt_date to fda_approval_date.",
    ),
    (
        "abbreviated_indication",
        "Short indication from the approval letter or original labeling. Filled for approvals before October 1, 2007.",
    ),
    (
        "approved_use",
        "Indications and Usage text of the label at original approval. Filled for approvals from October 1, 2007.",
    ),
    (
        "review_designation",
        "Priority or Standard at the time of approval. For 1985–1991, FDA maps its older type A and B ratings to Priority and type C to Standard.",
    ),
    (
        "orphan_drug_designation",
        "Yes if the sponsor held orphan designation for at least one initially approved indication.",
    ),
    ("accelerated_approval", "Yes, No, or N/A for approvals before April 15, 1992."),
    ("breakthrough_therapy_designation", "Yes, No, or N/A for approvals before July 9, 2012."),
    ("fast_track_designation", "Yes, No, or N/A for approvals before November 21, 1997."),
    ("qualified_infectious_disease_product", "Yes, No, or N/A for approvals before July 9, 2012."),
    (
        "priority_review_voucher_issued",
        "TD (tropical disease), RPD (rare pediatric disease) or MTMC (material threat medical countermeasure) when the approval earned a voucher; N/A before September 27, 2007.",
    ),
    (
        "priority_review_voucher_redeemed",
        "Yes when the application got priority review by redeeming a voucher.",
    ),
    ("notes", "FDA's notes, mostly products moved from NDA to BLA in March 2020."),
]


def render_compilation(
    comp_rows: list[dict], source: dict, vintage: str, modified: str
) -> tuple[str, str]:
    years = sorted({r["approval_year"] for r in comp_rows})
    y0, y1 = years[0], years[-1]
    n = len(comp_rows)
    src = source["source"]
    path = "/drugs/compilation/"
    title = (
        f"FDA compilation of CDER NME and new biologic approvals {y0}–{y1}: CSV download | trove"
    )
    description = (
        f"FDA's Compilation of CDER NME and New Biologic Approvals, {y0}–{y1}, converted from "
        f"FDA's Excel file to CSV and Parquet: {n:,} approvals with dates, applicant, application "
        f"number, review designation, orphan, accelerated approval, breakthrough and fast track."
    )
    lead = (
        f"This is FDA's <strong>Compilation of CDER NME and New Biologic Approvals, {y0}–{y1}</strong>, "
        f"as CSV and Parquet. FDA publishes the compilation as an Excel workbook only. The files "
        f"here hold the same {n:,} approvals, one row each, with ISO dates and application "
        f"numbers that match Drugs@FDA."
    )
    col_rows = "\n".join(
        f"        <tr><td><code>{esc(c)}</code></td><td>{esc(note)}</td></tr>"
        for c, note in _COLUMN_NOTES
    )
    file_name = src.get("file_name") or "FDA's workbook"
    body = f"""  <header>
    <h1>FDA compilation of CDER NME and new biologic approvals, {y0}–{y1}, as CSV</h1>
    <p class="subtitle">Every new molecular entity and new biologic approved by FDA's CDER since {y0}, in formats you can load directly.</p>
  </header>

  <p class="lead">{lead}</p>

  <h2>Download</h2>
  <ul class="links">
    <li><a href="/data/fda_nme_compilation.csv">fda_nme_compilation.csv</a><span class="what">CSV, UTF-8, {n:,} rows. Opens in Excel, R, pandas, DuckDB.</span></li>
    <li><a href="/data/fda_nme_compilation.parquet">fda_nme_compilation.parquet</a><span class="what">Parquet, zstd. Query it over HTTPS without downloading.</span></li>
    <li><a href="/data/fda_nme_compilation_source.json">fda_nme_compilation_source.json</a><span class="what">Which FDA file this came from: name, date, SHA-256, row counts by year.</span></li>
    <li><a href="{COMPILATION_PAGE_URL}" rel="noopener">FDA's original workbook and data dictionary ↗</a><span class="what">The source. FDA's page links the current Excel file and the PDF data dictionary.</span></li>
  </ul>
<pre><code># DuckDB: approvals per year, straight from the URL
SELECT approval_year, count(*) FROM '{SITE}/data/fda_nme_compilation.parquet' GROUP BY 1 ORDER BY 1;

# pandas: keep application numbers as text so leading zeros survive
import pandas as pd
df = pd.read_csv("{SITE}/data/fda_nme_compilation.csv", dtype={{"application_number": str}})</code></pre>

  <h2>What is in it</h2>
  <p>FDA describes the compilation as a listing of all new molecular entities approved since {y0} and regulated by the Center for Drug Evaluation and Research, covering both small-molecule drugs approved under an NDA and new biological products approved under a BLA. Product information, indications and regulatory characteristics reflect each application at the time of original marketing approval. The file here has {n:,} approvals from {y0} through {y1}; FDA's source file is <em>{esc(file_name)}</em>, dated {esc(fmt_date_long(vintage))}.</p>
  <p>It does not include vaccines, blood products, cell and gene therapies or other products approved by CBER, and it does not include generics, biosimilars or supplements to existing applications.</p>

  <h2>Columns</h2>
  <div class="scroll">
    <table>
      <caption>Columns of fda_nme_compilation.csv. Definitions are summarised from FDA's data dictionary.</caption>
      <thead><tr><th>Column</th><th>What it holds</th></tr></thead>
      <tbody>
{col_rows}
      </tbody>
    </table>
  </div>

  <h2>What trove changed, and what it did not</h2>
  <ul>
    <li><strong>Format.</strong> Excel to CSV and Parquet. Column names are lower-case with underscores.</li>
    <li><strong>Dates.</strong> FDA's workbook stores older dates as Excel serial numbers and newer ones as text such as 12/23/2025. Both are written as ISO dates (2025-12-23).</li>
    <li><strong>Application numbers.</strong> Zero-padded to six digits (19010 becomes 019010) so they join to Drugs@FDA and to the <a href="/drugs/">per-drug index</a>.</li>
    <li><strong>One added column.</strong> <code>days_receipt_to_approval</code>.</li>
    <li><strong>Everything else is FDA's text as written,</strong> including qualified values such as "Yes (indication [A] only)" and "Priority (used priority review voucher)". Leading and trailing spaces are trimmed. Rows are sorted by approval date.</li>
  </ul>
  <p class="callout">FDA's disclaimer applies to these files too: the dataset is for research purposes, some fields are simplified, and it reflects each application at the time of initial approval. For the current label and approval history of a product, use <a href="{DRUGS_AT_FDA_URL}" rel="noopener">Drugs@FDA</a>. FDA takes corrections to the compilation at the address on its page.</p>

  <h2>Use it</h2>
  <ul>
    <li><a href="/drugs/statistics/">FDA drug approval statistics, {y0}–{y1}</a>: approvals per year, review designations and review times, computed from this file.</li>
    <li>Per-year lists: {" · ".join(f'<a href="/drugs/{y}/">{y}</a>' for y in reversed(years[-8:]))} · <a href="/drugs/statistics/">all years</a>.</li>
    <li><a href="/docs/new-molecular-entity/">What is a new molecular entity (NME)?</a></li>
  </ul>"""

    extra = (
        f'    <p>Data: FDA, <a href="{COMPILATION_PAGE_URL}">Compilation of CDER NME and New Biologic Approvals</a>, '
        f"file dated {esc(fmt_date_long(vintage))}, SHA-256 <code>{esc(src['sha256'][:16])}…</code>. "
        f'Conversion code: <a href="{REPO_URL}/blob/main/packages/fda_sba/src/fda_sba/compilation.py">compilation.py</a>.</p>\n'
    )
    nodes = [
        {
            "@context": "https://schema.org",
            "@type": "Dataset",
            "name": f"FDA Compilation of CDER NME and New Biologic Approvals, {y0}–{y1} (CSV and Parquet)",
            "description": description,
            "url": f"{SITE}{path}",
            "isBasedOn": COMPILATION_PAGE_URL,
            "license": "https://www.usa.gov/government-works",
            "isAccessibleForFree": True,
            "keywords": [
                "FDA",
                "new molecular entity",
                "NME",
                "novel drug approvals",
                "CDER",
                "priority review",
                "orphan drug",
                "accelerated approval",
            ],
            "creator": {
                "@type": "GovernmentOrganization",
                "name": "U.S. Food and Drug Administration",
                "url": "https://www.fda.gov/",
            },
            "publisher": PUBLISHER,
            "maintainer": PERSON,
            "temporalCoverage": f"{y0}/{y1}",
            "spatialCoverage": "United States",
            "dateModified": modified,
            "distribution": [
                {
                    "@type": "DataDownload",
                    "encodingFormat": "text/csv",
                    "contentUrl": f"{SITE}/data/fda_nme_compilation.csv",
                },
                {
                    "@type": "DataDownload",
                    "encodingFormat": "application/vnd.apache.parquet",
                    "contentUrl": f"{SITE}/data/fda_nme_compilation.parquet",
                },
            ],
        },
        breadcrumbs([("trove", "/"), ("FDA drug approvals", "/drugs/"), ("Compilation", path)]),
    ]
    page = page_shell(
        title=title,
        description=description,
        path=path,
        og_title=f"FDA compilation of CDER NME and new biologic approvals, {y0}–{y1}, as CSV",
        nodes=nodes,
        crumbs_html='<a href="/">trove</a> / <a href="/drugs/">FDA drug approvals</a> / Compilation',
        body=body,
        footer=standard_footer(modified, extra),
        markdown_path=f"{path}index.md",
    )
    md = [
        f"# FDA compilation of CDER NME and new biologic approvals, {y0}–{y1}, as CSV",
        "",
        _strip_tags(lead),
        "",
        "## Download",
        "",
        f"- CSV: {SITE}/data/fda_nme_compilation.csv ({n:,} rows)",
        f"- Parquet: {SITE}/data/fda_nme_compilation.parquet",
        f"- Provenance: {SITE}/data/fda_nme_compilation_source.json",
        f"- FDA's original workbook and data dictionary: {COMPILATION_PAGE_URL}",
        "",
        "## Columns",
        "",
        "| Column | What it holds |",
        "|---|---|",
        *[f"| `{c}` | {note} |" for c, note in _COLUMN_NOTES],
        "",
        "## What trove changed",
        "",
        "Excel to CSV and Parquet; lower-case column names; ISO dates; application numbers "
        "zero-padded to six digits; one added column, `days_receipt_to_approval`. All other values "
        "are FDA's text as written.",
        "",
        f'Source: FDA file "{file_name}", dated {fmt_date_long(vintage)}. Page: {SITE}{path} '
        f"(updated {modified}).",
        "",
    ]
    return page, "\n".join(md)


# --- static list inside /drugs/ ---------------------------------------------


def render_static_list(index_rows: list[dict], comp_rows: list[dict]) -> str:
    """Crawlable HTML for /drugs/: year links plus every drug in the index."""
    years = sorted({r["approval_year"] for r in comp_rows})
    counts = {y: sum(1 for r in comp_rows if r["approval_year"] == y) for y in years}
    year_links = "\n".join(
        f'      <li><a href="/drugs/{y}/">{y}</a> <span class="when">({counts[y]})</span></li>'
        for y in reversed(years)
    )
    blocks = []
    for y in sorted({r["year"] for r in index_rows}, reverse=True):
        rows = sorted(
            (r for r in index_rows if r["year"] == y), key=lambda r: r["drug_name"].lower()
        )
        links = " · ".join(
            f'<a href="/drugs/{slugify(r["drug_name"])}/">{esc(r["drug_name"])}</a>' for r in rows
        )
        blocks.append(
            f'    <h3><a href="/drugs/{y}/">{y}</a>: {len(rows)} approvals</h3>\n'
            f'    <p class="drug-links">{links}</p>'
        )
    return f"""  <section>
    <h2>Browse FDA novel drug approvals by year</h2>
    <p>Every new molecular entity and new biologic approved by FDA's CDER since {years[0]}, one page per year, with the number of approvals in parentheses. See also <a href="/drugs/statistics/">approval statistics, {years[0]}–{years[-1]}</a> and the <a href="/drugs/compilation/">full list as CSV</a>.</p>
    <ul class="year-links">
{year_links}
    </ul>
  </section>

  <section>
    <h2>All {len(index_rows)} approvals in the per-drug index</h2>
    <p>Each links to a page with the approval date, application number, FDA label, approval letter, review documents and Drug Trials Snapshot.</p>
{chr(10).join(blocks)}
  </section>"""


# --- entry point ------------------------------------------------------------


def write_all(index: dict, today: str) -> list[tuple[str, str, str, str]]:
    """Write every list page; return their sitemap entries."""
    index_rows = index["rows"]
    comp_rows, source = load_compilation()
    vintage = source_date(source)
    years = sorted({r["approval_year"] for r in comp_rows})
    entries: list[tuple[str, str, str, str]] = []

    def emit(path: str, render, priority: str) -> None:
        out = DRUGS_DIR / path.removeprefix("/drugs/")
        modified = write_page(out / "index.html", lambda d: render(d)[0], today)
        (out / "index.md").write_text(render(modified)[1])
        entries.append((path, modified, "yearly", priority))

    for y in years:
        emit(
            f"/drugs/{y}/",
            lambda d, y=y: render_year(y, years, index_rows, comp_rows, vintage, d),
            "0.6",
        )
    emit("/drugs/statistics/", lambda d: render_statistics(comp_rows, vintage, d), "0.8")
    emit("/drugs/compilation/", lambda d: render_compilation(comp_rows, source, vintage, d), "0.8")

    DRUGS_INDEX.write_text(
        splice(
            DRUGS_INDEX.read_text(), "fda-static-list", render_static_list(index_rows, comp_rows)
        )
    )
    print(
        f"  → wrote {len(years)} per-year pages, statistics and compilation pages under {DRUGS_DIR}/"
    )
    return entries


def reserved_dirs() -> set[str]:
    """Directory names under web/drugs/ that are not per-drug pages."""
    comp_rows, _ = load_compilation()
    return RESERVED_SLUGS | {str(r["approval_year"]) for r in comp_rows}
