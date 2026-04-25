"""Read and filter the IRS index CSV that lists all e-filed returns per release year."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from form990.schema import INDEX_COLUMNS, RETURN_TYPE_990


def read_index(path: Path | str) -> pd.DataFrame:
    """Read an IRS index_{year}.csv into a DataFrame with the documented columns.

    Normalizes ``XML_BATCH_ID`` casing — the IRS index occasionally writes the
    trailing letter in lowercase (e.g. ``2024_TEOS_XML_04a``) but the actual
    bulk-XML URL is always uppercase. We upper-case the trailing letter here
    so cache filenames and URLs stay consistent.
    """
    df = pd.read_csv(
        path,
        usecols=list(INDEX_COLUMNS),
        dtype={c: "string" for c in INDEX_COLUMNS},
    )
    df["XML_BATCH_ID"] = df["XML_BATCH_ID"].str.replace(
        r"_(\d+)([a-d])$",
        lambda m: f"_{m.group(1)}{m.group(2).upper()}",
        regex=True,
    )
    return df


def filter_990s_for_tax_year(index: pd.DataFrame, tax_year: int) -> pd.DataFrame:
    """Filter the index to 990 returns whose TAX_PERIOD begins with the given tax year.

    Returns the latest amendment per EIN (highest SUB_DATE wins).
    """
    tax_prefix = str(tax_year)
    mask = (index["TAX_PERIOD"].str.startswith(tax_prefix, na=False)) & (
        index["RETURN_TYPE"] == RETURN_TYPE_990
    )
    matched = index.loc[mask].copy()
    # SUB_DATE is the submission/release year — sort descending and dedupe per EIN.
    matched = matched.sort_values("SUB_DATE", ascending=False)
    deduped = matched.drop_duplicates(subset=["EIN"], keep="first").reset_index(drop=True)
    return deduped
