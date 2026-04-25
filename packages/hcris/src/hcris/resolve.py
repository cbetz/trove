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

    Only dictionary entries with ``source == "nmrc"`` are considered. Rows in
    ``nmrc`` that don't match a dictionary entry are dropped — the dictionary
    is expected to be partial; this function is the point of narrowing.
    """
    if dictionary is None:
        dictionary = load_dictionary()
    lookup = _build_lookup(dictionary, source="nmrc")
    if lookup.empty:
        return nmrc.head(0).assign(variable_name=pd.Series(dtype="string"))
    merged = nmrc.merge(lookup, on=["wksht_cd", "line_num", "clmn_num"], how="inner")
    return merged[["rpt_rec_num", "variable_name", "itm_val_num"]].rename(
        columns={"itm_val_num": "value"}
    )


def resolve_alpha(
    alpha: pd.DataFrame,
    dictionary: Sequence[Variable] | None = None,
) -> pd.DataFrame:
    """Return a tidy DataFrame of (rpt_rec_num, variable_name, value) from ALPHA."""
    if dictionary is None:
        dictionary = load_dictionary()
    lookup = _build_lookup(dictionary, source="alpha")
    if lookup.empty:
        return alpha.head(0).assign(variable_name=pd.Series(dtype="string"))
    merged = alpha.merge(lookup, on=["wksht_cd", "line_num", "clmn_num"], how="inner")
    return merged[["rpt_rec_num", "variable_name", "itm_val_str"]].rename(
        columns={"itm_val_str": "value"}
    )


def _build_lookup(dictionary: Sequence[Variable], source: str) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for v in dictionary:
        if v.source != source:
            continue
        if v.line_num_end is not None:
            # Range variables require aggregation — deferred to a later milestone.
            continue
        rows.append(
            {
                "wksht_cd": v.wksht_cd,
                "line_num": v.line_num,
                "clmn_num": v.clmn_num,
                "variable_name": v.name,
            }
        )
    return pd.DataFrame(rows, columns=["wksht_cd", "line_num", "clmn_num", "variable_name"])
