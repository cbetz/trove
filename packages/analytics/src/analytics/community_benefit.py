"""Compare hospital community benefit on HCRIS Worksheet S-10 vs. IRS Form 990 Schedule H."""

from __future__ import annotations

import pandas as pd


def community_benefit_gap(
    hcris_wide: pd.DataFrame,
    schedule_h: pd.DataFrame,
    crosswalk: pd.DataFrame,
) -> pd.DataFrame:
    """Per nonprofit hospital system (one row per EIN) compare HCRIS to 990 Schedule H.

    HCRIS reports per-facility (CCN). 990s are filed per parent organization (EIN).
    A single EIN often covers multiple CCNs, so HCRIS facility-level numbers are
    summed across all CCNs sharing an EIN before comparing.

    Returns a DataFrame ranked by absolute charity-care gap (HCRIS minus 990) so
    the largest discrepancies surface at the top. Columns:

    - ``ein``, ``ccn_count``, ``hospital_name`` (lead facility)
    - ``hcris_charity_care_cost`` — summed across the system's CCNs
    - ``hcris_uncompensated_care_cost``
    - ``hcris_total_operating_expenses``
    - ``sched_h_financial_assistance_at_cost``
    - ``sched_h_total_community_benefit``
    - ``sched_h_total_expenses``
    - ``charity_gap`` — HCRIS charity care minus Schedule H 7a financial assistance
    - ``community_benefit_pct_of_expenses`` — Schedule H total community benefit
      divided by HCRIS total operating expenses (sanity check on the 7k ratio)
    """
    cw = crosswalk[["ccn", "ein"]].dropna()

    by_system = (
        hcris_wide.merge(cw, left_on="prvdr_num", right_on="ccn", how="inner")
        .groupby("ein", as_index=False)
        .agg(
            ccn_count=("ccn", "nunique"),
            hospital_name=("hospital_name", "first"),
            hcris_charity_care_cost=("charity_care_cost", "sum"),
            hcris_uncompensated_care_cost=("uncompensated_care_cost", "sum"),
            hcris_total_operating_expenses=("total_operating_expenses", "sum"),
        )
    )

    # When a 990 has been amended, the same EIN appears in multiple release-year
    # ingests with the same tax_period_end. Prefer the newest release_year, then
    # newest tax_period_end. release_year may be missing if the caller ran
    # parse_zip directly — fall back to tax_period_end-only ordering.
    sort_keys = ["tax_period_end"]
    if "release_year" in schedule_h.columns:
        sort_keys = ["release_year", "tax_period_end"]
    sched_latest = (
        schedule_h.sort_values(sort_keys, ascending=False)
        .drop_duplicates(subset=["ein"], keep="first")[
            [
                "ein",
                "organization_name",
                "tax_period_end",
                "financial_assistance_at_cost",
                "total_community_benefit",
                "total_expenses",
            ]
        ]
        .rename(
            columns={
                "organization_name": "sched_h_organization_name",
                "tax_period_end": "sched_h_tax_period_end",
                "financial_assistance_at_cost": "sched_h_financial_assistance_at_cost",
                "total_community_benefit": "sched_h_total_community_benefit",
                "total_expenses": "sched_h_total_expenses",
            }
        )
    )

    joined = by_system.merge(sched_latest, on="ein", how="inner")
    joined["charity_gap"] = (
        joined["hcris_charity_care_cost"] - joined["sched_h_financial_assistance_at_cost"]
    )
    joined["community_benefit_pct_of_expenses"] = (
        joined["sched_h_total_community_benefit"] / joined["hcris_total_operating_expenses"]
    )

    return joined.sort_values("charity_gap", ascending=False, key=lambda s: s.abs())
