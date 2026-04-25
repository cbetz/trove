"""Resolve long NMRC/ALPHA DataFrames against the semantic field dictionary."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from hcris.dictionary import Variable, load_dictionary


def resolve_numeric(
    nmrc: pd.DataFrame,
    dictionary: Sequence[Variable] | None = None,
) -> pd.DataFrame:
    """Return a tidy DataFrame of (rpt_rec_num, variable_name, value) from NMRC.

    Scalar dictionary entries yield one row per report. Range entries
    (``line_num_end`` set, ``aggregation="sum"``) are expanded across the
    range and summed per report. Rows that don't match any entry are dropped.
    """
    if dictionary is None:
        dictionary = load_dictionary()
    lookup = _build_numeric_lookup(dictionary)
    if lookup.empty:
        return nmrc.head(0).assign(variable_name=pd.Series(dtype="string"))
    merged = nmrc.merge(lookup, on=["wksht_cd", "line_num", "clmn_num"], how="inner")
    # groupby().sum() collapses range entries to one row per (report, variable)
    # and is a no-op for scalar entries (which already have one row).
    result = (
        merged.groupby(["rpt_rec_num", "variable_name"], as_index=False)["itm_val_num"]
        .sum()
        .rename(columns={"itm_val_num": "value"})
    )
    return result


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
    return merged[["rpt_rec_num", "variable_name", "itm_val_str"]].rename(
        columns={"itm_val_str": "value"}
    )


def _build_numeric_lookup(dictionary: Sequence[Variable]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for v in dictionary:
        if v.source != "nmrc":
            continue
        if v.line_num_end is None:
            rows.append(_row(v, v.line_num))
            continue
        # Range — expand to one lookup row per line in [line_num, line_num_end].
        if v.aggregation != "sum":
            raise ValueError(
                f"variable {v.name!r}: unsupported aggregation {v.aggregation!r}; "
                "only 'sum' is currently supported for range variables"
            )
        for line in range(int(v.line_num), int(v.line_num_end) + 1):
            rows.append(_row(v, f"{line:05d}"))
    return pd.DataFrame(rows, columns=["wksht_cd", "line_num", "clmn_num", "variable_name"])


def _build_alpha_lookup(dictionary: Sequence[Variable]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for v in dictionary:
        if v.source != "alpha" or v.line_num_end is not None:
            continue
        rows.append(_row(v, v.line_num))
    return pd.DataFrame(rows, columns=["wksht_cd", "line_num", "clmn_num", "variable_name"])


def _row(v: Variable, line_num: str) -> dict[str, str]:
    return {
        "wksht_cd": v.wksht_cd,
        "line_num": line_num,
        "clmn_num": v.clmn_num,
        "variable_name": v.name,
    }
