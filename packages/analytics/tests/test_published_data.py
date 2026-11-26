"""Assert key published numbers in ``web/data`` against a hand-verified anchor.

The anchor is Yale New Haven Hospital (EIN 060646652, CCN 070022), fiscal year
ending 2023-09-30, read off the two source filings:

- IRS Form 990 Schedule H Part I line 7a: (c) $257,262,512, (d) $144,162,000,
  (e) $113,100,512
- CMS cost report Worksheet S-10: line 23 col 3 $35,568,680, line 5 -$71,469,000

These tests read the committed bundles, so they fail if a rebuild silently changes
what the site and the skills serve.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

WEB_DATA = Path(__file__).resolve().parents[3] / "web" / "data"
ARTIFACTS = Path(__file__).resolve().parents[3] / "artifacts"

YALE_EIN = "060646652"
YALE = {
    "gross_7a_c": 257_262_512,
    "offset_7a_d": 144_162_000,
    "net_7a_e": 113_100_512,
    "s10_line23_col3": 35_568_680,
    "s10_line5": -71_469_000,
}


@pytest.fixture(scope="module")
def gap_json() -> dict:
    return json.loads((WEB_DATA / "community_benefit_gap_2022.json").read_text())


@pytest.fixture(scope="module")
def index_json() -> dict:
    return json.loads((WEB_DATA / "charity_care_gap_index_2022.json").read_text())


@pytest.fixture(scope="module")
def gap_csv() -> list[dict]:
    with (WEB_DATA / "community_benefit_gap_2022.csv").open() as f:
        return list(csv.DictReader(f))


def _all_rows(gap_json: dict) -> list[dict]:
    return gap_json["rows"] + gap_json["rows_not_computable"]


def _by_ein(rows: list[dict], ein: str) -> dict:
    hits = [r for r in rows if r["ein"] == ein]
    assert len(hits) == 1, f"expected exactly one row for EIN {ein}, got {len(hits)}"
    return hits[0]


def test_yale_anchor_in_lookup_json(gap_json) -> None:
    r = _by_ein(gap_json["rows"], YALE_EIN)
    assert r["fa_990_gross"] == YALE["gross_7a_c"]
    assert r["fa_990_offset"] == YALE["offset_7a_d"]
    assert r["fa_990"] == YALE["net_7a_e"]
    assert r["hcris_charity"] == YALE["s10_line23_col3"]
    assert r["hcris_dsh_supplemental"] == YALE["s10_line5"]
    assert r["gap"] == YALE["s10_line23_col3"] - YALE["net_7a_e"]
    assert r["gap_gross"] == YALE["s10_line23_col3"] - YALE["gross_7a_c"]
    assert r["period_end"] == r["hcris_fy_end"] == "2023-09-30"
    assert r["hcris_fy_begin"] == "2022-10-01"
    assert r["ccn_list"] == ["070022"]
    assert r["aligned"] is True and r["computable"] is True
    assert r["state"] == "CT"


def test_yale_anchor_in_csv_and_parquet(gap_csv) -> None:
    r = _by_ein(gap_csv, YALE_EIN)
    assert int(r["sched_h_financial_assistance_gross"]) == YALE["gross_7a_c"]
    assert int(r["sched_h_financial_assistance_offset_revenue"]) == YALE["offset_7a_d"]
    assert int(r["sched_h_financial_assistance_at_cost"]) == YALE["net_7a_e"]
    assert int(r["hcris_charity_care_cost"]) == YALE["s10_line23_col3"]
    assert int(r["hcris_medicaid_dsh_supplemental"]) == YALE["s10_line5"]
    assert r["ccn_list"] == "070022"
    assert r["period_aligned"] == "True"

    pq = pd.read_parquet(WEB_DATA / "community_benefit_gap_2022.parquet")
    row = pq[pq["ein"] == YALE_EIN].iloc[0]
    assert row["hcris_charity_care_cost"] == YALE["s10_line23_col3"]
    assert row["sched_h_financial_assistance_gross"] == YALE["gross_7a_c"]
    assert row["hcris_medicaid_dsh_supplemental"] == YALE["s10_line5"]
    assert len(pq) == len(gap_csv)


def test_yale_anchor_in_source_bundles() -> None:
    hcris = pd.read_parquet(WEB_DATA / "hcris_2023_wide.parquet")
    rep = hcris[(hcris["prvdr_num"] == "070022")].iloc[0]
    assert rep["charity_care_cost"] == YALE["s10_line23_col3"]
    assert rep["medicaid_dsh_supplemental_payments"] == YALE["s10_line5"]
    assert str(pd.Timestamp(rep["fy_end_dt"]).date()) == "2023-09-30"

    sched = pd.read_parquet(WEB_DATA / "schedule_h_2022.parquet")
    ret = sched[sched["ein"] == YALE_EIN].iloc[0]
    assert ret["financial_assistance_at_cost_gross"] == YALE["gross_7a_c"]
    assert ret["financial_assistance_at_cost_offset_revenue"] == YALE["offset_7a_d"]
    assert ret["financial_assistance_at_cost"] == YALE["net_7a_e"]


def test_yale_leads_the_index_with_components(index_json) -> None:
    first = index_json["rows"][0]
    assert first["ein"] == YALE_EIN
    assert first["irs_7a_gross"] == YALE["gross_7a_c"]
    assert first["irs_7a_offset"] == YALE["offset_7a_d"]
    assert first["irs_7a"] == YALE["net_7a_e"]
    assert first["cms_s10"] == YALE["s10_line23_col3"]
    assert first["cms_s10_line5"] == YALE["s10_line5"]
    assert first["gap"] == YALE["s10_line23_col3"] - YALE["net_7a_e"]
    assert first["object_id"]
    assert "Tampa General" in index_json["rows"][1]["name"]


def test_index_rows_satisfy_the_published_definition(index_json) -> None:
    f = index_json["filter"]
    rows = index_json["rows"]
    assert index_json["counts"]["clean_aligned"] == len(rows)
    assert len({r["ein"] for r in rows}) == len(rows)
    for r in rows:
        assert r["irs_7a"] >= f["material_floor_usd"]
        assert r["cms_s10"] >= f["material_floor_usd"]
        assert r["gap"] == r["cms_s10"] - r["irs_7a"]
        end, period = r["hcris_fy_end"], r["period_end"]
        months = abs((int(end[:4]) - int(period[:4])) * 12 + int(end[5:7]) - int(period[5:7]))
        assert months <= f["alignment_months_max"]
        assert ";" not in r["ccn"]
    gaps = [abs(r["gap"]) for r in rows]
    assert gaps == sorted(gaps, reverse=True)
    over = sum(1 for r in rows if r["gap_pct"] > 0.5)
    assert index_json["counts"]["clean_aligned_over_50pct"] == over


def test_no_false_zeros_anywhere(gap_json, gap_csv) -> None:
    """CMS never stores a zero, so a published 0 for S-10 charity care can only be
    a missing value summed into a number. Johns Hopkins, St. Jude and Texas
    Children's — $0 in earlier versions — must be null, with a null gap."""
    assert not [r for r in gap_csv if r["hcris_charity_care_cost"] in ("0", "0.0")]
    assert not [r for r in _all_rows(gap_json) if r["hcris_charity"] == 0]
    for ein in ("520591656", "620646012", "741100555"):
        assert not [r for r in gap_json["rows"] if r["ein"] == ein]
        j = _by_ein(gap_json["rows_not_computable"], ein)
        assert j["hcris_charity"] is None
        assert j["gap"] is None and j["gap_pct"] is None and j["gap_gross"] is None
        assert j["computable"] is False
        assert j["fa_990"] is not None
        c = _by_ein(gap_csv, ein)
        assert c["hcris_charity_care_cost"] == "" and c["charity_gap"] == ""
    # ``rows`` is the computable set and every gap there is a number, so readers
    # written for earlier versions never meet a null; the rest are kept apart.
    for r in gap_json["rows"]:
        assert r["computable"] is True
        assert isinstance(r["gap"], int) and r["hcris_charity"] is not None
    for r in gap_json["rows_not_computable"]:
        assert r["computable"] is False
        assert r["gap"] is None and r["gap_pct"] is None


def test_2023_release_filers_are_present(gap_json) -> None:
    """Calendar-year filers whose TY2022 return is in the IRS 2023 release."""
    rows = {r["ein"]: r for r in _all_rows(gap_json)}
    for ein in ("383952644", "912153073", "133957095", "131624096"):  # Mayo, CCF, NYP, Mt Sinai
        assert ein in rows, ein
        assert rows[ein]["release_year"] == 2023
        assert rows[ein]["period_end"] == "2022-12-31"
    assert {r["release_year"] for r in gap_json["rows"]} >= {2023, 2024, 2025}
    # Mayo, NewYork-Presbyterian and Mount Sinai are computable. Cleveland Clinic
    # is not: one of its 17 CCNs has no S-10 line 23, so the system total is null
    # and the partial total is published beside it.
    computable = {r["ein"] for r in gap_json["rows"]}
    assert {"383952644", "133957095", "131624096"} <= computable
    ccf = rows["912153073"]
    assert ccf["hcris_charity"] is None and ccf["ccns_missing_s10_charity"] >= 1
    assert ccf["hcris_charity_reporting_ccns"] > 0


def test_totals_are_consistent_with_rows(gap_json, gap_csv, index_json) -> None:
    t, rows = gap_json["totals"], gap_json["rows"]
    assert t["matched"] == len(_all_rows(gap_json)) == len(gap_csv)
    assert t["computable"] == len(rows)
    assert t["aligned"] == sum(r["aligned"] for r in rows)
    assert t["matched_minus_computable"] == t["matched"] - t["computable"]
    assert index_json["counts"]["matched"] == t["matched"]
    assert index_json["counts"]["computable"] == t["computable"]
    assert index_json["counts"]["aligned"] == t["aligned"]
    # The committed artifact and the served CSV are the same bytes.
    served = (WEB_DATA / "community_benefit_gap_2022.csv").read_bytes()
    assert served == (ARTIFACTS / "community_benefit_gap_2022.csv").read_bytes()


def test_legacy_fields_are_still_there(gap_json, gap_csv, index_json) -> None:
    """The site JS and the skills read these names; add, never rename."""
    legacy_json = {
        "ein", "system", "facility", "ccns", "period_end", "hcris_fy_end", "hcris_charity",
        "hcris_uncomp", "hcris_opex", "fa_990", "cb_990", "exp_990", "gap", "gap_pct", "cb_pct",
        "svi_overall_pct", "svi_socio_pct", "svi_household_pct", "svi_minority_pct",
        "svi_housing_pct",
    }  # fmt: skip
    assert legacy_json <= set(gap_json["rows"][0])
    assert {"matched", "computable", "aligned", "aligned_material"} <= set(gap_json["totals"])
    legacy_csv = [
        "ein", "ccn_count", "hospital_name", "hcris_charity_care_cost",
        "hcris_uncompensated_care_cost", "hcris_total_operating_expenses", "hcris_fy_end_dt",
        "svi_overall_pct", "svi_socio_pct", "svi_household_pct", "svi_minority_pct",
        "svi_housing_pct", "sched_h_organization_name", "sched_h_tax_period_end",
        "sched_h_financial_assistance_at_cost", "sched_h_total_community_benefit",
        "sched_h_total_expenses", "charity_gap", "community_benefit_pct_of_expenses",
        "community_benefit_pct_of_hcris_expenses",
    ]  # fmt: skip
    assert list(gap_csv[0])[: len(legacy_csv)] == legacy_csv
    legacy_index = {
        "ein", "name", "irs_7a", "cms_s10", "gap", "gap_pct", "expense_base", "hcris_fy_end",
        "period_end", "svi_overall_pct",
    }  # fmt: skip
    assert legacy_index <= set(index_json["rows"][0])
    for name in ("hcris_2023_wide.parquet", "schedule_h_2022.parquet"):
        assert (WEB_DATA / name).exists()
