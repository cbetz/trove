"""Pivot parsed HCRIS files into a wide, one-row-per-report DataFrame."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from hcris.dictionary import Variable, load_dictionary
from hcris.parse import HcrisFiles
from hcris.resolve import resolve_alpha, resolve_numeric


def pivot_wide(
    files: HcrisFiles,
    dictionary: Sequence[Variable] | None = None,
) -> pd.DataFrame:
    """Return a wide DataFrame with one row per report and one column per variable.

    Includes ``rpt_rec_num``, ``prvdr_num`` (CCN), and the fiscal-year dates from
    RPT, plus one column for every dictionary variable that resolved.
    """
    if dictionary is None:
        dictionary = load_dictionary()

    num = resolve_numeric(files.nmrc, dictionary)
    alf = resolve_alpha(files.alpha, dictionary)

    num_wide = _pivot_one(num, fill=float("nan"))
    alf_wide = _pivot_one(alf, fill=pd.NA)

    base = files.rpt[["rpt_rec_num", "prvdr_num", "fy_bgn_dt", "fy_end_dt"]]
    return base.merge(num_wide, on="rpt_rec_num", how="left").merge(
        alf_wide, on="rpt_rec_num", how="left"
    )


def _pivot_one(resolved: pd.DataFrame, fill) -> pd.DataFrame:
    if resolved.empty:
        return pd.DataFrame({"rpt_rec_num": pd.Series(dtype="int64")})
    # Take first value when a cell appears more than once — defensive; shouldn't
    # happen for single-cell dictionary entries but protects against oddities.
    deduped = resolved.drop_duplicates(subset=["rpt_rec_num", "variable_name"], keep="first")
    wide = deduped.pivot(index="rpt_rec_num", columns="variable_name", values="value")
    wide.columns.name = None
    return wide.reset_index()
