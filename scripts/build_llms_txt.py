"""Write ``web/llms.txt`` from the published data bundles.

``llms.txt`` is a plain-Markdown overview of the site for language-model
clients: what the site is, its main pages and its data files. Every count in
it is read from the bundles under ``web/data/``, so it cannot drift from the
data after a rebuild. ``build_drug_pages.py`` calls this; it can also be run
alone.

Usage: ``uv run python scripts/build_llms_txt.py``
"""

from __future__ import annotations

import json
from pathlib import Path

SITE = "https://troveproject.com"
DATA = Path("web/data")
OUT = Path("web/llms.txt")


def render() -> str:
    fda = json.loads((DATA / "fda_approvals_nme_recent.json").read_text())
    comp = json.loads((DATA / "fda_nme_compilation_source.json").read_text())["totals"]
    hospitals = json.loads((DATA / "community_benefit_gap_2022.json").read_text())
    ranked = json.loads((DATA / "charity_care_gap_index_2022.json").read_text())

    n = fda["totals"]["drugs"]
    i0, i1 = fda["totals"]["year_min"], fda["totals"]["year_max"]
    y0, y1, total = comp["year_min"], comp["year_max"], comp["approvals"]
    tax_year = hospitals["tax_year"]
    matched = hospitals["totals"]["matched"]
    clean = ranked["counts"]["clean_aligned"]
    states = ranked["counts"]["clean_states"]
    years = " ".join(f"[{y}]({SITE}/drugs/{y}/index.md)" for y in range(y1, y1 - 8, -1))
    examples = ", ".join(
        f"[{r['drug_name']}]({SITE}/drugs/{slug}/index.md)"
        for r, slug in (
            (r, "".join(c if c.isalnum() else "-" for c in r["drug_name"].lower()).strip("-"))
            for r in fda["rows"][:3]
        )
    )
    return f"""# trove

> Public-domain U.S. healthcare data, parsed and documented: FDA novel drug approvals ({y0}–{y1}) with labels, approval letters and review documents, and nonprofit hospital charity care as reported to the IRS (Form 990 Schedule H) and to CMS (Medicare cost report Worksheet S-10). Open source, MIT-licensed, built by Chris Betz. Not medical, legal or financial advice.

Every figure on the site comes from a named federal source and links back to it. Data files are under {SITE}/data/ and can be read directly over HTTPS (CSV, JSON, Parquet). Pages listed below as .md are Markdown versions of the HTML pages.

## FDA drug approvals

- [FDA drug approvals: list and lookup]({SITE}/drugs/): {total:,} CDER novel approvals by year, {y0}–{y1}, and a page for each of {n} novel approvals from {i0}–{i1}
- [FDA drug approval statistics, {y0}–{y1}]({SITE}/drugs/statistics/index.md): approvals per year, NDA and BLA counts, priority review, orphan, accelerated approval, breakthrough and fast track counts, receipt-to-approval times
- [FDA NME compilation as CSV and Parquet]({SITE}/drugs/compilation/index.md): FDA's Compilation of CDER NME and New Biologic Approvals, converted from Excel, with column definitions
- Per-year lists: {years} (pattern: {SITE}/drugs/YYYY/index.md, {y0} onward)
- Per-drug pages: {SITE}/drugs/<brand-name>/index.md, for example {examples}. Each gives the approval date, application number, sponsor, review designation, pharmacologic class where FDA records one, and links to the FDA label, approval letter, review documents and Drug Trials Snapshot

## Hospital charity care (IRS and CMS)

- [Hospital charity care: the IRS figure and the CMS figure, side by side]({SITE}/hospitals/): lookup of {matched:,} matched nonprofit hospital systems, tax year {tax_year}, and a ranked index of {clean} single-facility hospitals in {states} states
- [Note: what is in the difference between the two figures]({SITE}/notes/charity-care-gap/): method, a worked reconciliation for one hospital, and the largest differences

## Explainers

- [What is an FDA novel drug approval?]({SITE}/docs/fda-nme/)
- [What is a new molecular entity (NME)? NME vs NCE]({SITE}/docs/new-molecular-entity/)
- [What is an FDA approval package? Approval letter, reviews, Summary Basis of Approval]({SITE}/docs/fda-approval-package/)
- [What is an FDA Drug Trials Snapshot?]({SITE}/docs/drug-trials-snapshot/)
- [What is HCRIS? CMS Medicare Cost Reports]({SITE}/docs/hcris/)
- [What is IRS Form 990 Schedule H? Parts, line 7a and the instructions]({SITE}/docs/schedule-h/)

## Data files

- [fda_approvals_nme_recent.json]({SITE}/data/fda_approvals_nme_recent.json): {n} FDA novel approvals, {i0}–{i1}, one object per drug, with document URLs, review designations and pharmacologic class (also .parquet)
- [fda_nme_compilation.csv]({SITE}/data/fda_nme_compilation.csv): {total:,} CDER novel approvals, {y0}–{y1} (also .parquet)
- [community_benefit_gap_{tax_year}.csv]({SITE}/data/community_benefit_gap_{tax_year}.csv): IRS Schedule H line 7a and CMS S-10 line 23 for {matched:,} matched hospital systems, tax year {tax_year} (also .json, .parquet)
- [charity_care_gap_index_{tax_year}.json]({SITE}/data/charity_care_gap_index_{tax_year}.json): the ranked index of {clean} single-facility hospitals

## Optional

- [Claude Code skills]({SITE}/skills/): fda-analyst and hcris-analyst answer questions over these datasets
- [Source code](https://github.com/cbetz/trove): parsers, build scripts and tests
- [Sitemap]({SITE}/sitemap.xml)
"""


def write() -> None:
    OUT.write_text(render())
    print(f"  → wrote {OUT}")


if __name__ == "__main__":
    write()
