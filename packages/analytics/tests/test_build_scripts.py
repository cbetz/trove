"""Tests for the build scripts' pure logic: index notes, the noise floor, the
chart injector, source-vintage recording and the share card's wording.

The scripts live in ``scripts/`` (not a package), so they are loaded by path.
"""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gap_index():
    return _load("build_gap_index")


def _csv_row(**over) -> dict:
    """One row of the gap CSV, as csv.DictReader yields it (all strings)."""
    row = {
        "ein": "111111111",
        "ccn_count": "1",
        "crosswalk_ccn_count": "1",
        "ccn_list": "000001",
        "hospital_name": "TEST HOSPITAL",
        "city": "TOWN",
        "state": "CT",
        "hcris_charity_care_cost": "5000000",
        "sched_h_financial_assistance_at_cost": "2000000",
        "sched_h_financial_assistance_gross": "2000000",
        "sched_h_financial_assistance_offset_revenue": "",
        "hcris_total_operating_expenses": "100000000",
        "sched_h_total_expenses": "101000000",
        "hcris_fy_end_dt": "2022-12-31",
        "sched_h_tax_period_end": "2022-12-31",
        "period_aligned": "True",
        "hcris_report_status": "settled_without_audit",
        "hcris_medicaid_dsh_supplemental": "",
        "sched_h_amended_return": "False",
        "sched_h_fa_7a_consistent": "True",
        "svi_overall_pct": "",
    }
    row.update(over)
    return row


# ------------------------------------------------------------------ the floor


def test_a_negative_figure_does_not_pass_the_noise_floor(gap_index) -> None:
    """``abs(value) >= 500_000`` let a 7a (e) of -$3,063,123 count as ">= $500K"."""
    ok = _csv_row()
    negative_irs = _csv_row(ein="2", sched_h_financial_assistance_at_cost="-3063123")
    negative_cms = _csv_row(ein="3", hcris_charity_care_cost="-600000")
    below = _csv_row(ein="4", sched_h_financial_assistance_at_cost="499999")
    at_floor = _csv_row(ein="5", sched_h_financial_assistance_at_cost="500000")
    blank = _csv_row(ein="6", hcris_charity_care_cost="")
    kept = gap_index.material_subset([ok, negative_irs, negative_cms, below, at_floor, blank])
    assert [r["ein"] for r in kept] == ["111111111", "5"]


def test_a_negative_figure_is_not_in_the_index(gap_index) -> None:
    rows = [_csv_row(), _csv_row(ein="2", sched_h_financial_assistance_at_cost="-3063123")]
    assert [r["ein"] for r in gap_index.clean_index(rows)] == ["111111111"]


def test_published_material_subset_uses_the_strict_floor() -> None:
    gap = json.loads((ROOT / "web/data/community_benefit_gap_2022.json").read_text())
    index = json.loads((ROOT / "web/data/charity_care_gap_index_2022.json").read_text())
    material = [
        r
        for r in gap["rows"]
        if r["aligned"] and r["hcris_charity"] >= 500_000 and r["fa_990"] >= 500_000
    ]
    assert gap["totals"]["aligned_material"] == len(material)
    assert index["counts"]["aligned_material"] == len(material)
    big = sum(1 for r in material if abs(r["gap_pct"]) >= 0.5)
    assert gap["totals"]["aligned_material_big_gaps"] == big
    assert index["counts"]["aligned_material_50pct_or_more"] == big
    # Mount Sinai Beth Israel: aligned, 7a (e) negative — excluded.
    msbi = next(r for r in gap["rows"] if r["ein"] == "135564934")
    assert msbi["aligned"] and msbi["fa_990"] < 0
    assert msbi not in material


# ---------------------------------------------------------------- index notes


def test_notes_are_mechanical_and_in_fixed_order(gap_index) -> None:
    plain = gap_index.clean_index([_csv_row()])[0]
    assert plain["notes"] == []
    assert plain["ccns_with_cost_report"] == 1
    assert plain["crosswalk_ccn_count"] == 1
    assert plain["multi_ccn_crosswalk"] is False

    everything = gap_index.clean_index(
        [
            _csv_row(
                crosswalk_ccn_count="3",
                sched_h_financial_assistance_gross="13776776",
                sched_h_financial_assistance_offset_revenue="9000000",
                sched_h_financial_assistance_at_cost="2000000",
                hcris_medicaid_dsh_supplemental="-71469000",
                hcris_report_status="as_submitted",
                sched_h_amended_return="True",
            )
        ]
    )[0]
    assert everything["notes"] == list(gap_index.NOTE_CODES)
    assert everything["multi_ccn_crosswalk"] is True and everything["crosswalk_ccn_count"] == 3


@pytest.mark.parametrize(
    ("gross", "offset", "net", "flagged"),
    [
        ("3000000", "1000000", "2000000", False),  # exact
        ("3001000", "1000000", "2000000", False),  # $1,000 off: not MORE than $1,000
        ("3001001", "1000000", "2000000", True),
        ("2000000", "", "2000000", False),  # blank (d) reads as 0
        ("4000000", "", "2000000", True),
        ("", "1000000", "2000000", False),  # (c) blank: not checkable, not flagged
        ("1000000", "1000000", "2000000", True),  # (e) larger than (c) - (d)
    ],
)
def test_irs_7a_inconsistent_threshold(gap_index, gross, offset, net, flagged) -> None:
    row = gap_index.clean_index(
        [
            _csv_row(
                sched_h_financial_assistance_gross=gross,
                sched_h_financial_assistance_offset_revenue=offset,
                sched_h_financial_assistance_at_cost=net,
            )
        ]
    )[0]
    assert ("irs_7a_inconsistent" in row["notes"]) is flagged


def test_single_condition_notes(gap_index) -> None:
    def notes(**over):
        return gap_index.clean_index([_csv_row(**over)])[0]["notes"]

    assert notes(sched_h_financial_assistance_offset_revenue="0") == []
    assert notes(
        sched_h_financial_assistance_gross="2000001",
        sched_h_financial_assistance_offset_revenue="1",
    ) == ["irs_offset_reported"]
    assert notes(hcris_medicaid_dsh_supplemental="35795183") == ["cms_line5_reported"]
    assert notes(hcris_medicaid_dsh_supplemental="-1") == ["cms_line5_reported"]
    assert notes(crosswalk_ccn_count="2") == ["multi_ccn_crosswalk"]
    assert notes(hcris_report_status="as_submitted") == ["cms_report_as_submitted"]
    assert notes(hcris_report_status="amended") == []
    assert notes(sched_h_amended_return="True") == ["irs_amended_return"]


def test_published_index_notes_and_ccn_counts() -> None:
    index = json.loads((ROOT / "web/data/charity_care_gap_index_2022.json").read_text())
    codes = index["note_codes"]
    assert list(codes) == [
        "irs_7a_inconsistent",
        "irs_offset_reported",
        "cms_line5_reported",
        "multi_ccn_crosswalk",
        "cms_report_as_submitted",
        "irs_amended_return",
    ]
    for key in ("notes", "ccns_with_cost_report", "crosswalk_ccn_count", "multi_ccn_crosswalk"):
        assert key in index["fields"], key
    tally = dict.fromkeys(codes, 0)
    for r in index["rows"]:
        assert r["ccns_with_cost_report"] == 1
        assert r["crosswalk_ccn_count"] >= 1
        assert r["multi_ccn_crosswalk"] is (r["crosswalk_ccn_count"] > 1)
        assert set(r["notes"]) <= set(codes)
        assert ("multi_ccn_crosswalk" in r["notes"]) is r["multi_ccn_crosswalk"]
        assert ("irs_offset_reported" in r["notes"]) is ((r["irs_7a_offset"] or 0) > 0)
        assert ("cms_line5_reported" in r["notes"]) is (r["cms_s10_line5"] is not None)
        assert ("irs_amended_return" in r["notes"]) is r["amended_990"]
        assert ("cms_report_as_submitted" in r["notes"]) is (r["hcris_status"] == "as_submitted")
        for code in r["notes"]:
            tally[code] += 1
    assert index["counts"]["notes"] == tally
    assert index["counts"]["clean_multi_ccn_crosswalk"] == tally["multi_ccn_crosswalk"]
    yale = index["rows"][0]
    assert yale["notes"] == ["irs_offset_reported", "cms_line5_reported"]
    # Hendrick Medical Center: (c) - (d) = 13,776,776 but (e) = 4,523,276.
    hendrick = next(r for r in index["rows"] if r["ein"] == "750827446")
    assert "irs_7a_inconsistent" in hendrick["notes"]


def test_index_markdown_says_one_ccn_with_a_cost_report() -> None:
    md = (ROOT / "artifacts/charity_care_gap_index_2022.md").read_text()
    assert "exactly one CCN with a cost report" in md
    assert "one CCN under one EIN" not in md
    summary = (ROOT / "artifacts/community_benefit_gap_2022_summary.md").read_text()
    assert "one CCN with a cost report" in summary


# ------------------------------------------------------------- chart injector


def _index_rows(n: int = 12) -> list[dict]:
    rows = []
    for i in range(n):
        irs, cms = 1_000_000 * (i + 1), 1_500_000 * (n - i)
        rows.append(
            {
                "name": f"Hospital <{i}> & Co",
                "city": "Town",
                "state": "CT",
                "irs_7a": irs,
                "cms_s10": cms,
                "gap": cms - irs,
                "gap_pct": abs(cms - irs) / max(cms, irs),
                "period_end": "2022-12-31",
            }
        )
    return rows


def test_chart_is_accessible_and_escapes_names(gap_index) -> None:
    svg = gap_index.svg_chart(_index_rows())
    assert svg.count('class="dot ') == 12
    assert 'role="img"' in svg and 'aria-labelledby="gapchart-t gapchart-d"' in svg
    assert '<title id="gapchart-t">' in svg and '<desc id="gapchart-d">' in svg
    assert "12 hospitals" in svg
    assert "<0>" not in svg and "Hospital &lt;0&gt; &amp; Co" in svg
    assert svg.count('class="ring"') == gap_index.CHART_LABELS
    assert "http" not in svg  # no external resources
    frag = gap_index.chart_fragment(_index_rows())
    assert frag.startswith(gap_index.CHART_START) and frag.endswith(gap_index.CHART_END)
    assert frag.count(gap_index.CHART_START) == 1 and frag.count(gap_index.CHART_END) == 1
    assert "prefers-color-scheme: dark" in frag
    assert "innerHTML" not in frag
    assert "src=" not in frag and "@import" not in frag and "url(" not in frag


def test_splice_replaces_only_what_is_between_the_markers(gap_index) -> None:
    s, e = gap_index.CHART_START, gap_index.CHART_END
    page = f"<p>before</p>\n{s}\nOLD CHART\n{e}\n<p>after</p>"
    out = gap_index.splice_chart(page, f"{s}NEW{e}")
    assert out == f"<p>before</p>\n{s}NEW{e}\n<p>after</p>"
    # Idempotent: a second run changes nothing.
    assert gap_index.splice_chart(out, f"{s}NEW{e}") == out


@pytest.mark.parametrize(
    "page",
    [
        "<p>no markers at all</p>",
        "<!-- GAP_CHART:START --> only a start",
        "only an end <!-- GAP_CHART:END -->",
        "<!-- GAP_CHART:END --> reversed <!-- GAP_CHART:START -->",
        "<!-- GAP_CHART:START --> a <!-- GAP_CHART:END --> <!-- GAP_CHART:START --> b "
        "<!-- GAP_CHART:END -->",
        "<!-- GAP_CHART:START --> a <!-- GAP_CHART:END --> stray <!-- GAP_CHART:END -->",
        "<!--GAP_CHART:START--> wrong spacing <!--GAP_CHART:END-->",
    ],
)
def test_splice_fails_loudly_on_unusable_markers(gap_index, page) -> None:
    with pytest.raises(gap_index.ChartMarkerError):
        gap_index.splice_chart(page, "X")


def test_write_chart_is_all_or_nothing(gap_index, tmp_path) -> None:
    s, e = gap_index.CHART_START, gap_index.CHART_END
    good = tmp_path / "good.html"
    bad = tmp_path / "bad.html"
    good.write_text(f"<main>{s}old{e}</main>")
    bad.write_text("<main>markers were deleted</main>")
    with pytest.raises(gap_index.ChartMarkerError, match="bad.html"):
        gap_index.write_chart(_index_rows(), targets=(good, bad))
    assert good.read_text() == f"<main>{s}old{e}</main>"  # untouched

    with pytest.raises(gap_index.ChartMarkerError, match="does not exist"):
        gap_index.write_chart(_index_rows(), targets=(good, tmp_path / "missing.html"))
    assert good.read_text() == f"<main>{s}old{e}</main>"

    with pytest.raises(gap_index.ChartMarkerError, match="empty chart"):
        gap_index.write_chart([], targets=(good,))

    bad.write_text(f"{s}{e}")
    assert gap_index.write_chart(_index_rows(), targets=(good, bad)) == [good, bad]
    assert good.read_text().startswith(f"<main>{s}") and good.read_text().endswith(f"{e}</main>")
    assert 'class="gapchart"' in good.read_text() and "old" not in good.read_text()


def test_site_pages_have_exactly_one_marker_pair(gap_index) -> None:
    """The injector's precondition, checked against the real pages."""
    for path in gap_index.CHART_TARGETS:
        text = path.read_text()
        assert text.count(gap_index.CHART_START) == 1, path
        assert text.count(gap_index.CHART_END) == 1, path
        assert text.index(gap_index.CHART_START) < text.index(gap_index.CHART_END), path


# ------------------------------------------------------------- source vintage


def test_cms_vintage_comes_from_the_files_not_a_literal(tmp_path) -> None:
    dataset = _load("build_gap_dataset")
    with zipfile.ZipFile(tmp_path / "HOSP10FY2022.zip", "w") as zf:
        for name, when in (
            ("HOSP10_2022_rpt.csv", (2031, 3, 4, 1, 2, 4)),
            ("x.csv", (2031, 3, 1, 0, 0, 0)),
        ):
            zf.writestr(zipfile.ZipInfo(name, date_time=when), "1,2,000001\n")
    with zipfile.ZipFile(tmp_path / "HOSP10FY2024.zip", "w") as zf:
        zf.writestr("HOSP10_2024_rpt.csv", "9,2,000002,x\n8,2,000777,x\n")
    wide = pd.DataFrame(
        {
            "hcris_file_fy": [2022, 2022, 2023],
            "prvdr_num": ["000001", "000005", "000001"],
            "proc_dt": pd.to_datetime(["2031-01-05", "2031-02-27", "2030-12-01"]),
        }
    )
    sched = pd.DataFrame(
        {"ein": ["1", "1", "2"], "release_year": [2023, 2024, 2024], "batch_id": ["a", "b", "b"]}
    )
    cw = pd.DataFrame(
        {"ccn": ["000001", "000002", "000003", "000009"], "ein": ["1", "1", "1", "5"]}
    )
    gap = pd.DataFrame({"ein": ["1"]})
    v = dataset.source_vintage(wide, sched, cw, gap, previous=None, raw_dir=tmp_path)

    fy22, fy23 = v["cms_hcris"]["files"]
    assert fy22["extract_date"] == "2031-03-04"  # newest member inside the ZIP
    assert fy22["latest_proc_dt"] == "2031-02-27" and fy22["reports"] == 2
    assert len(fy22["zip_sha256"]) == 64
    # No FY2023 ZIP on disk and nothing recorded before: unknown, not invented.
    assert fy23["extract_date"] is None and fy23["zip_sha256"] is None
    assert fy23["latest_proc_dt"] == "2030-12-01"
    # EIN 1's crosswalk CCNs 000002 and 000003 have no loaded report; 000002 is in FY2024.
    assert v["crosswalk"] == {
        "eins": 2,
        "ccns_without_cost_report": 2,
        "also_checked_fiscal_years": [2024],
        "found_in_also_checked": 1,
    }
    assert v["irs_990"]["returns_by_release_year"] == {"2023": 1, "2024": 2}

    # ZIPs deleted, parsed data unchanged: recorded values are carried forward...
    for z in tmp_path.glob("*.zip"):
        z.unlink()
    again = dataset.source_vintage(wide, sched, cw, gap, previous=v, raw_dir=tmp_path)
    assert again["cms_hcris"]["files"][0]["extract_date"] == "2031-03-04"
    assert again["crosswalk"]["found_in_also_checked"] == 1
    # ...but not when the parsed file is a different vintage.
    newer = wide.assign(proc_dt=pd.to_datetime(["2031-06-01"] * 3))
    stale = dataset.source_vintage(newer, sched, cw, gap, previous=v, raw_dir=tmp_path)
    assert stale["cms_hcris"]["files"][0]["extract_date"] is None
    assert stale["crosswalk"]["found_in_also_checked"] is None


def test_vintage_sentence_and_published_summary(gap_index) -> None:
    sources = {
        "cms_hcris": {
            "files": [
                {"fiscal_year": 2022, "extract_date": "2031-03-04", "latest_proc_dt": "2031-02-27"},
                {"fiscal_year": 2023, "extract_date": "2031-03-04", "latest_proc_dt": "2031-02-28"},
            ]
        }
    }
    text = gap_index.cms_vintage_sentence(sources)
    assert "FY2022 and FY2023" in text and "2031-03-04" in text and "2031-02-28" in text
    assert "posted" not in text
    for f in sources["cms_hcris"]["files"]:
        f["posted_date"] = "2031-03-07"
    assert "CMS extract generated 2031-03-04, posted 2031-03-07" in gap_index.cms_vintage_sentence(
        sources
    )
    sources["cms_hcris"]["files"][1]["extract_date"] = None
    assert "extract generated" not in gap_index.cms_vintage_sentence(sources)

    recorded = json.loads((ROOT / "artifacts/community_benefit_gap_2022_sources.json").read_text())
    summary = (ROOT / "artifacts/community_benefit_gap_2022_summary.md").read_text()
    assert gap_index.cms_vintage_sentence(recorded) in summary
    index = json.loads((ROOT / "web/data/charity_care_gap_index_2022.json").read_text())
    assert index["sources"]["cms_files"] == recorded["cms_hcris"]["files"]
    src = (ROOT / "scripts/build_gap_index.py").read_text()
    for f in recorded["cms_hcris"]["files"]:
        for key in ("extract_date", "latest_proc_dt"):
            assert f[key] and f[key] not in src, f"{key} is hard-coded in build_gap_index.py"


# ----------------------------------------------------------------- share card


def test_share_card_text_is_neutral_and_reads_the_index() -> None:
    og = _load("build_og_image")
    text = og.card_text(
        {"tax_year": 2022, "counts": {"clean_aligned": 1493, "clean_aligned_over_50pct": 107}}
    )
    assert text == {
        "line_1": "Hospital charity care:",
        "line_2": "the IRS figure and the CMS figure, side by side",
        "line_3": "1,493 hospitals · tax year 2022 · with the components behind each difference",
    }
    src = (ROOT / "scripts/build_og_image.py").read_text()
    assert "don't match" not in src
    assert og.OG_SIZE == (1200, 630) and og.SOCIAL_SIZE == (1280, 640)
