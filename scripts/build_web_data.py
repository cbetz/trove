"""Derive the JSON bundle that powers troveproject.com from the published CSV.

Reads ``artifacts/community_benefit_gap_2022.csv`` (the committed, GitHub-viewable
artifact produced by ``build_gap_dataset.py``) and writes a compact JSON to
``web/data/community_benefit_gap_2022.json`` for the static site to fetch.

``rows`` holds the computable systems (both figures present), exactly as in
earlier versions, so a reader that assumes ``gap`` is a number keeps working.
``rows_not_computable`` holds the other matched systems in the same row shape:
they carry ``null`` for the missing figure and for ``gap`` / ``gap_pct`` /
``gap_gross`` — a null is a line with no value on the form, never a reported $0
(earlier versions published a missing S-10 as 0 and listed those systems in
``rows``). Search both arrays to find every matched system.
``totals`` describes the funnel; its keys are unchanged from earlier versions.

Usage: ``uv run python scripts/build_web_data.py``
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

CSV_IN = Path("artifacts/community_benefit_gap_2022.csv")
JSON_OUT = Path("web/data/community_benefit_gap_2022.json")
TAX_YEAR = 2022
MATERIAL_FLOOR = 500_000
# Leading zeros (EIN, CCN) and 18-digit ids must not be parsed as numbers.
STRING_COLUMNS = ("ein", "ccn_list", "sched_h_object_id", "hcris_rpt_rec_num")
DATE_COLUMNS = (
    "hcris_fy_bgn_dt",
    "hcris_fy_end_dt",
    "sched_h_tax_period_begin",
    "sched_h_tax_period_end",
)


def main() -> None:
    raw = pd.read_csv(
        CSV_IN,
        dtype={c: str for c in STRING_COLUMNS},
        parse_dates=list(DATE_COLUMNS),
    )
    matched_count = len(raw)

    # Computable = both 7a (990) and S-10 (HCRIS) are present so charity_gap is defined.
    raw["computable"] = (
        raw["hcris_charity_care_cost"].notna() & raw["sched_h_financial_assistance_at_cost"].notna()
    )
    comp = raw[raw["computable"]]
    computable_count = len(comp)

    # ``period_aligned`` comes from the gap build: every CCN under the EIN has a
    # cost report ending within one calendar month of the 990's tax period.
    aligned = comp[comp["period_aligned"]]
    aligned_count = len(aligned)
    # On the value, not its absolute size: a negative 7a (e) is not ">= $500K".
    aligned_material = aligned[
        (aligned["hcris_charity_care_cost"] >= MATERIAL_FLOOR)
        & (aligned["sched_h_financial_assistance_at_cost"] >= MATERIAL_FLOOR)
    ]
    aligned_material_count = len(aligned_material)

    df = raw.copy()
    df["gap_pct"] = _gap_pct(df)
    # Sort alphabetically by system name so search results aren't implicitly
    # ranked by gap size — this is a lookup tool, not a leaderboard.
    df = df.sort_values(["sched_h_organization_name", "ein"], na_position="last")

    all_rows = [
        {
            "ein": r.ein,
            "system": r.sched_h_organization_name,
            "facility": r.hospital_name,
            # CCNs under the EIN with a cost report in the HCRIS files used; see
            # crosswalk_ccns (below) for how many the crosswalk lists.
            "ccns": int(r.ccn_count),
            "period_end": (
                r.sched_h_tax_period_end.strftime("%Y-%m-%d")
                if pd.notna(r.sched_h_tax_period_end)
                else None
            ),
            "hcris_fy_end": (
                r.hcris_fy_end_dt.strftime("%Y-%m-%d") if pd.notna(r.hcris_fy_end_dt) else None
            ),
            "hcris_charity": _num(r.hcris_charity_care_cost),
            "hcris_uncomp": _num(r.hcris_uncompensated_care_cost),
            "hcris_opex": _num(r.hcris_total_operating_expenses),
            "fa_990": _num(r.sched_h_financial_assistance_at_cost),
            "cb_990": _num(r.sched_h_total_community_benefit),
            "exp_990": _num(r.sched_h_total_expenses),
            "gap": _num(r.charity_gap),
            "gap_pct": _num(r.gap_pct, decimals=4),
            # Percent (0-100) of the same form's total expenses, not a fraction.
            "cb_pct": _num(r.community_benefit_pct_of_expenses, decimals=1),
            "svi_overall_pct": _num(getattr(r, "svi_overall_pct", None), decimals=1),
            "svi_socio_pct": _num(getattr(r, "svi_socio_pct", None), decimals=1),
            "svi_household_pct": _num(getattr(r, "svi_household_pct", None), decimals=1),
            "svi_minority_pct": _num(getattr(r, "svi_minority_pct", None), decimals=1),
            "svi_housing_pct": _num(getattr(r, "svi_housing_pct", None), decimals=1),
            # --- added with the FY2022+FY2023 / releases 2023-2026 rebuild ---
            "computable": bool(r.computable),
            "aligned": bool(r.period_aligned),
            "city": _str(r.city),
            "state": _str(r.state),
            "ccn_list": r.ccn_list.split(";") if isinstance(r.ccn_list, str) else [],
            "ccns_missing_s10_charity": int(r.hcris_ccns_missing_charity),
            # S-10 line 23 col 3 over the CCNs that report it; equals hcris_charity
            # unless some CCNs are missing, in which case hcris_charity is null.
            "hcris_charity_reporting_ccns": _num(r.hcris_charity_care_cost_reporting_ccns),
            "s10_filed": bool(r.hcris_s10_filed),
            "hcris_fy_begin": _date(r.hcris_fy_bgn_dt),
            "hcris_status": _str(r.hcris_report_status),
            # S-10 line 23 cols 1 / 2 (hcris_charity is col 3) and line 5.
            "hcris_charity_uninsured": _num(r.hcris_charity_care_cost_uninsured),
            "hcris_charity_insured": _num(r.hcris_charity_care_cost_insured),
            "hcris_dsh_supplemental": _num(r.hcris_medicaid_dsh_supplemental),
            # Schedule H line 7a cols (c) / (d) (fa_990 is col (e)); line 7b (c)/(d)/(e).
            "period_begin": _date(r.sched_h_tax_period_begin),
            "fa_990_gross": _num(r.sched_h_financial_assistance_gross),
            "fa_990_offset": _num(r.sched_h_financial_assistance_offset_revenue),
            "medicaid_990_gross": _num(r.sched_h_unreimbursed_medicaid_gross),
            "medicaid_990_offset": _num(r.sched_h_unreimbursed_medicaid_offset_revenue),
            "medicaid_990": _num(r.sched_h_unreimbursed_medicaid),
            # hcris_charity - fa_990_gross.
            "gap_gross": _num(r.charity_gap_gross),
            # Whether the return's own 7a arithmetic holds; null when not checkable.
            "fa_990_consistent": None
            if pd.isna(r.sched_h_fa_7a_consistent)
            else bool(r.sched_h_fa_7a_consistent),
            "object_id": _str(r.sched_h_object_id),
            "release_year": _num(r.sched_h_release_year),
            # CCNs the crosswalk lists for the EIN; can exceed "ccns" when a listed
            # CCN has no cost report in the HCRIS files used.
            "crosswalk_ccns": _num(r.crosswalk_ccn_count),
            "amended_990": None
            if pd.isna(r.sched_h_amended_return)
            else bool(r.sched_h_amended_return),
        }
        for r in df.itertuples(index=False)
    ]

    median_aligned_pct = (
        float(_gap_pct(aligned_material).abs().median()) if len(aligned_material) else 0
    )
    big_gaps = int((_gap_pct(aligned_material).abs() >= 0.5).sum())
    totals = {
        "s10_charity_missing": int(raw["hcris_charity_care_cost"].isna().sum()),
        "fa_990_missing": int(raw["sched_h_financial_assistance_at_cost"].isna().sum()),
        "matched": matched_count,
        "computable": computable_count,
        "aligned": aligned_count,
        "aligned_material": aligned_material_count,
        "matched_minus_computable": matched_count - computable_count,
        "aligned_minus_material": aligned_count - aligned_material_count,
        "median_aligned_material_gap_pct": round(median_aligned_pct, 4),
        "aligned_material_big_gaps": big_gaps,
        "absolute_gap_usd_aligned_material": _num(aligned_material["charity_gap"].abs().sum()),
        "total_cb_usd_aligned_material": _num(
            aligned_material["sched_h_total_community_benefit"].sum()
        ),
    }

    rows = [r for r in all_rows if r["computable"]]
    rows_not_computable = [r for r in all_rows if not r["computable"]]
    bundle = {
        "tax_year": TAX_YEAR,
        "totals": totals,
        "rows": rows,
        "rows_not_computable": rows_not_computable,
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(bundle, separators=(",", ":")) + "\n")
    size_kb = JSON_OUT.stat().st_size / 1024
    print(
        f"  → {JSON_OUT} ({len(rows):,} computable rows + "
        f"{len(rows_not_computable):,} not computable, {size_kb:.1f} KB)"
    )


def _str(v: object) -> str | None:
    return None if pd.isna(v) else str(v)


def _date(v: object) -> str | None:
    return None if pd.isna(v) else pd.Timestamp(v).strftime("%Y-%m-%d")


def _num(v: float, decimals: int = 0) -> float | int | None:
    if pd.isna(v):
        return None
    f = float(v)
    if not math.isfinite(f):
        return None
    return round(f, decimals) if decimals else int(round(f))


def _gap_pct(df: pd.DataFrame) -> pd.Series:
    """Gap as a fraction of the larger of the two reported numbers.

    0 = identical reporting. 1 = one of the two is zero. Sign matches the
    sign of charity_gap (positive = HCRIS larger, negative = 990 larger).
    Missing when either figure is missing — a missing side is not a zero.
    """
    h = df["hcris_charity_care_cost"].abs()
    f = df["sched_h_financial_assistance_at_cost"].abs()
    denom = pd.concat([h, f], axis=1).max(axis=1)
    pct = df["charity_gap"] / denom
    return pct.where((denom > 0) | df["charity_gap"].isna(), 0)


if __name__ == "__main__":
    main()
