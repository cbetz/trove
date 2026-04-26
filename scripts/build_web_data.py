"""Derive the JSON bundle that powers troveproject.com from the published CSV.

Reads ``artifacts/community_benefit_gap_2022.csv`` (the committed, GitHub-viewable
artifact produced by ``build_gap_dataset.py``) and writes a compact JSON to
``web/data/community_benefit_gap_2022.json`` for the static site to fetch.

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


def main() -> None:
    raw = pd.read_csv(CSV_IN, dtype={"ein": str}, parse_dates=["hcris_fy_end_dt", "sched_h_tax_period_end"])
    matched_count = len(raw)

    # Computable = both 7a (990) and S-10 (HCRIS) are present so charity_gap is defined.
    df = raw[
        raw["hcris_charity_care_cost"].notna()
        & raw["sched_h_financial_assistance_at_cost"].notna()
    ].copy()
    computable_count = len(df)

    df["months_apart"] = (
        (df["hcris_fy_end_dt"] - df["sched_h_tax_period_end"]).abs().dt.days / 30.44
    ).round()
    aligned_count = int((df["months_apart"] <= 1).sum())
    aligned_material = df[
        (df["months_apart"] <= 1)
        & (df["hcris_charity_care_cost"].abs() >= 500_000)
        & (df["sched_h_financial_assistance_at_cost"].abs() >= 500_000)
    ]
    aligned_material_count = len(aligned_material)

    df["gap_pct"] = _gap_pct(df)
    df = df.sort_values("gap_pct", ascending=False, key=lambda s: s.abs())

    rows = [
        {
            "ein": r.ein,
            "system": r.sched_h_organization_name,
            "facility": r.hospital_name,
            "ccns": int(r.ccn_count),
            "period_end": r.sched_h_tax_period_end.strftime("%Y-%m-%d") if pd.notna(r.sched_h_tax_period_end) else None,
            "hcris_fy_end": r.hcris_fy_end_dt.strftime("%Y-%m-%d") if pd.notna(r.hcris_fy_end_dt) else None,
            "hcris_charity": _num(r.hcris_charity_care_cost),
            "hcris_uncomp": _num(r.hcris_uncompensated_care_cost),
            "hcris_opex": _num(r.hcris_total_operating_expenses),
            "fa_990": _num(r.sched_h_financial_assistance_at_cost),
            "cb_990": _num(r.sched_h_total_community_benefit),
            "exp_990": _num(r.sched_h_total_expenses),
            "gap": _num(r.charity_gap),
            "gap_pct": _num(r.gap_pct, decimals=4),
            "cb_pct": _num(r.community_benefit_pct_of_expenses, decimals=4),
        }
        for r in df.itertuples(index=False)
    ]

    aligned_material_sorted = aligned_material.sort_values(
        "charity_gap", ascending=False, key=lambda s: s.abs()
    )
    top = aligned_material_sorted.iloc[0]
    median_aligned_pct = float(_gap_pct(aligned_material).abs().median()) if len(aligned_material) else 0
    big_gaps = int((_gap_pct(aligned_material).abs() >= 0.5).sum())
    totals = {
        "matched": matched_count,
        "computable": computable_count,
        "aligned": aligned_count,
        "aligned_material": aligned_material_count,
        "matched_minus_computable": matched_count - computable_count,
        "aligned_minus_material": aligned_count - aligned_material_count,
        "median_aligned_material_gap_pct": round(median_aligned_pct, 4),
        "aligned_material_big_gaps": big_gaps,
        "absolute_gap_usd_aligned_material": _num(aligned_material["charity_gap"].abs().sum()),
        "total_cb_usd_aligned_material": _num(aligned_material["sched_h_total_community_benefit"].sum()),
        "top_aligned_system": top.sched_h_organization_name,
        "top_aligned_facility": top.hospital_name,
        "top_aligned_gap_usd": _num(top.charity_gap),
    }

    bundle = {"tax_year": TAX_YEAR, "totals": totals, "rows": rows}

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(bundle, separators=(",", ":")) + "\n")
    size_kb = JSON_OUT.stat().st_size / 1024
    print(f"  → {JSON_OUT} ({len(rows):,} rows, {size_kb:.1f} KB)")


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
    """
    h = df["hcris_charity_care_cost"].abs()
    f = df["sched_h_financial_assistance_at_cost"].abs()
    denom = pd.concat([h, f], axis=1).max(axis=1)
    pct = df["charity_gap"] / denom
    return pct.where(denom > 0, 0)


if __name__ == "__main__":
    main()
