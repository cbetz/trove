import pandas as pd
from analytics import community_benefit_gap


def _crosswalk() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ccn": "330101", "ein": "111111111", "hospital_name": "Big AMC"},
            {"ccn": "330102", "ein": "111111111", "hospital_name": "Big AMC - Annex"},
            {"ccn": "440039", "ein": "222222222", "hospital_name": "Solo Hospital"},
            {"ccn": "999999", "ein": "999999999", "hospital_name": "No Match Hospital"},
        ]
    )


def _hcris_wide() -> pd.DataFrame:
    return pd.DataFrame(
        [
            # Big AMC: two CCNs under one EIN, charity care should sum to 60M
            {
                "prvdr_num": "330101",
                "hospital_name": "BIG AMC FLAGSHIP",
                "charity_care_cost": 50_000_000.0,
                "uncompensated_care_cost": 70_000_000.0,
                "total_operating_expenses": 5_000_000_000.0,
            },
            {
                "prvdr_num": "330102",
                "hospital_name": "BIG AMC ANNEX",
                "charity_care_cost": 10_000_000.0,
                "uncompensated_care_cost": 12_000_000.0,
                "total_operating_expenses": 1_000_000_000.0,
            },
            # Solo Hospital: one CCN
            {
                "prvdr_num": "440039",
                "hospital_name": "SOLO HOSPITAL",
                "charity_care_cost": 30_000_000.0,
                "uncompensated_care_cost": 40_000_000.0,
                "total_operating_expenses": 2_000_000_000.0,
            },
            # Hospital not in crosswalk — should be dropped
            {
                "prvdr_num": "111111",
                "hospital_name": "ORPHAN HOSPITAL",
                "charity_care_cost": 5_000_000.0,
                "uncompensated_care_cost": 6_000_000.0,
                "total_operating_expenses": 100_000_000.0,
            },
        ]
    )


def _schedule_h() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ein": "111111111",
                "organization_name": "Big AMC",
                "tax_period_end": pd.Timestamp("2022-12-31"),
                "financial_assistance_at_cost": 40_000_000.0,
                "total_community_benefit": 800_000_000.0,
                "total_expenses": 6_000_000_000.0,
            },
            {
                "ein": "222222222",
                "organization_name": "Solo Hospital",
                "tax_period_end": pd.Timestamp("2022-12-31"),
                "financial_assistance_at_cost": 35_000_000.0,
                "total_community_benefit": 100_000_000.0,
                "total_expenses": 2_000_000_000.0,
            },
            # An older filing for Big AMC — should NOT win the dedup
            {
                "ein": "111111111",
                "organization_name": "Big AMC (old)",
                "tax_period_end": pd.Timestamp("2020-12-31"),
                "financial_assistance_at_cost": 1.0,
                "total_community_benefit": 1.0,
                "total_expenses": 1.0,
            },
        ]
    )


def test_aggregates_hcris_facilities_under_one_ein() -> None:
    out = community_benefit_gap(_hcris_wide(), _schedule_h(), _crosswalk())
    big_amc = out[out["ein"] == "111111111"].iloc[0]
    assert big_amc["ccn_count"] == 2
    assert big_amc["hcris_charity_care_cost"] == 60_000_000.0
    assert big_amc["hcris_uncompensated_care_cost"] == 82_000_000.0


def test_charity_gap_is_hcris_minus_schedule_h() -> None:
    out = community_benefit_gap(_hcris_wide(), _schedule_h(), _crosswalk()).set_index("ein")
    # Big AMC: 60M HCRIS charity - 40M 990 charity = +20M
    assert out.loc["111111111", "charity_gap"] == 20_000_000.0
    # Solo: 30M HCRIS - 35M 990 = -5M (Schedule H reports MORE)
    assert out.loc["222222222", "charity_gap"] == -5_000_000.0


def test_dedupes_990_amendments_keeping_latest() -> None:
    out = community_benefit_gap(_hcris_wide(), _schedule_h(), _crosswalk()).set_index("ein")
    big = out.loc["111111111"]
    assert big["sched_h_financial_assistance_at_cost"] == 40_000_000.0  # not the old 1.0
    assert big["sched_h_tax_period_end"] == pd.Timestamp("2022-12-31")


def test_drops_hospitals_not_in_crosswalk() -> None:
    out = community_benefit_gap(_hcris_wide(), _schedule_h(), _crosswalk())
    eins = set(out["ein"])
    assert "999999999" not in eins  # in crosswalk but no HCRIS row
    # No row for the unmatched CCN 111111 — it never gets to the join because
    # there's no crosswalk entry for it.


def test_sorted_by_absolute_charity_gap() -> None:
    out = community_benefit_gap(_hcris_wide(), _schedule_h(), _crosswalk())
    abs_gaps = out["charity_gap"].abs().tolist()
    assert abs_gaps == sorted(abs_gaps, reverse=True)
