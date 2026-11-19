"""Resolve long NMRC/ALPHA DataFrames against the semantic field dictionary."""

from __future__ import annotations

import warnings
from collections.abc import Sequence

import pandas as pd

from hcris.dictionary import Variable, load_dictionary

_LOOKUP_COLUMNS = ["wksht_cd", "line_num", "clmn_num", "variable_name", "_wksht_rank"]


def resolve_numeric(
    nmrc: pd.DataFrame,
    dictionary: Sequence[Variable] | None = None,
) -> pd.DataFrame:
    """Return a tidy DataFrame of (rpt_rec_num, variable_name, value) from NMRC.

    Scalar dictionary entries yield one row per report. Range entries
    (``line_num_end`` set, ``aggregation="sum"``) are expanded across the
    range and summed per report. Rows that don't match any entry are dropped.

    A variable may list worksheet aliases (CMS renumbered Worksheet S-10). A
    report is expected to use exactly one of them. If a report ever carries the
    same variable under more than one worksheet code, only the first code in
    ``Variable.wksht_cds`` order (the primary) is used and a ``RuntimeWarning``
    is raised, so the two are never added together.
    """
    if dictionary is None:
        dictionary = load_dictionary()
    lookup = _build_numeric_lookup(dictionary)
    if lookup.empty:
        return nmrc.head(0).assign(variable_name=pd.Series(dtype="string"))
    merged = nmrc.merge(lookup, on=["wksht_cd", "line_num", "clmn_num"], how="inner")
    merged = _prefer_one_worksheet(merged)
    # groupby().sum() collapses range entries to one row per (report, variable)
    # and is a no-op for scalar entries (which already have one row).
    result = (
        merged.groupby(["rpt_rec_num", "variable_name"], as_index=False)["itm_val_num"]
        .sum()
        .rename(columns={"itm_val_num": "value"})
    )
    return result


def _prefer_one_worksheet(merged: pd.DataFrame) -> pd.DataFrame:
    """Keep, per (report, variable), only the cells of the best-ranked worksheet code."""
    if merged.empty or merged["_wksht_rank"].max() == 0:
        return merged.drop(columns="_wksht_rank")
    best = merged.groupby(["rpt_rec_num", "variable_name"])["_wksht_rank"].transform("min")
    dropped = merged[merged["_wksht_rank"] != best]
    if not dropped.empty:
        reports = dropped["rpt_rec_num"].nunique()
        names = sorted(dropped["variable_name"].unique())
        warnings.warn(
            f"{reports} report(s) carry the same variable under more than one worksheet "
            f"code; kept the primary worksheet only for: {', '.join(names)}",
            RuntimeWarning,
            stacklevel=3,
        )
    return merged[merged["_wksht_rank"] == best].drop(columns="_wksht_rank")


def resolve_alpha(
    alpha: pd.DataFrame,
    dictionary: Sequence[Variable] | None = None,
) -> pd.DataFrame:
    """Return a tidy DataFrame of (rpt_rec_num, variable_name, value) from ALPHA.

    Only scalar entries are supported for alpha — ranges don't make sense
    for string fields.
    """
    if dictionary is None:
        dictionary = load_dictionary()
    lookup = _build_alpha_lookup(dictionary)
    if lookup.empty:
        return alpha.head(0).assign(variable_name=pd.Series(dtype="string"))
    merged = alpha.merge(lookup, on=["wksht_cd", "line_num", "clmn_num"], how="inner")
    merged = _prefer_one_worksheet(merged)
    return merged[["rpt_rec_num", "variable_name", "itm_val_str"]].rename(
        columns={"itm_val_str": "value"}
    )


def _build_numeric_lookup(dictionary: Sequence[Variable]) -> pd.DataFrame:
    rows: list[dict[str, str | int]] = []
    for v in dictionary:
        if v.source != "nmrc":
            continue
        if v.line_num_end is None:
            rows.extend(_rows(v, v.line_num))
            continue
        # Range — expand to one lookup row per line in [line_num, line_num_end].
        if v.aggregation != "sum":
            raise ValueError(
                f"variable {v.name!r}: unsupported aggregation {v.aggregation!r}; "
                "only 'sum' is currently supported for range variables"
            )
        for line in range(int(v.line_num), int(v.line_num_end) + 1):
            rows.extend(_rows(v, f"{line:05d}"))
    return pd.DataFrame(rows, columns=_LOOKUP_COLUMNS)


def _build_alpha_lookup(dictionary: Sequence[Variable]) -> pd.DataFrame:
    rows: list[dict[str, str | int]] = []
    for v in dictionary:
        if v.source != "alpha" or v.line_num_end is not None:
            continue
        rows.extend(_rows(v, v.line_num))
    return pd.DataFrame(rows, columns=_LOOKUP_COLUMNS)


def _rows(v: Variable, line_num: str) -> list[dict[str, str | int]]:
    """One lookup row per worksheet code (primary + aliases) for this line.

    ``_wksht_rank`` is the code's position in ``v.wksht_cds`` (0 = primary).
    """
    return [
        {
            "wksht_cd": wksht_cd,
            "line_num": line_num,
            "clmn_num": v.clmn_num,
            "variable_name": v.name,
            "_wksht_rank": rank,
        }
        for rank, wksht_cd in enumerate(v.wksht_cds)
    ]
