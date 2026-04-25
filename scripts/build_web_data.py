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
    df = pd.read_csv(CSV_IN, dtype={"ein": str})
    df = df.sort_values("charity_gap", ascending=False, key=lambda s: s.abs())

    rows = [
        {
            "ein": r.ein,
            "system": r.sched_h_organization_name,
            "facility": r.hospital_name,
            "ccns": int(r.ccn_count),
            "period_end": r.sched_h_tax_period_end,
            "hcris_charity": _num(r.hcris_charity_care_cost),
            "hcris_uncomp": _num(r.hcris_uncompensated_care_cost),
            "hcris_opex": _num(r.hcris_total_operating_expenses),
            "fa_990": _num(r.sched_h_financial_assistance_at_cost),
            "cb_990": _num(r.sched_h_total_community_benefit),
            "exp_990": _num(r.sched_h_total_expenses),
            "gap": _num(r.charity_gap),
            "cb_pct": _num(r.community_benefit_pct_of_expenses, decimals=4),
        }
        for r in df.itertuples(index=False)
    ]

    top = df.iloc[0]
    totals = {
        "systems": int(len(df)),
        "absolute_gap_usd": _num(df["charity_gap"].abs().sum()),
        "total_community_benefit_usd": _num(df["sched_h_total_community_benefit"].sum()),
        "pct_hcris_higher": round(float((df["charity_gap"] > 0).mean()), 4),
        "median_abs_gap_usd": _num(df["charity_gap"].abs().median()),
        "top_gap_system": top.sched_h_organization_name,
        "top_gap_facility": top.hospital_name,
        "top_gap_usd": _num(top.charity_gap),
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


if __name__ == "__main__":
    main()
