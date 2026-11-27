"""Generate the FDA section of the site from the published data bundles.

Per-drug pages under ``web/drugs/{slug}/`` — one permalink for each FDA novel
drug approval in the index, opening with a plain-language answer (what was
approved, when, under which application), then the facts FDA records about the
application, direct links to the label, approval letter, review documents and
Drug Trials Snapshot, and links to related approvals. Each page has a Markdown
twin at ``index.md``.

It then calls ``build_fda_lists`` for the per-year lists, the statistics page,
the compilation download page and the static list inside ``/drugs/``.

Pages for drugs no longer in the source JSON are removed, and the sitemap
entries under ``/drugs/`` are regenerated; every other sitemap entry is left
exactly as it is. A page's ``dateModified`` and sitemap ``lastmod`` change only
when its content does.

Usage: ``uv run python scripts/build_drug_pages.py``
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import build_fda_lists
import build_llms_txt
from fda_site_common import (
    DRUGS_AT_FDA_URL,
    NOVEL_APPROVALS_URL,
    PERSON,
    PUBLISHER,
    REPO_URL,
    SITE,
    breadcrumbs,
    cber_use,
    days_between,
    designations,
    esc,
    fmt_date,
    fmt_date_long,
    is_priority,
    is_yes,
    join_words,
    page_shell,
    slugify,
    title_case,
    update_sitemap,
    url_attr,
    write_page,
)

SRC = Path("web/data/fda_approvals_nme_recent.json")
OUT_DIR = Path("web/drugs")
# Keep in step with README.md "Install the skills" and web/skills/index.html.
PLUGIN_INSTALL = """/plugin marketplace add anthropics/claude-plugins-community
/plugin install trove@claude-community"""
# How many same-sponsor / same-year links to show before deferring to the index.
MAX_RELATED = 8
# A CBER indication this short is quoted in the opening sentence; a longer one
# gets its own section so the opening stays readable.
CBER_USE_IN_LEAD = 320

_VOUCHERS = {
    "TD": "tropical disease",
    "RPD": "rare pediatric disease",
    "MTMC": "material threat medical countermeasure",
}
_CENTERS = {
    "CDER": "CDER (Center for Drug Evaluation and Research)",
    "CBER": "CBER (Center for Biologics Evaluation and Research)",
}


def is_cber(r: dict) -> bool:
    return r.get("regulatory_center") == "CBER"


def application(r: dict) -> str:
    return f"{r.get('application_type') or ''} {r.get('application_number') or ''}".strip()


def summary_paragraphs(r: dict) -> list[str]:
    """The answer-first paragraphs at the top of a drug page, as plain text.

    Each stands on its own: it names the drug and does not rely on a heading
    or on the paragraph before it.
    """
    name = r["drug_name"]
    active = r.get("active_ingredient")
    named = f"{name} ({active})" if active else name
    sponsor = title_case(r.get("sponsor")).rstrip(".")
    when = fmt_date_long(r["approval_date"])
    app = application(r)
    if is_cber(r):
        first = (
            f"The FDA approved {named} on {when}. It is licensed by FDA's Center for Biologics "
            f"Evaluation and Research (CBER)"
            + (f" under {app}" if r.get("application_number") else "")
            + (f"; the manufacturer is {sponsor}." if sponsor else ".")
        )
    else:
        first = (
            f"The FDA approved {named} on {when}"
            + (f", under {app}" if app else "")
            + (f". The sponsor is {sponsor}." if sponsor else ".")
        )
    use = cber_use(r.get("indication")) if is_cber(r) else ""
    if use and len(use) <= CBER_USE_IN_LEAD:
        first += f" FDA's product page gives the indication as: \u201c{use}.\u201d"
    elif r.get("indication") and not is_cber(r):
        first += f" FDA lists the approved use as: “{r['indication'].rstrip('.')}.”"
    out = [first]

    review = r.get("review_designation")
    if review:
        flags = designations(r)
        if is_priority(review):
            second = f"At original approval, FDA recorded {join_words(flags)} for {name}."
        elif flags:
            second = (
                f"FDA reviewed {name} on the standard review clock and recorded "
                f"{join_words(flags)} at original approval."
            )
        else:
            second = (
                f"FDA reviewed {name} on the standard review clock. Its records show no orphan "
                f"drug, accelerated approval, breakthrough therapy or fast track designation at "
                f"original approval."
            )
        days = days_between(r.get("fda_receipt_date"), r["approval_date"])
        if days and days > 0:
            second += (
                f" FDA received the application on {fmt_date_long(r['fda_receipt_date'])} and "
                f"approved it {days:,} days later."
            )
        out.append(second)
    epc = r.get("pharm_class_epc")
    if epc:
        classes = [c.strip() for c in epc.split(";") if c.strip()]
        out.append(
            f"FDA's labeling data puts {name} in the established pharmacologic "
            f"{'class' if len(classes) == 1 else 'classes'}: {join_words(classes)}."
        )
    return out


def fact_rows(r: dict) -> list[tuple[str, str, str]]:
    """``(label, text, html)`` for each line of the facts table."""
    rows: list[tuple[str, str, str]] = []

    def add(label: str, text: object, markup: str | None = None) -> None:
        if text not in (None, ""):
            rows.append((label, str(text), markup if markup is not None else esc(text)))

    year = r["year"]
    add("Brand name", r["drug_name"])
    add("Active ingredient", r.get("active_ingredient"))
    add("Manufacturer" if is_cber(r) else "Sponsor", title_case(r.get("sponsor")))
    add("Application", application(r))
    add("FDA approval date", fmt_date_long(r["approval_date"]))
    add(
        "Approval year",
        year,
        f'<a href="/drugs/{year}/">{year}</a> (all {year} novel drug approvals)',
    )
    if r.get("fda_receipt_date"):
        add("FDA received application", fmt_date_long(r["fda_receipt_date"]))
        days = days_between(r["fda_receipt_date"], r["approval_date"])
        if days and days > 0:
            add("Receipt to approval", f"{days:,} days")
    add("Pharmacologic class", r.get("pharm_class_epc"))
    add("Dosage form", r.get("dosage_form"))
    add("Route of administration", r.get("route_of_administration"))
    add("Review designation", r.get("review_designation"))
    add("Orphan drug designation", r.get("orphan_drug_designation"))
    add("Accelerated approval", r.get("accelerated_approval"))
    add("Breakthrough therapy designation", r.get("breakthrough_therapy_designation"))
    add("Fast track designation", r.get("fast_track_designation"))
    if is_yes(r.get("qualified_infectious_disease_product")):
        add("Qualified infectious disease product", r["qualified_infectious_disease_product"])
    voucher = r.get("priority_review_voucher_issued")
    if voucher in _VOUCHERS:
        add("Priority review voucher issued", f"Yes ({_VOUCHERS[voucher]})")
    if is_yes(r.get("priority_review_voucher_redeemed")):
        add("Priority review voucher redeemed", "Yes")
    add("Submission classification", r.get("submission_classification"))
    add("FDA center", _CENTERS.get(r.get("regulatory_center"), r.get("regulatory_center")))
    return rows


def document_links(r: dict) -> list[tuple[str, str, str]]:
    """``(url, link text, what it is)`` for each FDA document we can link."""
    name = r["drug_name"]
    links: list[tuple[str, str, str]] = []
    if is_cber(r):
        if r.get("label_pdf_url"):
            links.append(
                (
                    r["label_pdf_url"],
                    f"{name} package insert (prescribing information), PDF",
                    "The FDA-approved labeling: indications, dosing, warnings and adverse reactions.",
                )
            )
        if r.get("drugs_at_fda_url"):
            links.append(
                (
                    r["drugs_at_fda_url"],
                    f"FDA product page for {name} (CBER)",
                    "Approval letter, Summary Basis for Regulatory Action, review memos and approval history.",
                )
            )
        return links
    if r.get("label_pdf_url"):
        links.append(
            (
                r["label_pdf_url"],
                f"{name} FDA label (prescribing information), PDF",
                "The label from FDA's approval listing: indications, dosing, warnings and adverse reactions. Later revisions are on Drugs@FDA.",
            )
        )
    if r.get("approval_letter_url"):
        links.append(
            (
                r["approval_letter_url"],
                f"{name} FDA approval letter, PDF",
                "The letter authorizing marketing: the approved indication, postmarketing requirements and commitments, and the FDA contact for the application.",
            )
        )
    if r.get("review_url"):
        links.append(
            (
                r["review_url"],
                f"{name} FDA review documents (approval package)",
                "FDA's own reviews of the application: clinical, statistical, clinical pharmacology, nonclinical and chemistry, with the summary review.",
            )
        )
    if r.get("trials_snapshot_url"):
        links.append(
            (
                r["trials_snapshot_url"],
                f"{name} Drug Trials Snapshot",
                "Who took part in the trials behind the approval, by sex, race, age and ethnicity, and whether results differed among groups.",
            )
        )
    if r.get("drugs_at_fda_url"):
        has_documents = bool(r.get("approval_letter_url") or r.get("review_url"))
        links.append(
            (
                r["drugs_at_fda_url"],
                f"Drugs@FDA record for {application(r)}",
                "Every FDA action on the application since approval: supplements, label revisions and letters."
                if has_documents
                else "FDA's page for the application: the approval letter, review documents and label history.",
            )
        )
    return links


def document_kinds(r: dict) -> str:
    """The documents a page actually links, for its title, heading and description."""
    if is_cber(r):
        return "package insert and FDA product page"
    kinds = [
        label
        for key, label in (
            ("label_pdf_url", "label"),
            ("approval_letter_url", "approval letter"),
            ("review_url", "review documents"),
            ("trials_snapshot_url", "Drug Trials Snapshot"),
        )
        if r.get(key)
    ]
    return join_words(kinds) if kinds else "Drugs@FDA record"


def source_note(r: dict, sources_read: dict) -> str:
    """One sentence saying when the FDA pages behind a record were read."""
    if is_cber(r):
        read_on = sources_read.get("cber")
        return (
            f" FDA's product page was read on {fmt_date_long(read_on)}; FDA may have posted "
            f"documents since."
            if read_on
            else ""
        )
    if r.get("approval_letter_url") or r.get("review_url"):
        read_on = sources_read.get("drugs_at_fda")
        return (
            f" Drugs@FDA was read on {fmt_date_long(read_on)}; FDA may have posted documents since."
            if read_on
            else ""
        )
    read_on = sources_read.get("cder_lists")
    return (
        " Direct links to the approval letter and review documents have not been collected "
        "for this record yet; the Drugs@FDA record has them."
        + (f" FDA's approval list was read on {fmt_date_long(read_on)}." if read_on else "")
    )


def build_jsonld(r: dict, path: str, modified: str, description: str) -> list[dict]:
    canonical = f"{SITE}{path}"
    drug_node = {
        "@context": "https://schema.org",
        "@type": "Drug",
        "name": r["drug_name"],
        "url": canonical,
        "nonProprietaryName": r.get("active_ingredient"),
        "activeIngredient": r.get("active_ingredient"),
        "manufacturer": {
            "@type": "Organization",
            "name": title_case(r.get("sponsor")),
        }
        if r.get("sponsor")
        else None,
        "description": r.get("indication"),
        "dosageForm": r.get("dosage_form"),
        "administrationRoute": r.get("route_of_administration"),
        "prescribingInfo": r.get("label_pdf_url"),
        "isProprietary": True,
    }
    drug_node = {k: v for k, v in drug_node.items() if v is not None}
    page_node = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": f"{r['drug_name']} FDA approval",
        "description": description,
        "url": canonical,
        "isPartOf": {"@type": "WebSite", "name": "trove", "url": f"{SITE}/"},
        "author": PERSON,
        "publisher": PUBLISHER,
        "dateModified": modified,
        "isBasedOn": [u for u in (r.get("drugs_at_fda_url"), NOVEL_APPROVALS_URL) if u],
    }
    crumbs = breadcrumbs(
        [
            ("trove", "/"),
            ("FDA drug approvals", "/drugs/"),
            (str(r["year"]), f"/drugs/{r['year']}/"),
            (r["drug_name"], path),
        ]
    )
    return [drug_node, page_node, crumbs]


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

    year = r["year"]
    blocks.append(
        f'  <p><a href="/drugs/{year}/">All FDA novel drug approvals in {year} →</a> · '
        f'<a href="/drugs/">Search the index →</a></p>'
    )
    return "\n".join(blocks)


def render_drug(
    r: dict, ordered: list[dict], coverage: str, sources_read: dict, modified: str
) -> tuple[str, str]:
    """Return ``(html, markdown)`` for one drug page."""
    name = r["drug_name"]
    slug = slugify(name)
    path = f"/drugs/{slug}/"
    active = r.get("active_ingredient") or ""
    named = f"{name} ({active})" if active else name
    sponsor = title_case(r.get("sponsor"))
    paragraphs = summary_paragraphs(r)
    facts = fact_rows(r)
    links = document_links(r)

    kinds = document_kinds(r)
    title = (
        f"{named} FDA approval: date, label, review documents | trove"
        if r.get("review_url") or is_cber(r)
        else f"{named} FDA approval: date, application, label | trove"
    )
    description = (
        f"{named} was approved by the FDA on {fmt_date_long(r['approval_date'])}"
        + (
            f" ({application(r)}" + (f", {sponsor}" if sponsor else "") + ")"
            if application(r)
            else ""
        )
        + f". Approval facts and direct links to the FDA {kinds}."
    )
    read_line = source_note(r, sources_read)
    fact_html = "\n".join(
        f"    <div><dt>{esc(label)}</dt><dd>{markup}</dd></div>" for label, _, markup in facts
    )
    if links:
        link_html = "\n".join(
            f'    <li><a href="{url_attr(url)}" rel="noopener">{esc(text)} ↗</a>'
            f'<span class="what">{esc(what)}</span></li>'
            for url, text, what in links
        )
    else:
        link_html = (
            '    <li><span class="muted">No FDA links available for this record.</span></li>'
        )
    has_designations = bool(r.get("review_designation"))
    designation_note = (
        '  <p class="note">Review designation and the expedited-program rows are from FDA\'s '
        '<a href="/drugs/compilation/">compilation of CDER NME and new biologic approvals</a> and '
        "describe the application at the time of original approval.</p>\n"
        if has_designations
        else ""
    )
    use = cber_use(r.get("indication")) if is_cber(r) else ""
    if len(use) <= CBER_USE_IN_LEAD:
        use = ""  # already quoted in the opening sentence
    use_html = (
        f"\n  <h2>What {esc(name)} is approved for</h2>\n"
        f"  <p>FDA's product page for {esc(name)} gives the indication as: {esc(use)}</p>\n"
        '  <p class="note">Copied from FDA\'s CBER product page as it read when trove fetched it; '
        "it can be abbreviated, and can include indications added after the original approval. "
        "The package insert linked below has the full text.</p>\n"
        if use
        else ""
    )
    doc_kinds = kinds
    body = f"""  <header>
    <h1>{esc(named)} FDA approval</h1>
    <p class="subtitle">{esc(" · ".join(x for x in (sponsor, application(r), f"approved {fmt_date(r['approval_date'])}") if x))}</p>
  </header>

  <p class="lead">{esc(paragraphs[0])}</p>
{"".join(f"  <p>{esc(p)}</p>{chr(10)}" for p in paragraphs[1:])}
  <h2>{esc(name)} approval facts</h2>
  <dl class="facts">
{fact_html}
  </dl>
{designation_note}{use_html}
  <h2>{esc(name)} FDA {doc_kinds}</h2>
  <p>FDA's documents for {esc(name)} are public. These links go straight to them on FDA's site.</p>
  <ul class="links">
{link_html}
  </ul>
  <p class="note">New to these? See <a href="/docs/fda-approval-package/">what is in an FDA approval package</a>, <a href="/docs/drug-trials-snapshot/">what a Drug Trials Snapshot is</a> and <a href="/docs/new-molecular-entity/">what a new molecular entity is</a>.{esc(read_line)}</p>

  <h2>Related approvals</h2>
{build_related(r, ordered)}

  <h2>Ask Claude about {esc(name)}</h2>
  <p>The <a href="/skills/fda-analyst/"><code>fda-analyst</code> skill</a> answers natural-language questions about this approval by fetching the relevant FDA review PDFs at query time. It ships in the trove Claude Code plugin. Add Anthropic's public community marketplace, then install the plugin:</p>
<pre><code>{esc(PLUGIN_INSTALL)}</code></pre>
  <p>Other install options are on the <a href="/skills/">skills page</a>; the source is at <a href="{REPO_URL}">github.com/cbetz/trove</a>.</p>
  <p>Example prompts for {esc(name)}:</p>
  <ul>
    <li><em>"What was the basis for {esc(name)}'s approval — what trials, what endpoints?"</em></li>
    <li><em>"What adverse events did the FDA flag in the {esc(name)} medical review?"</em></li>
    <li><em>"What postmarketing requirements are in the {esc(name)} approval letter?"</em></li>
  </ul>"""

    footer = f"""    <p><a href="/drugs/">← All FDA novel drug approvals</a> · <a href="/drugs/{r["year"]}/">{r["year"]} approvals</a> · <a href="/drugs/statistics/">Approval statistics</a> · <a href="/">trove home</a> · <a href="/skills/">Claude skills</a> · <a href="{REPO_URL}">Source on GitHub</a></p>
    <p>One record from the <a href="/drugs/">FDA novel drug approvals index</a> ({esc(coverage)}) at <a href="/">trove</a>. Page updated {esc(fmt_date_long(modified))}. Built by <a href="https://github.com/cbetz">Chris Betz</a>. Not medical advice; the FDA approval package is the source of truth.</p>
    <p>Source: U.S. Food and Drug Administration, <a href="{NOVEL_APPROVALS_URL}">Novel Drug Approvals</a>; <a href="{DRUGS_AT_FDA_URL}">Drugs@FDA database</a>. US government work, public domain.</p>
    <p>More from Chris: <a href="https://cbetz.com">cbetz.com</a> · <a href="https://x.com/thechrisbetz">@thechrisbetz</a> on X · <a href="https://github.com/cbetz">github.com/cbetz</a>.</p>"""

    page = page_shell(
        title=title,
        description=description,
        path=path,
        og_title=f"{name} — FDA approval, {kinds}",
        nodes=build_jsonld(r, path, modified, description),
        crumbs_html=(
            f'<a href="/">trove</a> / <a href="/drugs/">FDA drug approvals</a> / '
            f'<a href="/drugs/{r["year"]}/">{r["year"]}</a> / {esc(name)}'
        ),
        body=body,
        footer=footer,
        markdown_path=f"{path}index.md",
    )

    md = [f"# {named} FDA approval", "", *[p + "\n" for p in paragraphs]]
    md += [f"## {name} approval facts", ""]
    md += [f"- {label}: {text}" for label, text, _ in facts]
    if use:
        md += ["", f"## What {name} is approved for", ""]
        md += [f"FDA's product page gives the indication as: {use}"]
    md += ["", f"## {name} FDA documents", ""]
    md += [f"- [{text}]({url.replace(' ', '%20')}): {what}" for url, text, what in links]
    md += [
        "",
        f"Source: U.S. Food and Drug Administration (Novel Drug Approvals; Drugs@FDA; Compilation "
        f"of CDER NME and New Biologic Approvals).{read_line} Page: {SITE}{path} (updated "
        f"{modified}). All {r['year']} approvals: {SITE}/drugs/{r['year']}/. Not medical advice.",
        "",
    ]
    return page, "\n".join(md)


def prune_stale_pages(keep: set[str]) -> list[str]:
    """Delete generated pages for drugs that are no longer in the index.

    ``keep`` is every directory name that should exist: drug slugs plus the
    list pages. Only touches a directory that holds nothing but generated
    ``index.html`` / ``index.md`` files.
    """
    removed = []
    for d in sorted(OUT_DIR.iterdir()):
        if not d.is_dir() or d.name in keep:
            continue
        if not {f.name for f in d.iterdir()} <= {"index.html", "index.md"}:
            continue
        for f in d.iterdir():
            f.unlink()
        d.rmdir()
        removed.append(d.name)
    return removed


def main() -> None:
    data = json.loads(SRC.read_text())
    rows = data["rows"]
    totals = data["totals"]
    coverage = f"{totals['year_min']}–{totals['year_max']}"
    sources_read = totals.get("sources_read", {})
    today = datetime.now(UTC).strftime("%Y-%m-%d")
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
    reserved = build_fda_lists.reserved_dirs()
    clash = sorted(set(slugs) & reserved)
    if clash:
        raise SystemExit(f"Drug slugs collide with list pages: {', '.join(clash)}")
    ordered = sorted(rows, key=lambda r: (r["approval_date"], r["drug_name"]))

    entries: list[tuple[str, str, str, str]] = []
    for r in rows:
        slug = slugify(r["drug_name"])
        out = OUT_DIR / slug

        def render(d: str, r: dict = r) -> tuple[str, str]:
            return render_drug(r, ordered, coverage, sources_read, d)

        modified = write_page(out / "index.html", lambda d, render=render: render(d)[0], today)
        (out / "index.md").write_text(render(modified)[1])
        entries.append((f"/drugs/{slug}/", modified, "yearly", "0.7"))
    print(f"  → wrote {len(slugs)} per-drug pages under {OUT_DIR}/")

    entries += build_fda_lists.write_all(data, today)

    removed = prune_stale_pages(set(slugs) | reserved)
    if removed:
        print(f"  → removed {len(removed)} stale page(s): {', '.join(removed)}")

    n = update_sitemap(entries)
    print(f"  → updated {n} URLs under /drugs/ in web/sitemap.xml (other entries untouched)")
    build_llms_txt.write()


if __name__ == "__main__":
    main()
