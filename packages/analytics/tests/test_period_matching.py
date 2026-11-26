"""Missing-stays-missing, fiscal-period matching, and the published components."""

from __future__ import annotations

import numpy as np
import pandas as pd
from analytics import community_benefit_gap
from analytics.community_benefit import months_apart, select_period_matched_reports


def _report(ccn: str, end: str, charity: float | None, **extra) -> dict:
    end_ts = pd.Timestamp(end)
    return {
        "rpt_rec_num": extra.pop("rpt_rec_num", abs(hash((ccn, end))) % 10**6),
        "prvdr_num": ccn,
        "fy_bgn_dt": end_ts - pd.DateOffset(years=1) + pd.Timedelta(days=1),
        "fy_end_dt": end_ts,
        "rpt_stus_cd": extra.pop("rpt_stus_cd", 1),
        "proc_dt": pd.Timestamp(extra.pop("proc_dt", "2025-01-01")),
        "rpt_status": "as_submitted",
        "s10_filed": extra.pop("s10_filed", True),
        "hospital_name": f"HOSPITAL {ccn}",
        "charity_care_cost": np.nan if charity is None else charity,
        "charity_care_cost_uninsured": extra.pop("uninsured", np.nan),
        "charity_care_cost_insured": extra.pop("insured", np.nan),
        "medicaid_dsh_supplemental_payments": extra.pop("line5", np.nan),
        "uncompensated_care_cost": extra.pop("uncomp", np.nan),
        "total_operating_expenses": extra.pop("opex", 1_000_000_000.0),
    }


def _sched(ein: str, end: str, net: float | None, **extra) -> dict:
    end_ts = pd.Timestamp(end)
    return {
        "ein": ein,
        "organization_name": f"ORG {ein}",
        "tax_period_begin": end_ts - pd.DateOffset(years=1) + pd.Timedelta(days=1),
        "tax_period_end": end_ts,
        "financial_assistance_at_cost": np.nan if net is None else net,
        "financial_assistance_at_cost_gross": extra.pop("gross", np.nan),
        "financial_assistance_at_cost_offset_revenue": extra.pop("offset", np.nan),
        "total_community_benefit": 100_000_000.0,
        "total_expenses": 1_000_000_000.0,
        "object_id": extra.pop("object_id", "202400000000000001"),
        "release_year": extra.pop("release_year", 2024),
    }


def _cw(*pairs: tuple[str, str]) -> pd.DataFrame:
    return pd.DataFrame([{"ccn": c, "ein": e, "city": "Town", "state": "CT"} for c, e in pairs])


def _gap(reports: list[dict], scheds: list[dict], cw: pd.DataFrame) -> pd.DataFrame:
    return community_benefit_gap(pd.DataFrame(reports), pd.DataFrame(scheds), cw).set_index("ein")


# ---------------------------------------------------------------- false zeros


def test_missing_s10_stays_missing_not_zero() -> None:
    """A hospital with no S-10 line 23 must not be published as reporting $0."""
    out = _gap(
        [_report("210009", "2023-06-30", None)],
        [_sched("520591656", "2023-06-30", 63_958_981.0)],
        _cw(("210009", "520591656")),
    )
    row = out.loc["520591656"]
    assert pd.isna(row["hcris_charity_care_cost"])
    assert row["hcris_charity_care_cost"] != 0
    assert pd.isna(row["charity_gap"])
    assert pd.isna(row["charity_gap_gross"])
    assert pd.isna(row["hcris_uncompensated_care_cost"])
    assert pd.isna(row["hcris_medicaid_dsh_supplemental"])
    assert row["hcris_ccns_missing_charity"] == 1
    # The 990 side is untouched.
    assert row["sched_h_financial_assistance_at_cost"] == 63_958_981.0


def test_missing_schedule_h_7a_stays_missing() -> None:
    out = _gap(
        [_report("111111", "2022-12-31", 5_000_000.0)],
        [_sched("111111111", "2022-12-31", None)],
        _cw(("111111", "111111111")),
    )
    assert pd.isna(out.loc["111111111", "charity_gap"])
    assert out.loc["111111111", "hcris_charity_care_cost"] == 5_000_000.0


def test_multi_ccn_total_is_missing_when_any_ccn_is_missing() -> None:
    """A partial sum would understate the system, so the headline is empty and the
    partial total is published separately."""
    out = _gap(
        [_report("000001", "2022-12-31", 10_000_000.0), _report("000002", "2022-12-31", None)],
        [_sched("111111111", "2022-12-31", 4_000_000.0)],
        _cw(("000001", "111111111"), ("000002", "111111111")),
    )
    row = out.loc["111111111"]
    assert row["ccn_count"] == 2
    assert pd.isna(row["hcris_charity_care_cost"])
    assert row["hcris_charity_care_cost_reporting_ccns"] == 10_000_000.0
    assert row["hcris_ccns_missing_charity"] == 1
    assert pd.isna(row["charity_gap"])


def test_missing_survives_csv_roundtrip(tmp_path) -> None:
    """The publication path (nullable ints -> CSV) writes an empty field, never 0."""
    out = _gap(
        [_report("210009", "2023-06-30", None)],
        [_sched("520591656", "2023-06-30", 63_958_981.0)],
        _cw(("210009", "520591656")),
    ).reset_index()
    out["hcris_charity_care_cost"] = out["hcris_charity_care_cost"].round(0).astype("Int64")
    out["charity_gap"] = out["charity_gap"].round(0).astype("Int64")
    path = tmp_path / "gap.csv"
    out.to_csv(path, index=False)
    back = pd.read_csv(path, dtype={"ein": str})
    assert back["hcris_charity_care_cost"].isna().all()
    assert back["charity_gap"].isna().all()


# ------------------------------------------------------------ period matching


def test_months_apart_matches_index_arithmetic() -> None:
    a = pd.Series(pd.to_datetime(["2023-06-30", "2023-06-30", "2024-06-30", None]))
    b = pd.Series(pd.to_datetime(["2023-06-30", "2023-07-01", "2023-06-30", "2023-06-30"]))
    out = months_apart(a, b)
    assert out.iloc[:3].tolist() == [0, 1, 12]
    assert pd.isna(out.iloc[3])


def test_picks_the_cost_report_for_the_990s_own_period() -> None:
    """June year-end filer: the FY2023 HCRIS file holds the report ending June 2024
    (twelve months late); the right one, ending June 2023, is in the FY2022 file."""
    out = _gap(
        [
            _report("111111", "2023-06-30", 7_000_000.0, rpt_rec_num=1),  # FY2022 file
            _report("111111", "2024-06-30", 9_000_000.0, rpt_rec_num=2),  # FY2023 file
        ],
        [_sched("111111111", "2023-06-30", 6_000_000.0)],
        _cw(("111111", "111111111")),
    )
    row = out.loc["111111111"]
    assert row["hcris_charity_care_cost"] == 7_000_000.0
    assert row["hcris_fy_end_dt"] == pd.Timestamp("2023-06-30")
    assert row["hcris_fy_bgn_dt"] == pd.Timestamp("2022-07-01")
    assert row["hcris_months_from_990"] == 0
    assert bool(row["period_aligned"]) is True
    assert row["hcris_rpt_rec_num"] == "1"
    assert row["charity_gap"] == 1_000_000.0


def test_one_month_tolerance_and_unaligned_flag() -> None:
    out = _gap(
        [
            _report("000001", "2023-07-31", 1_000_000.0),  # 1 month from the 990: aligned
            _report("000002", "2024-06-30", 2_000_000.0),  # 12 months: not aligned
        ],
        [_sched("111111111", "2023-06-30", 1.0), _sched("222222222", "2023-06-30", 1.0)],
        _cw(("000001", "111111111"), ("000002", "222222222")),
    )
    assert bool(out.loc["111111111", "period_aligned"]) is True
    assert out.loc["111111111", "hcris_months_from_990"] == 1
    assert bool(out.loc["222222222", "period_aligned"]) is False
    assert out.loc["222222222", "hcris_months_from_990"] == 12
    # The nearest report is still shown, flagged, rather than dropping the row.
    assert out.loc["222222222", "hcris_charity_care_cost"] == 2_000_000.0


def test_multi_ccn_is_aligned_only_if_every_ccn_matches() -> None:
    out = _gap(
        [
            _report("000001", "2022-12-31", 5_000_000.0, opex=2e9),
            _report("000002", "2023-06-30", 1_000_000.0, opex=1e9),  # different fiscal year
            _report("000003", "2022-12-31", 3_000_000.0, opex=2e9),
            _report("000004", "2022-12-31", 4_000_000.0, opex=1e9),
        ],
        [_sched("111111111", "2022-12-31", 1.0), _sched("222222222", "2022-12-31", 1.0)],
        _cw(
            ("000001", "111111111"),
            ("000002", "111111111"),
            ("000003", "222222222"),
            ("000004", "222222222"),
        ),
    )
    mixed, clean = out.loc["111111111"], out.loc["222222222"]
    assert bool(mixed["period_aligned"]) is False
    # The published dates are the worst-matching CCN's, so they agree with the flag.
    assert mixed["hcris_fy_end_dt"] == pd.Timestamp("2023-06-30")
    assert mixed["hcris_months_from_990"] == 6
    assert bool(clean["period_aligned"]) is True
    assert clean["hcris_charity_care_cost"] == 7_000_000.0
    # Lead facility (largest operating expenses) first.
    assert clean["ccn_list"] == "000003;000004"
    assert clean["hospital_name"] == "HOSPITAL 000003"


def test_duplicate_reports_for_one_period_prefer_authoritative_then_latest() -> None:
    targets = pd.DataFrame(
        {"ein": ["1"] * 1, "ccn": ["000001"], "tax_period_end": [pd.Timestamp("2022-12-31")]}
    )
    reports = pd.DataFrame(
        [
            _report(
                "000001", "2022-12-31", 1.0, rpt_rec_num=10, rpt_stus_cd=1, proc_dt="2026-01-01"
            ),
            _report(
                "000001", "2022-12-31", 2.0, rpt_rec_num=11, rpt_stus_cd=3, proc_dt="2025-01-01"
            ),
            _report(
                "000001", "2022-12-31", 3.0, rpt_rec_num=12, rpt_stus_cd=5, proc_dt="2026-06-01"
            ),
        ]
    )
    # Settled with audit (3) outranks amended (5) and as-submitted (1).
    assert select_period_matched_reports(reports, targets)["rpt_rec_num"].tolist() == [11]
    # Same status: the most recently processed wins.
    reports["rpt_stus_cd"] = 1
    assert select_period_matched_reports(reports, targets)["rpt_rec_num"].tolist() == [12]


def test_equidistant_reports_take_the_same_side_for_every_ccn_of_an_ein() -> None:
    """A June year-end 990 is 6 months from both the prior and the next calendar-year
    cost report. Status used to decide per CCN, so one EIN could mix 2022-12-31 and
    2023-12-31 reports. The side is now chosen once per EIN."""
    targets = pd.DataFrame(
        {
            "ein": ["1", "1", "1"],
            "ccn": ["000001", "000002", "000003"],
            "tax_period_end": [pd.Timestamp("2023-06-30")] * 3,
        }
    )
    reports = pd.DataFrame(
        [
            # CCN 1: the earlier report has the better status (settled with audit).
            _report("000001", "2022-12-31", 1.0, rpt_rec_num=10, rpt_stus_cd=3),
            _report("000001", "2023-12-31", 1.0, rpt_rec_num=11, rpt_stus_cd=1),
            # CCN 2: the later report has the better status.
            _report("000002", "2022-12-31", 1.0, rpt_rec_num=20, rpt_stus_cd=1),
            _report("000002", "2023-12-31", 1.0, rpt_rec_num=21, rpt_stus_cd=3),
            # CCN 3: only a later report exists, so "after" has more CCNs behind it.
            _report("000003", "2023-12-31", 1.0, rpt_rec_num=31, rpt_stus_cd=1),
        ]
    )
    chosen = select_period_matched_reports(reports, targets).set_index("ccn")
    assert chosen["rpt_rec_num"].to_dict() == {"000001": 11, "000002": 21, "000003": 31}
    assert chosen["fy_end_dt"].nunique() == 1
    assert (chosen["months_from_990"] == 6).all()

    # With the vote level (drop CCN 3), the side holding the best status wins; both
    # sides hold a settled-with-audit report here, so the later side is taken.
    two = select_period_matched_reports(reports, targets.iloc[:2]).set_index("ccn")
    assert two["rpt_rec_num"].to_dict() == {"000001": 11, "000002": 21}
    # ...and when only one side holds the better status, that side wins for both.
    earlier_better = reports[reports["rpt_rec_num"] != 21]
    earlier_better = pd.concat(
        [earlier_better, pd.DataFrame([_report("000002", "2023-12-31", 1.0, rpt_rec_num=22)])]
    )
    got = select_period_matched_reports(earlier_better, targets.iloc[:2]).set_index("ccn")
    assert got["rpt_rec_num"].to_dict() == {"000001": 10, "000002": 20}

    # A closer report always beats the side preference.
    closer = pd.concat(
        [reports, pd.DataFrame([_report("000001", "2023-06-30", 1.0, rpt_rec_num=12)])]
    )
    got = select_period_matched_reports(closer, targets).set_index("ccn")
    assert got.loc["000001", "rpt_rec_num"] == 12
    assert got.loc["000002", "rpt_rec_num"] == 21

    # Different EINs decide independently.
    other = targets.iloc[:1].assign(ein="2")
    both = select_period_matched_reports(reports, pd.concat([targets, other]))
    assert both.set_index(["ein", "ccn"]).loc[("2", "000001"), "rpt_rec_num"] == 10
    assert both.set_index(["ein", "ccn"]).loc[("1", "000001"), "rpt_rec_num"] == 11


def test_ccn_count_is_ccns_with_a_cost_report_and_crosswalk_count_is_published() -> None:
    """The crosswalk can list CCNs that have no cost report in the files (retired
    or merged numbers). ``ccn_count`` counts reports found; the crosswalk count
    is published beside it so "single facility" is not overstated."""
    out = _gap(
        [_report("000001", "2022-12-31", 5_000_000.0)],
        [_sched("111111111", "2022-12-31", 4_000_000.0)],
        _cw(("000001", "111111111"), ("000009", "111111111")),
    )
    row = out.loc["111111111"]
    assert row["ccn_count"] == 1
    assert row["crosswalk_ccn_count"] == 2
    assert row["ccn_list"] == "000001"


def test_return_of_record_rule_has_a_single_implementation() -> None:
    import analytics.community_benefit as cb
    import form990.parse as fp

    assert cb.latest_return_per_ein is fp.latest_return_per_ein
    assert cb.FULL_YEAR_MIN_DAYS == fp.FULL_YEAR_MIN_DAYS


# ----------------------------------------------------------------- components


def test_publishes_components_and_gross_gap() -> None:
    """The Yale New Haven anchor, as synthetic input: every component passes through."""
    out = _gap(
        [
            _report(
                "070022",
                "2023-09-30",
                35_568_680.0,
                uninsured=30_287_094.0,
                insured=5_281_586.0,
                line5=-71_469_000.0,
                rpt_rec_num=827192,
            )
        ],
        [
            _sched(
                "060646652",
                "2023-09-30",
                113_100_512.0,
                gross=257_262_512.0,
                offset=144_162_000.0,
                object_id="202422269349301652",
            )
        ],
        _cw(("070022", "060646652")),
    )
    row = out.loc["060646652"]
    assert row["sched_h_financial_assistance_gross"] == 257_262_512.0
    assert row["sched_h_financial_assistance_offset_revenue"] == 144_162_000.0
    assert row["sched_h_financial_assistance_at_cost"] == 113_100_512.0
    assert row["hcris_charity_care_cost_uninsured"] == 30_287_094.0
    assert row["hcris_charity_care_cost_insured"] == 5_281_586.0
    assert row["hcris_medicaid_dsh_supplemental"] == -71_469_000.0
    assert row["charity_gap"] == 35_568_680.0 - 113_100_512.0
    assert row["charity_gap_gross"] == 35_568_680.0 - 257_262_512.0
    assert bool(row["sched_h_fa_7a_consistent"]) is True
    assert row["sched_h_object_id"] == "202422269349301652"
    assert row["ccn_list"] == "070022"
    assert (row["city"], row["state"]) == ("Town", "CT")
    assert row["hcris_report_status"] == "as_submitted"


def test_flags_returns_whose_7a_arithmetic_does_not_hold() -> None:
    out = _gap(
        [_report("000001", "2023-08-31", 24_454_147.0), _report("000002", "2023-08-31", 1.0)],
        [
            # (c) - (d) = 13.8M, but (e) says 4.5M.
            _sched("111111111", "2023-08-31", 4_523_276.0, gross=35_917_454.0, offset=22_140_678.0),
            # No gross column at all: not checkable, so NA rather than True.
            _sched("222222222", "2023-08-31", 5.0),
        ],
        _cw(("000001", "111111111"), ("000002", "222222222")),
    )
    assert bool(out.loc["111111111", "sched_h_fa_7a_consistent"]) is False
    assert pd.isna(out.loc["222222222", "sched_h_fa_7a_consistent"])
