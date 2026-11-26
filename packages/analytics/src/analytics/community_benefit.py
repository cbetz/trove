"""Compare hospital community benefit on HCRIS Worksheet S-10 vs. IRS Form 990 Schedule H."""

from __future__ import annotations

import pandas as pd

# The return-of-record rule lives in one place (form990.parse) and is re-exported
# here, so the parser and the comparison can never drift apart.
from form990.parse import FULL_YEAR_MIN_DAYS, latest_return_per_ein

ALIGNMENT_MONTHS: int = 1

__all__ = [
    "ALIGNMENT_MONTHS",
    "FULL_YEAR_MIN_DAYS",
    "community_benefit_gap",
    "latest_return_per_ein",
    "months_apart",
    "select_period_matched_reports",
]

# rpt_stus_cd, most authoritative first: reopened (4), settled with audit (3),
# settled without audit (2), amended (5), as submitted (1). HCRIS normally keeps
# a single report per provider and period, so this only breaks rare ties.
_STATUS_RANK: dict[int, int] = {4: 0, 3: 1, 2: 2, 5: 3, 1: 4}

_SDOH_COLS: tuple[str, ...] = (
    "adi_natrank",
    "adi_state_decile",
    "svi_overall_pct",
    "svi_socio_pct",
    "svi_household_pct",
    "svi_minority_pct",
    "svi_housing_pct",
)

# HCRIS wide column -> output column, summed across a system's CCNs. A missing
# value on one CCN is treated as "nothing reported on that line" for these
# (CMS never stores zeros, and most of these lines are legitimately empty for
# most hospitals); the total is missing only when every CCN is missing.
_HCRIS_SUMS: dict[str, str] = {
    "uncompensated_care_cost": "hcris_uncompensated_care_cost",
    "total_operating_expenses": "hcris_total_operating_expenses",
    "charity_care_cost_uninsured": "hcris_charity_care_cost_uninsured",
    "charity_care_cost_insured": "hcris_charity_care_cost_insured",
    "charity_care_initial_charges": "hcris_charity_care_charges",
    "charity_care_cost_before_payments": "hcris_charity_care_cost_before_payments",
    "charity_care_partial_payments": "hcris_charity_care_partial_payments",
    "medicaid_dsh_supplemental_payments": "hcris_medicaid_dsh_supplemental",
    "medicaid_shortfall": "hcris_medicaid_shortfall",
}

# Schedule H column -> output column (all optional except the first block).
_SCHED_H_RENAMES: dict[str, str] = {
    "organization_name": "sched_h_organization_name",
    "tax_period_begin": "sched_h_tax_period_begin",
    "tax_period_end": "sched_h_tax_period_end",
    "financial_assistance_at_cost": "sched_h_financial_assistance_at_cost",
    "financial_assistance_at_cost_gross": "sched_h_financial_assistance_gross",
    "financial_assistance_at_cost_offset_revenue": "sched_h_financial_assistance_offset_revenue",
    "unreimbursed_medicaid": "sched_h_unreimbursed_medicaid",
    "unreimbursed_medicaid_gross": "sched_h_unreimbursed_medicaid_gross",
    "unreimbursed_medicaid_offset_revenue": "sched_h_unreimbursed_medicaid_offset_revenue",
    "total_community_benefit": "sched_h_total_community_benefit",
    "total_expenses": "sched_h_total_expenses",
    "object_id": "sched_h_object_id",
    "release_year": "sched_h_release_year",
    "amended_return": "sched_h_amended_return",
}


def months_apart(a: pd.Series, b: pd.Series) -> pd.Series:
    """Whole calendar months between two date series (year*12+month difference), unsigned.

    The same arithmetic the ranked index has always used: 2023-06-30 vs 2023-07-01
    is 1 month apart, 2023-06-01 vs 2023-06-30 is 0. Missing dates give ``<NA>``.
    """
    a = pd.to_datetime(a)
    b = pd.to_datetime(b)
    diff = (a.dt.year - b.dt.year) * 12 + (a.dt.month - b.dt.month)
    return diff.abs().astype("Int64")


def select_period_matched_reports(
    hcris_wide: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    """Pick, for every (EIN, CCN) pair, the one cost report closest to the 990's period.

    ``hcris_wide`` may hold several cost reports per CCN (several HCRIS fiscal-year
    files concatenated — CMS files a report under the federal fiscal year in which
    its period BEGINS, so a TY2022 990 can pair with a report in either the FY2022
    or the FY2023 file). ``targets`` has one row per (``ein``, ``ccn``) with the
    990's ``tax_period_end``.

    For each pair the report whose ``fy_end_dt`` is the fewest calendar months
    from ``tax_period_end`` wins.

    **Exact ties in distance.** A report ending N months before the 990 and one
    ending N months after are equally close (in practice N = 6: a calendar-year
    cost report against a June year-end 990). The side is decided once per EIN,
    not per CCN, so a system's facilities never take reports from different
    years: the side on which more of the EIN's CCNs have a closest report wins,
    then the side holding the more authoritative report status, then the later
    one. Only after that do report status (reopened > settled with audit >
    settled > amended > as submitted) and the most recent processing date break
    what is left — duplicate reports for the same period.

    Returns the chosen rows of ``hcris_wide`` plus ``ein``, ``ccn`` and
    ``months_from_990``. When ``hcris_wide`` has no ``fy_end_dt`` the first
    report per CCN is taken and ``months_from_990`` is NA.
    """
    cand = targets[["ein", "ccn", "tax_period_end"]].merge(
        hcris_wide, left_on="ccn", right_on="prvdr_num", how="inner"
    )
    if "rpt_stus_cd" in cand.columns:
        cand["_status_rank"] = cand["rpt_stus_cd"].map(_STATUS_RANK).fillna(len(_STATUS_RANK))
    else:
        cand["_status_rank"] = 0
    if "fy_end_dt" in cand.columns:
        cand["months_from_990"] = months_apart(cand["fy_end_dt"], cand["tax_period_end"])
        cand["_off_side"] = _off_preferred_side(cand)
    else:
        cand["months_from_990"] = pd.Series(pd.NA, index=cand.index, dtype="Int64")
        cand["_off_side"] = 0
    sort_cols = ["ein", "ccn", "months_from_990", "_off_side", "_status_rank"]
    ascending = [True, True, True, True, True]
    for col in ("proc_dt", "rpt_rec_num"):
        if col in cand.columns:
            sort_cols.append(col)
            ascending.append(False)
    cand = cand.sort_values(sort_cols, ascending=ascending, na_position="last", kind="stable")
    chosen = cand.drop_duplicates(subset=["ein", "ccn"], keep="first")
    return chosen.drop(columns=["_status_rank", "_off_side", "tax_period_end"], errors="ignore")


def _off_preferred_side(cand: pd.DataFrame) -> pd.Series:
    """0 where a candidate report is on its EIN's preferred side of the 990, else 1.

    "Side" is whether the report ends before (-1), in the same month as (0), or
    after (+1) the 990's tax period. See ``select_period_matched_reports`` for
    how the preferred side is chosen; same-month candidates are never off-side.
    """
    end = pd.to_datetime(cand["fy_end_dt"])
    tax = pd.to_datetime(cand["tax_period_end"])
    signed = (end.dt.year - tax.dt.year) * 12 + (end.dt.month - tax.dt.month)
    side = signed.fillna(0).clip(-1, 1).astype(int)
    best = cand.groupby(["ein", "ccn"])["months_from_990"].transform("min")
    closest = cand.assign(_side=side)[(cand["months_from_990"] == best).fillna(False) & (side != 0)]
    if closest.empty:
        return pd.Series(0, index=cand.index)
    votes = (
        closest.groupby(["ein", "_side"])
        .agg(_ccns=("ccn", "nunique"), _rank=("_status_rank", "min"))
        .reset_index()
        .sort_values(["ein", "_ccns", "_rank", "_side"], ascending=[True, False, True, False])
        .drop_duplicates("ein", keep="first")
        .set_index("ein")["_side"]
    )
    preferred = cand["ein"].map(votes)
    return ((side != 0) & preferred.notna() & (side != preferred)).astype(int)


def community_benefit_gap(
    hcris_wide: pd.DataFrame,
    schedule_h: pd.DataFrame,
    crosswalk: pd.DataFrame,
    *,
    alignment_months: int = ALIGNMENT_MONTHS,
) -> pd.DataFrame:
    """Per nonprofit hospital system (one row per EIN) compare HCRIS to 990 Schedule H.

    HCRIS reports per-facility (CCN). 990s are filed per parent organization (EIN).
    A single EIN often covers multiple CCNs, so HCRIS facility-level numbers are
    summed across all CCNs sharing an EIN before comparing.

    **Period matching.** For each CCN the cost report whose period END is closest
    to the 990's tax-period end is used (see ``select_period_matched_reports``).
    ``period_aligned`` is True only when EVERY CCN under the EIN has a report
    ending within ``alignment_months`` of the 990; ``hcris_fy_end_dt`` /
    ``hcris_fy_bgn_dt`` are the dates of the worst-matching CCN's report, so a
    date comparison on the published row agrees with ``period_aligned``.

    **Missing stays missing.** CMS's numeric file never stores a zero, so an
    absent S-10 cell is "blank or zero", not a reported $0. Sums use
    ``min_count=1``; ``hcris_charity_care_cost`` is stricter — missing when ANY
    CCN lacks line 23 column 3, since a partial total would understate the
    system. ``charity_gap`` and ``charity_gap_gross`` are missing whenever either
    side is. ``hcris_s10_filed`` says whether every CCN filed a Worksheet S-10.

    Returns a DataFrame ranked by absolute charity-care gap. Columns:

    - identity: ``ein``, ``ccn_count`` (CCNs with a cost report in ``hcris_wide``),
      ``crosswalk_ccn_count`` (CCNs the crosswalk lists for the EIN), ``ccn_list``
      (";"-joined, lead facility first), ``hospital_name`` / ``city`` / ``state``
      (lead facility — the CCN with the largest operating expenses)
    - HCRIS, summed across CCNs: ``hcris_charity_care_cost`` (S-10 line 23 col 3),
      ``hcris_ccns_missing_charity`` (how many CCNs have no line 23 col 3) and
      ``hcris_charity_care_cost_reporting_ccns`` (the partial total over the CCNs
      that do — equal to ``hcris_charity_care_cost`` when none are missing),
      ``hcris_charity_care_cost_uninsured`` / ``_insured`` (cols 1 / 2),
      ``hcris_charity_care_charges`` (line 20 col 3),
      ``hcris_charity_care_cost_before_payments`` (line 21 col 3),
      ``hcris_charity_care_partial_payments`` (line 22 col 3),
      ``hcris_medicaid_dsh_supplemental`` (line 5; can be negative),
      ``hcris_medicaid_shortfall`` (line 8), ``hcris_uncompensated_care_cost``
      (line 30), ``hcris_total_operating_expenses`` (G-3 line 4)
    - HCRIS report: ``hcris_fy_bgn_dt``, ``hcris_fy_end_dt``,
      ``hcris_report_status``, ``hcris_rpt_rec_num`` (";"-joined, ``ccn_list``
      order), ``hcris_months_from_990``, ``period_aligned``, ``hcris_s10_filed``
    - Schedule H: ``sched_h_organization_name``, ``sched_h_tax_period_begin`` /
      ``_end``, line 7a ``sched_h_financial_assistance_gross`` (col c),
      ``sched_h_financial_assistance_offset_revenue`` (col d),
      ``sched_h_financial_assistance_at_cost`` (col e); line 7b
      ``sched_h_unreimbursed_medicaid`` (+ ``_gross``, ``_offset_revenue``);
      ``sched_h_total_community_benefit`` (7k col e), ``sched_h_total_expenses``,
      ``sched_h_object_id``, ``sched_h_release_year``, ``sched_h_amended_return``
    - ``charity_gap`` — S-10 line 23 col 3 minus Schedule H 7a col (e) (net basis)
    - ``charity_gap_gross`` — S-10 line 23 col 3 minus Schedule H 7a col (c)
    - ``sched_h_fa_offset_pct_of_gross`` — 7a col (d) as a percentage of col (c)
    - ``sched_h_fa_7a_consistent`` — whether the return's own 7a arithmetic holds,
      (c) - (d) = (e) within $1 (NA when (c) or (e) is blank)
    - ``community_benefit_pct_of_expenses`` — Schedule H total community benefit as a
      percentage (0-100) of Schedule H total expenses. Same-form denominator, so this
      is the standard internally-consistent "community benefit as a share of expenses"
      measure and it is the one to quote.
    - ``community_benefit_pct_of_hcris_expenses`` — the same numerator over HCRIS total
      operating expenses (0-100). Cross-form, so it inherits every scope difference
      between the two filings. Both are NaN rather than ``inf`` when the denominator
      is 0 or missing.

    Columns whose inputs are absent from the frames passed in are simply omitted.
    """
    sched = latest_return_per_ein(schedule_h)
    sched = sched[[c for c in _SCHED_H_RENAMES if c in sched.columns] + ["ein"]]

    cw_cols = ["ccn", "ein"] + [c for c in ("city", "state", *_SDOH_COLS) if c in crosswalk.columns]
    cw = crosswalk[cw_cols].dropna(subset=["ccn", "ein"]).drop_duplicates(["ccn", "ein"])

    targets = cw[["ccn", "ein"]].merge(sched[["ein", "tax_period_end"]], on="ein", how="inner")
    chosen = select_period_matched_reports(hcris_wide, targets)
    chosen = chosen.merge(cw, on=["ccn", "ein"], how="left")

    # Lead facility first within each EIN: the CCN with the largest operating
    # expenses names the row and supplies its city/state.
    chosen = chosen.sort_values(
        ["ein", "total_operating_expenses", "ccn"],
        ascending=[True, False, True],
        na_position="last",
        kind="stable",
    )
    grouped = chosen.groupby("ein", sort=False)

    by_system = grouped.agg(
        ccn_count=("ccn", "nunique"),
        ccn_list=("ccn", ";".join),
        hospital_name=("hospital_name", "first"),
    )
    for col in ("city", "state"):
        if col in chosen.columns:
            by_system[col] = grouped[col].first()

    # Headline S-10 figure: all-or-nothing across CCNs.
    by_system["hcris_charity_care_cost"] = grouped["charity_care_cost"].sum(min_count=1)
    any_missing = chosen["charity_care_cost"].isna().groupby(chosen["ein"], sort=False).any()
    by_system["hcris_charity_care_cost_reporting_ccns"] = by_system["hcris_charity_care_cost"]
    by_system.loc[any_missing[any_missing].index, "hcris_charity_care_cost"] = float("nan")
    by_system["hcris_ccns_missing_charity"] = (
        chosen["charity_care_cost"].isna().groupby(chosen["ein"], sort=False).sum().astype("int64")
    )

    for src, out in _HCRIS_SUMS.items():
        if src in chosen.columns:
            by_system[out] = grouped[src].sum(min_count=1)

    if "fy_end_dt" in chosen.columns:
        # Dates of the worst-matching CCN, so the published dates tell the truth
        # about a multi-CCN row; fall back to the latest end when unmatched.
        worst = chosen.sort_values(
            ["ein", "months_from_990", "fy_end_dt"],
            ascending=[True, False, False],
            na_position="last",
            kind="stable",
        ).drop_duplicates("ein", keep="first")
        worst = worst.set_index("ein")
        by_system["hcris_fy_end_dt"] = worst["fy_end_dt"]
        if "fy_bgn_dt" in chosen.columns:
            by_system["hcris_fy_bgn_dt"] = worst["fy_bgn_dt"]
        by_system["hcris_months_from_990"] = grouped["months_from_990"].max()
        by_system["period_aligned"] = (
            (chosen["months_from_990"] <= alignment_months)
            .fillna(False)
            .astype(bool)
            .groupby(chosen["ein"], sort=False)
            .all()
        )
    if "rpt_status" in chosen.columns:
        by_system["hcris_report_status"] = grouped["rpt_status"].agg(
            lambda s: ";".join(dict.fromkeys(s.dropna().astype(str)))
        )
    if "rpt_rec_num" in chosen.columns:
        by_system["hcris_rpt_rec_num"] = grouped["rpt_rec_num"].agg(
            lambda s: ";".join(str(int(v)) for v in s)
        )
    if "s10_filed" in chosen.columns:
        by_system["hcris_s10_filed"] = grouped["s10_filed"].all()
    for sdoh_col in _SDOH_COLS:
        if sdoh_col in chosen.columns:
            by_system[sdoh_col] = grouped[sdoh_col].median()

    by_system["crosswalk_ccn_count"] = cw.groupby("ein")["ccn"].nunique()
    by_system = by_system.reset_index()
    joined = by_system.merge(sched.rename(columns=_SCHED_H_RENAMES), on="ein", how="inner")

    joined["charity_gap"] = (
        joined["hcris_charity_care_cost"] - joined["sched_h_financial_assistance_at_cost"]
    )
    if "sched_h_financial_assistance_gross" in joined.columns:
        gross = joined["sched_h_financial_assistance_gross"]
        joined["charity_gap_gross"] = joined["hcris_charity_care_cost"] - gross
        if "sched_h_financial_assistance_offset_revenue" in joined.columns:
            joined["sched_h_fa_offset_pct_of_gross"] = (
                joined["sched_h_financial_assistance_offset_revenue"]
                / gross.where(gross != 0)
                * 100
            )
            # Form arithmetic: (e) should equal (c) - (d), with a blank (d) read as 0.
            # NA when (c) or (e) is blank, so "not checkable" is not "consistent".
            offset = joined["sched_h_financial_assistance_offset_revenue"].fillna(0)
            residual = gross - offset - joined["sched_h_financial_assistance_at_cost"]
            joined["sched_h_fa_7a_consistent"] = (
                (residual.abs() <= 1).where(residual.notna()).astype("boolean")
            )
    # Percent, not a fraction, to match the column name and the SVI ``_pct`` columns.
    # Zero denominators become NaN so the ratio is missing rather than ``inf``.
    sched_denom = joined["sched_h_total_expenses"]
    hcris_denom = joined["hcris_total_operating_expenses"]
    joined["community_benefit_pct_of_expenses"] = (
        joined["sched_h_total_community_benefit"] / sched_denom.where(sched_denom != 0) * 100
    )
    joined["community_benefit_pct_of_hcris_expenses"] = (
        joined["sched_h_total_community_benefit"] / hcris_denom.where(hcris_denom != 0) * 100
    )

    return joined.sort_values(
        "charity_gap", ascending=False, key=lambda s: s.abs(), na_position="last"
    ).reset_index(drop=True)
