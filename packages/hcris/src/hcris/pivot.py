"""Pivot parsed HCRIS files into a wide, one-row-per-report DataFrame."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from hcris.dictionary import Variable, load_dictionary
from hcris.parse import HcrisFiles
from hcris.resolve import resolve_alpha, resolve_numeric
from hcris.schema import REPORT_STATUS_CODES

# Worksheet S-10 (uncompensated care), all vintages: S100000 before the
# Transmittal 18 renumbering, S100001/S100002 (Parts I/II) after.
_S10_PREFIX = "S10"


def pivot_wide(
    files: HcrisFiles,
    dictionary: Sequence[Variable] | None = None,
) -> pd.DataFrame:
    """Return a wide DataFrame with one row per report and one column per variable.

    Includes ``rpt_rec_num``, ``prvdr_num`` (CCN), the cost-reporting period
    dates, the report status (``rpt_stus_cd`` plus a readable ``rpt_status``) and
    HCRIS processing date from RPT, an ``s10_filed`` flag, plus one column for
    every dictionary variable that resolved.

    ``s10_filed`` says whether the report has ANY Worksheet S-10 cell. CMS's
    numeric file never stores zeros, so a missing S-10 dollar value on a report
    with ``s10_filed`` True means the cell was zero or left blank, while
    ``s10_filed`` False means the hospital filed no S-10 at all (e.g. Maryland
    all-payer hospitals, most children's and cancer hospitals).
    """
    if dictionary is None:
        dictionary = load_dictionary()

    num = resolve_numeric(files.nmrc, dictionary)
    alf = resolve_alpha(files.alpha, dictionary)

    num_wide = _pivot_one(num, fill=float("nan"))
    alf_wide = _pivot_one(alf, fill=pd.NA)

    base_cols = ["rpt_rec_num", "prvdr_num", "fy_bgn_dt", "fy_end_dt"]
    base_cols += [c for c in ("rpt_stus_cd", "proc_dt") if c in files.rpt.columns]
    base = files.rpt[base_cols].copy()
    if "rpt_stus_cd" in base.columns:
        base["rpt_status"] = base["rpt_stus_cd"].map(REPORT_STATUS_CODES).astype("string")
    s10_reports = files.nmrc.loc[
        files.nmrc["wksht_cd"].str.startswith(_S10_PREFIX, na=False), "rpt_rec_num"
    ].unique()
    base["s10_filed"] = base["rpt_rec_num"].isin(s10_reports)
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
