"""Tests for the 1.2.0 additions: CBER indication markup, openFDA pharmacologic
class, compilation fallbacks, and the paced, stop-on-refusal drugs@FDA fetcher."""

from __future__ import annotations

import io
from urllib.error import HTTPError

import pandas as pd
import pytest
from fda_sba import overview, parse_pharm_class
from fda_sba.cber import parse_cber_product
from fda_sba.compilation import enrich_with_designations, fill_missing_application_numbers

# --- CBER indication: three page layouts -------------------------------------


def _indication(body: str) -> str | None:
    return parse_cber_product(f"<html><body>{body}</body></html>")["indication"]


def test_bold_label_followed_by_a_list() -> None:
    body = """<p><strong>Manufacturer: </strong>Acme<br><strong>Indications:&nbsp;</strong></p>
    <ul><li>Treatment of adults with condition A.</li><li>Treatment of children with B.</li></ul>
    <h2>Product Information</h2><ul><li>Package Insert - X</li></ul>"""
    assert _indication(body) == (
        "Treatment of adults with condition A; Treatment of children with B"
    )


def test_bold_label_line_break_lead_in_and_connective_items() -> None:
    body = """<p><strong>Indication:</strong><br> For adults with hemophilia B who:</p>
    <ul><li>Currently use prophylaxis, or</li><li>Have had hemorrhage, and,</li>
    <li>Have no antibodies.</li></ul><h2>Product Information</h2>"""
    assert _indication(body) == (
        "For adults with hemophilia B who: Currently use prophylaxis, or "
        "Have had hemorrhage, and, Have no antibodies"
    )


def test_label_paragraph_then_statement_paragraph_stops_before_limitations() -> None:
    body = """<p><strong>Indication:</strong><br>X is indicated for patients with <em>DMD </em>gene
    mutations.</p><p>Limitations of Use:<br>Not recommended in:</p><ul><li>Liver impairment.</li></ul>"""
    assert _indication(body) == "X is indicated for patients with DMD gene mutations"


def test_accordion_layout_with_nested_list_and_limitations() -> None:
    body = """<div class="panel panel-default"><div class="panel-heading"><h2 class="panel-title">
    <a role="button">Indication</a></h2></div><div class="panel-collapse"><div class="panel-body">
    <ul><li>STN 1 - For patients aged 2 and older with:<ul><li>Disease A.</li><li>Disease B.</li></ul></li>
    <li>STN 2 - For patients aged 12 and older.</li></ul><p>Limitations of Use: none.</p></div></div></div>
    <div class="panel-heading"><h2><a>Product Information</a></h2></div><div><ul><li>Insert</li></ul></div>"""
    assert _indication(body) == (
        "STN 1 - For patients aged 2 and older with: Disease A. Disease B; "
        "STN 2 - For patients aged 12 and older"
    )


def test_accordion_paragraph_statement_ignores_the_limitations_list() -> None:
    body = """<div class="panel-heading"><h2><a>Indication</a></h2></div><div><div class="panel-body">
    <p>X is indicated for ambulatory patients.</p><p>Limitations of Use:<br>Not for:</p>
    <ul><li>Liver impairment.</li></ul></div></div>"""
    assert _indication(body) == "X is indicated for ambulatory patients"


# --- openFDA pharmacologic class ---------------------------------------------


def test_pharm_class_is_deduplicated_across_labels_and_loses_its_tag() -> None:
    payload = {
        "results": [
            {"openfda": {"pharm_class_epc": ["Kinase Inhibitor [EPC]"], "pharm_class_moa": None}},
            {
                "openfda": {
                    "pharm_class_epc": ["Kinase Inhibitor [EPC]", "Other Class [EPC]"],
                    "pharm_class_moa": ["Protein Kinase Inhibitors [MoA]"],
                }
            },
        ]
    }
    assert parse_pharm_class(payload) == {
        "pharm_class_epc": "Kinase Inhibitor; Other Class",
        "pharm_class_moa": "Protein Kinase Inhibitors",
    }
    assert parse_pharm_class({"results": []}) == {"pharm_class_epc": None, "pharm_class_moa": None}


# --- compilation fallbacks ----------------------------------------------------


def _compilation() -> pd.DataFrame:
    base = {
        "application_number_2": None,
        "application_number_3": None,
        "dosage_form": "Tablet",
        "route_of_administration": "Oral",
        "fda_receipt_date": "2024-12-30",
        "review_designation": "Standard",
        "orphan_drug_designation": "No",
        "accelerated_approval": "No",
        "breakthrough_therapy_designation": "No",
        "fast_track_designation": "No",
        "qualified_infectious_disease_product": "No",
        "priority_review_voucher_issued": "No",
        "priority_review_voucher_redeemed": "No",
    }
    return pd.DataFrame(
        [
            {
                **base,
                "proprietary_name": "Nereus",
                "approval_year": 2025,
                "application_type": "NDA",
                "application_number": "220152",
                "applicant": "Vanda Pharmaceuticals, Inc.",
                "fda_approval_date": "2025-12-30",
            }
        ]
    )


def test_a_list_row_without_an_application_number_takes_the_compilations() -> None:
    index = pd.DataFrame(
        {
            "drug_name": ["NEREUS", "Nereus", "Other"],
            "year": [2025, 2024, 2025],
            "application_number": [None, None, "111111"],
            "application_type": [None, None, "NDA"],
            "drugs_at_fda_url": [None, None, "u"],
        }
    )
    out = fill_missing_application_numbers(index, _compilation()).to_dict("records")
    assert out[0]["application_number"] == "220152" and out[0]["application_type"] == "NDA"
    assert out[0]["drugs_at_fda_url"].endswith("ApplNo=220152")
    assert pd.isna(out[1]["application_number"])  # same name, different year: no match
    assert out[2]["application_number"] == "111111"  # an existing number is kept


def test_sponsor_falls_back_to_the_compilations_applicant() -> None:
    index = pd.DataFrame(
        {
            "drug_name": ["Nereus", "Nereus"],
            "application_number": ["220152", "220152"],
            "approval_date": [pd.Timestamp("2025-12-30").date()] * 2,
            "sponsor": [None, "Vanda Pharms INC"],
        }
    )
    out = enrich_with_designations(index, _compilation())
    assert list(out["sponsor"]) == ["Vanda Pharmaceuticals, Inc.", "Vanda Pharms INC"]


def test_a_date_that_disagrees_with_the_compilation_is_reported() -> None:
    index = pd.DataFrame(
        {
            "drug_name": ["Nereus"],
            "application_number": ["220152"],
            "approval_date": [pd.Timestamp("2025-12-29").date()],
            "sponsor": ["x"],
        }
    )
    with pytest.warns(UserWarning, match="differs from FDA's compilation"):
        enrich_with_designations(index, _compilation())


# --- the drugs@FDA fetcher stops when refused ---------------------------------


@pytest.fixture
def fetcher(monkeypatch, tmp_path):
    monkeypatch.delenv("TROVE_FDA_OFFLINE", raising=False)
    monkeypatch.setenv("TROVE_FDA_FETCH_PAGES", "1")
    monkeypatch.setattr(overview, "REQUEST_DELAY", 0)
    monkeypatch.setattr(overview, "_blocked_reason", None)
    monkeypatch.setattr(overview, "_failed", {})
    monkeypatch.setattr(overview, "_consecutive_404", 0)
    calls: list[str] = []

    def answer(code: int):
        def urlopen(req, timeout=30):
            calls.append(req.full_url)
            raise HTTPError(req.full_url, code, "x", {}, io.BytesIO(b""))

        monkeypatch.setattr(overview, "urlopen", urlopen)

    return answer, calls, tmp_path


def test_a_403_stops_every_later_request(fetcher) -> None:
    answer, calls, cache = fetcher
    answer(403)
    with pytest.raises(overview.FdaBlockedError):
        overview.fetch_application_overview("111111", cache)
    with pytest.raises(overview.FdaBlockedError):
        overview.fetch_application_overview("222222", cache)
    assert len(calls) == 1
    assert not list(cache.iterdir())  # a refusal is never cached as a page


def test_repeated_404s_are_treated_as_a_refusal_and_not_retried(fetcher) -> None:
    answer, calls, cache = fetcher
    answer(404)
    for number in ("111111", "222222"):
        with pytest.raises(HTTPError):
            overview.fetch_application_overview(number, cache)
    with pytest.raises(RuntimeError):  # already failed this run: no second request
        overview.fetch_application_overview("111111", cache)
    with pytest.raises(overview.FdaBlockedError):
        overview.fetch_application_overview("333333", cache)
    with pytest.raises(overview.FdaBlockedError):
        overview.fetch_application_overview("444444", cache)
    assert len(calls) == 3


def test_offline_switch_uses_the_cache_and_sends_nothing(fetcher, monkeypatch) -> None:
    answer, calls, cache = fetcher
    answer(403)
    monkeypatch.setenv("TROVE_FDA_OFFLINE", "1")
    (cache / "111111.html").write_text("cached")
    assert overview.fetch_application_overview("111111", cache).read_text() == "cached"
    with pytest.raises(overview.PageNotCachedError):
        overview.fetch_application_overview("222222", cache)
    assert calls == []


def test_pages_are_not_requested_unless_switched_on(fetcher, monkeypatch) -> None:
    answer, calls, cache = fetcher
    answer(403)
    monkeypatch.delenv("TROVE_FDA_FETCH_PAGES")
    (cache / "111111.html").write_text("cached")
    assert overview.fetch_application_overview("111111", cache).read_text() == "cached"
    with pytest.raises(overview.PageNotCachedError, match="TROVE_FDA_FETCH_PAGES"):
        overview.fetch_application_overview("222222", cache)
    assert calls == []


# --- openFDA Drugs@FDA record -------------------------------------------------


def test_original_approval_comes_from_the_first_approved_orig_submission() -> None:
    from fda_sba import parse_original_approval

    record = {
        "submissions": [
            {
                "submission_type": "ORIG",
                "submission_number": "2",
                "submission_status": "AP",
                "submission_status_date": "20250301",
                "application_docs": [{"type": "Letter", "url": "https://x/second.pdf"}],
            },
            {
                "submission_type": "ORIG",
                "submission_number": "1",
                "submission_status": "AP",
                "submission_status_date": "20250130",
                "submission_class_code_description": "Type 1 - New Molecular Entity",
                "review_priority": "PRIORITY",
                "submission_property_type": [{"code": "Orphan"}],
                "application_docs": [
                    {"type": "Label", "url": "http://x/lbl.pdf", "date": "20250207"},
                    {"type": "Letter", "url": "https://x/ltr.pdf", "date": "20250207"},
                    {"type": "Letter", "url": "https://x/corrected.pdf", "date": "20250301"},
                    {"type": "Review", "url": "https://x/TOC.html", "date": "20250224"},
                    # A review FDA filed later under the same submission is not
                    # the approval package.
                    {"type": "Review", "url": "https://x/later-review.pdf", "date": "20260602"},
                ],
            },
            {"submission_type": "ORIG", "submission_number": "3", "submission_status": "TA"},
        ]
    }
    assert parse_original_approval(record) == {
        "approval_letter_url": "https://x/corrected.pdf",
        "review_url": "https://x/TOC.html",
        "label_url": "https://x/lbl.pdf",
        "submission_classification": "Type 1 - New Molecular Entity",
        "approval_date": "2025-01-30",
        "review_designation": "Priority",
        "orphan": "Yes",
    }
    assert set(parse_original_approval({"submissions": []}).values()) == {None}
    # No orphan property is "not recorded", never "No".
    plain = {
        "submissions": [
            {
                "submission_type": "ORIG",
                "submission_number": "1",
                "submission_status": "AP",
                "review_priority": "STANDARD",
            }
        ]
    }
    assert parse_original_approval(plain)["review_designation"] == "Standard"
    assert parse_original_approval(plain)["orphan"] is None


def _openfda_record(**extra) -> dict:
    return {
        "fetched": "2026-11-28",
        "sponsor_name": "ACME PHARMS INC",
        "products": [{"brand_name": "ALPHA FLEXTOUCH"}],
        "submissions": [
            {
                "submission_type": "ORIG",
                "submission_number": "1",
                "submission_status": "AP",
                "submission_status_date": "20260130",
                "submission_class_code_description": "Type 1 - New Molecular Entity",
                "review_priority": "PRIORITY",
                "submission_property_type": [{"code": "Orphan"}],
                "application_docs": [
                    {"type": "Letter", "url": "https://x/ltr.pdf"},
                    {"type": "Review", "url": "https://x/TOC.html"},
                    {"type": "Label", "url": "https://x/openfda-label.pdf"},
                ],
            }
        ],
        **extra,
    }


def test_openfda_refreshes_documents_and_fills_what_the_compilation_does_not_cover(
    tmp_path, monkeypatch
) -> None:
    import json

    from fda_sba import drugsfda

    for key in ("NDA111111", "BLA222222", "NDA333333"):
        (tmp_path / f"{key}.json").write_text(json.dumps(_openfda_record()))
    # An application openFDA does not have (withdrawn) is cached as empty.
    (tmp_path / "NDA444444.json").write_text(json.dumps({"fetched": "2026-11-28"}))
    monkeypatch.setattr(drugsfda, "urlopen", lambda *a, **k: pytest.fail("network used"))
    day = pd.Timestamp("2026-01-30").date()
    index = pd.DataFrame(
        {
            "drug_name": ["A", "B", "C", "D"],
            "application_type": ["NDA", "BLA", "NDA", "NDA"],
            "application_number": ["111111", "222222", "333333", "444444"],
            # C's list date is two days off; D's record is empty.
            "approval_date": [day, day, pd.Timestamp("2026-02-01").date(), day],
            "approval_letter_url": [None, None, "https://x/old-letter.pdf", "https://x/page.pdf"],
            "review_url": [None, None, None, None],
            "label_pdf_url": ["https://x/list-label.pdf", None, None, None],
            "submission_classification": [None, None, None, None],
            "sponsor": ["Named By The Compilation", None, None, "Page Sponsor"],
            "review_designation": ["Standard", None, None, None],
            "orphan_drug_designation": ["No", None, None, None],
        }
    )
    out = drugsfda.enrich_from_drugsfda(index, tmp_path).to_dict("records")
    a, b, c, d = out
    assert a["approval_letter_url"] == "https://x/ltr.pdf"
    assert a["label_pdf_url"] == "https://x/list-label.pdf"  # the list's label link is kept
    assert a["submission_classification"] == "Type 1 - New Molecular Entity"
    assert a["sponsor"] == "Named By The Compilation"
    # The compilation's designations are never overwritten.
    assert (a["review_designation"], a["orphan_drug_designation"]) == ("Standard", "No")
    assert a["designations_source"] == "compilation"
    assert a["documents_read"] == "2026-11-28"

    assert b["label_pdf_url"] == "https://x/openfda-label.pdf"
    assert pd.isna(b["submission_classification"])  # shown for NDAs only
    assert b["sponsor"] == "Acme Pharms INC"
    assert (b["review_designation"], b["orphan_drug_designation"]) == ("Priority", "Yes")
    assert b["designations_source"] == "openfda"

    assert c["approval_letter_url"] == "https://x/ltr.pdf"  # openFDA is the fresher read
    assert c["approval_date"] == day  # Drugs@FDA's date wins within a year

    assert d["approval_letter_url"] == "https://x/page.pdf"  # kept from the cached page
    assert d["sponsor"] == "Page Sponsor"
    assert pd.isna(d["documents_read"])
    assert pd.isna(d["designations_source"])


def test_a_brand_name_is_matched_only_when_the_approval_date_agrees(tmp_path, monkeypatch) -> None:
    import json

    from fda_sba import drugsfda

    monkeypatch.setattr(drugsfda, "REQUEST_DELAY", 0)
    asked: list[str] = []

    class Answer(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(req, timeout=30):
        asked.append(req.full_url)
        results = [
            {"application_number": "BLA761326", **_openfda_record()},
            # Same brand, approved years earlier: another product line.
            {
                "application_number": "NDA020000",
                **_openfda_record(
                    submissions=[
                        {
                            "submission_type": "ORIG",
                            "submission_number": "1",
                            "submission_status": "AP",
                            "submission_status_date": "20010101",
                        }
                    ]
                ),
            },
        ]
        return Answer(json.dumps({"meta": {}, "results": results}).encode())

    monkeypatch.setattr(drugsfda, "urlopen", urlopen)
    # The list says January 31; Drugs@FDA says January 30. Close enough.
    found = drugsfda.find_application("Alpha", "2026-01-31", tmp_path)
    assert found["application"] == "BLA761326"
    assert drugsfda.find_application("Alpha", "2026-06-30", tmp_path) is None
    assert len(asked) == 1  # the second lookup came from the cache
    assert drugsfda._same_brand("Alpha", "ALPHA FLEXTOUCH")
    assert not drugsfda._same_brand("Alpha", "ALPHABET")

    index = pd.DataFrame(
        {
            "drug_name": ["Alpha", "Listed"],
            "approval_date": [pd.Timestamp("2026-01-31").date()] * 2,
            "application_number": [None, "555555"],
            "application_type": [None, "NDA"],
            "drugs_at_fda_url": [None, "https://x/555555"],
        }
    )
    out = drugsfda.fill_application_numbers(index, tmp_path).to_dict("records")
    assert (out[0]["application_type"], out[0]["application_number"]) == ("BLA", "761326")
    assert out[0]["drugs_at_fda_url"].endswith("ApplNo=761326")
    assert out[1]["application_number"] == "555555"
    assert len(asked) == 1
