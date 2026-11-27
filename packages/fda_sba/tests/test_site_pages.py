"""Tests for the scripts that write the FDA section of the site, and for the
pages they publish.

The scripts live in ``scripts/`` (not a package) and import one another, so
that directory is put on ``sys.path`` for the import.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "web"
sys.path.insert(0, str(ROOT / "scripts"))

import build_drug_pages  # noqa: E402
import build_fda_lists  # noqa: E402
import fda_site_common  # noqa: E402


def _row(**over) -> dict:
    row = {
        "year": 2023,
        "drug_name": "Testavir",
        "active_ingredient": "testavirum",
        "sponsor": "ACME PHARMS INC",
        "approval_date": "2023-12-18",
        "indication": "To treat test conditions",
        "application_number": "215064",
        "application_type": "NDA",
        "regulatory_center": "CDER",
        "label_pdf_url": "https://x/lbl.pdf",
        "drugs_at_fda_url": "https://x/overview",
        "approval_letter_url": "https://x/a, b ltr.pdf",
        "review_url": "https://x/TOC.html",
        "trials_snapshot_url": "https://x/snapshot",
        "fda_receipt_date": "2023-04-18",
        "review_designation": "Priority",
        "orphan_drug_designation": "Yes (indication [A] only)",
        "accelerated_approval": "No",
        "breakthrough_therapy_designation": "No",
        "fast_track_designation": "Yes",
        "qualified_infectious_disease_product": "No",
        "priority_review_voucher_issued": "RPD",
        "priority_review_voucher_redeemed": "No",
    }
    row.update(over)
    return row


def test_designations_keep_fdas_qualifier_and_skip_no_and_na() -> None:
    assert fda_site_common.designations(_row()) == [
        "priority review",
        "orphan drug designation (indication [A] only)",
        "fast track designation",
    ]
    assert fda_site_common.designations(_row(review_designation="Standard")) == [
        "orphan drug designation (indication [A] only)",
        "fast track designation",
    ]
    # A CBER row has no compilation data at all.
    blank = {k: None for k in _row() if k.endswith(("designation", "approval", "product"))}
    assert fda_site_common.designations(blank) == []


def test_summary_states_the_approval_and_only_what_fda_recorded() -> None:
    first, second = build_drug_pages.summary_paragraphs(_row())
    assert first.startswith(
        "The FDA approved Testavir (testavirum) on December 18, 2023, under NDA 215064."
    )
    assert "The sponsor is Acme Pharms Inc. FDA lists" in first
    assert "“To treat test conditions.”" in first
    assert "priority review" in second and "accelerated approval" not in second
    assert "approved it 244 days later" in second

    plain = _row(
        review_designation="Standard", orphan_drug_designation="No", fast_track_designation="No"
    )
    assert "standard review clock" in build_drug_pages.summary_paragraphs(plain)[1]


def test_cber_summary_leaves_a_long_indication_to_its_own_section() -> None:
    cber = _row(
        regulatory_center="CBER",
        application_type="BLA",
        indication="Treatment of something. " * 20,
        review_designation=None,
        fda_receipt_date=None,
    )
    paragraphs = build_drug_pages.summary_paragraphs(cber)
    assert len(paragraphs) == 1
    assert "CBER" in paragraphs[0] and "Treatment of something" not in paragraphs[0]
    legacy = "s: Treatment of something Production Information Package Insert"
    assert fda_site_common.cber_use(legacy) == "Treatment of something"


def test_document_links_depend_on_the_center() -> None:
    cder = [text for _, text, _ in build_drug_pages.document_links(_row())]
    assert cder == [
        "Testavir FDA label (prescribing information), PDF",
        "Testavir FDA approval letter, PDF",
        "Testavir FDA review documents (approval package)",
        "Testavir Drug Trials Snapshot",
        "Drugs@FDA record for NDA 215064",
    ]
    cber = build_drug_pages.document_links(_row(regulatory_center="CBER"))
    assert [text for _, text, _ in cber] == [
        "Testavir package insert (prescribing information), PDF",
        "FDA product page for Testavir (CBER)",
    ]
    # A space in an FDA URL must not break the href.
    assert fda_site_common.url_attr("https://x/a, b ltr.pdf") == "https://x/a,%20b%20ltr.pdf"


def test_a_page_names_only_the_documents_it_links() -> None:
    assert build_drug_pages.document_kinds(_row()) == (
        "label, approval letter, review documents and Drug Trials Snapshot"
    )
    bare = _row(approval_letter_url=None, review_url=None, trials_snapshot_url=None)
    assert build_drug_pages.document_kinds(bare) == "label"
    assert build_drug_pages.document_kinds(_row(regulatory_center="CBER")).startswith("package")
    read = {"cder_lists": "2026-11-26", "drugs_at_fda": "2026-05-05", "cber": "2026-11-26"}
    assert "Drugs@FDA was read on May 5, 2026" in build_drug_pages.source_note(_row(), read)
    note = build_drug_pages.source_note(bare, read)
    assert "have not been collected" in note and "November 26, 2026" in note


def test_pharmacologic_class_and_short_cber_indication_reach_the_summary() -> None:
    row = _row(pharm_class_epc="Kinase Inhibitor; Other Class")
    assert build_drug_pages.summary_paragraphs(row)[-1] == (
        "FDA's labeling data puts Testavir in the established pharmacologic classes: "
        "Kinase Inhibitor and Other Class."
    )
    cber = _row(
        regulatory_center="CBER",
        application_type="BLA",
        indication="the treatment of adults with a condition",
        review_designation=None,
        sponsor="Acme, Inc.",
    )
    first = build_drug_pages.summary_paragraphs(cber)[0]
    assert "the manufacturer is Acme, Inc." in first and "Inc.." not in first
    assert "\u201cThe treatment of adults with a condition.\u201d" in first


def test_llms_txt_is_generated_from_the_bundles(index) -> None:
    import build_llms_txt

    text = build_llms_txt.render()
    assert text == (WEB / "llms.txt").read_text()
    assert f"each of {index['totals']['drugs']} novel approvals" in text


def test_write_page_changes_the_date_only_when_the_content_changes(tmp_path: Path) -> None:
    path = tmp_path / "p" / "index.html"

    def render(body: str):
        return lambda d: f'<p>{body}</p>\n"dateModified": "{d}"\n'

    assert fda_site_common.write_page(path, render("one"), "2026-01-01") == "2026-01-01"
    assert fda_site_common.write_page(path, render("one"), "2026-06-01") == "2026-01-01"
    assert '"2026-01-01"' in path.read_text()
    assert fda_site_common.write_page(path, render("two"), "2026-06-01") == "2026-06-01"
    assert "two" in path.read_text()


def _comp(**over) -> dict:
    row = {
        "approval_year": 1990,
        "application_type": "NDA",
        "review_designation": "Standard",
        "orphan_drug_designation": "No",
        "accelerated_approval": "N/A",
        "breakthrough_therapy_designation": "N/A",
        "fast_track_designation": "N/A",
        "days_receipt_to_approval": 400,
    }
    row.update(over)
    return row


def test_summarize_shows_a_program_that_did_not_exist_as_missing_not_zero() -> None:
    rows = [
        _comp(),
        _comp(application_type="BLA", review_designation="Priority (indication [A] only)"),
        _comp(orphan_drug_designation="Yes", days_receipt_to_approval=200),
        _comp(days_receipt_to_approval=None),
    ]
    s = build_fda_lists.summarize(rows)
    assert (s["n"], s["nda"], s["bla"], s["priority"], s["orphan"]) == (4, 3, 1, 1, 1)
    assert s["accelerated"] is None and s["breakthrough"] is None
    assert s["median_days"] == 400
    # One approval after the program began makes the count a real zero or more.
    assert build_fda_lists.summarize([*rows, _comp(accelerated_approval="No")])["accelerated"] == 0


def test_short_use_cuts_at_a_sentence_or_word() -> None:
    assert build_fda_lists.short_use("One line.\nLimitations of Use: more") == "One line."
    long = "First sentence about the indication. " + "word " * 80
    assert build_fda_lists.short_use(long, limit=60) == "First sentence about the indication."
    assert build_fda_lists.short_use("word " * 80, limit=22).endswith("…")
    assert build_fda_lists.short_use(None) == ""


# --- the published pages ----------------------------------------------------


@pytest.fixture(scope="module")
def index() -> dict:
    return json.loads((WEB / "data" / "fda_approvals_nme_recent.json").read_text())


def test_every_drug_has_a_page_and_a_markdown_twin(index) -> None:
    for r in index["rows"]:
        d = WEB / "drugs" / fda_site_common.slugify(r["drug_name"])
        page = (d / "index.html").read_text()
        assert (d / "index.md").exists(), d
        assert f"/drugs/{r['year']}/" in page
        assert fda_site_common.fmt_date_long(r["approval_date"]) in page


def test_year_pages_match_fdas_counts(index) -> None:
    source = json.loads((WEB / "data" / "fda_nme_compilation_source.json").read_text())
    for year, n in source["totals"]["by_year"].items():
        page = (WEB / "drugs" / year / "index.html").read_text()
        assert f"approved <strong>{n} novel drugs in {year}</strong>" in page
        body = page.split("<tbody>")[1].split("</tbody>")[0]
        assert body.count("<tr>") == n
    # The per-drug index and FDA's compilation agree on every year both cover.
    for year, n in index["totals"]["by_year"].items():
        cder = sum(
            1 for r in index["rows"] if r["year"] == int(year) and r["regulatory_center"] == "CDER"
        )
        assert cder == source["totals"]["by_year"][year]
        assert n >= cder


def test_sitemap_lists_every_generated_page_and_nothing_missing(index) -> None:
    sitemap = (WEB / "sitemap.xml").read_text()
    locs = re.findall(r"<loc>https://troveproject\.com(/[^<]*)</loc>", sitemap)
    assert len(locs) == len(set(locs))
    for loc in locs:
        assert (WEB / loc.strip("/") / "index.html").exists(), loc
    for r in index["rows"]:
        assert f"/drugs/{fda_site_common.slugify(r['drug_name'])}/" in locs
    for path in ("/drugs/statistics/", "/drugs/compilation/", "/drugs/1985/", "/drugs/2025/"):
        assert path in locs


def test_internal_links_resolve() -> None:
    broken = set()
    for page in WEB.rglob("*.html"):
        for href in set(re.findall(r'href="(/[^"#?]*)', page.read_text())):
            if href.startswith("/_vercel"):
                continue
            target = WEB / href.lstrip("/")
            if not (target.is_file() or (target / "index.html").is_file()):
                broken.add(href)
    assert not broken


def test_drugs_index_has_a_static_list_for_crawlers(index) -> None:
    page = (WEB / "drugs" / "index.html").read_text()
    static = page.split("<!-- fda-static-list:start -->")[1].split("<!-- fda-static-list:end -->")[
        0
    ]
    assert static.count('href="/drugs/') >= len(index["rows"]) + 41
