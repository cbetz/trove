"""Read and filter the IRS index CSV that lists all e-filed returns per release year."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from form990.schema import INDEX_COLUMNS, INDEX_OPTIONAL_COLUMNS, RETURN_TYPE_990


def read_index(path: Path | str) -> pd.DataFrame:
    """Read an IRS index_{year}.csv into a DataFrame with the documented columns.

    ``XML_BATCH_ID`` is optional: the 2023 release's index does not have it (the
    column was introduced with the 2024 release). When absent it is returned as an
    all-missing column, so callers must not rely on the index to locate a return —
    ``form990.parse`` locates returns by scanning each ZIP's member names instead.
    Even where the column exists it is not reliable: the 2025 and 2026 releases
    split May into ``05A`` and ``05B`` ZIPs while the index labels every May row
    ``05A``.

    Normalizes ``XML_BATCH_ID`` casing — the IRS index occasionally writes the
    trailing letter in lowercase (e.g. ``2024_TEOS_XML_04a``) but the actual
    bulk-XML URL is always uppercase.
    """
    header = pd.read_csv(path, nrows=0).columns
    missing = [c for c in INDEX_COLUMNS if c not in header and c not in INDEX_OPTIONAL_COLUMNS]
    if missing:
        raise ValueError(f"index {path} is missing required column(s): {missing}")
    present = [c for c in INDEX_COLUMNS if c in header]
    df = pd.read_csv(path, usecols=present, dtype={c: "string" for c in present})
    for c in INDEX_COLUMNS:
        if c not in df.columns:
            df[c] = pd.Series(pd.NA, index=df.index, dtype="string")
    df = df[list(INDEX_COLUMNS)]
    df["XML_BATCH_ID"] = df["XML_BATCH_ID"].str.replace(
        r"_(\d+)([a-d])$",
        lambda m: f"_{m.group(1)}{m.group(2).upper()}",
        regex=True,
    )
    return df


def tax_periods_for_tax_year(tax_year: int) -> tuple[str, str]:
    """Inclusive ``TAX_PERIOD`` (YYYYMM, the period END) window for a full-year return.

    The IRS "tax year" is the calendar year in which the period BEGINS, so tax
    year 2022 covers 12-month periods ending 2022-12 through 2023-11. Short-year
    returns can end earlier and are not covered by this window; the XML's own
    ``TaxYr`` is authoritative and is what the parser filters on.
    """
    return f"{tax_year}12", f"{tax_year + 1}11"


def filter_990s_for_tax_year(index: pd.DataFrame, tax_year: int) -> pd.DataFrame:
    """Filter the index to full-year 990 returns for the given tax year.

    ``TAX_PERIOD`` is the period END (YYYYMM); see ``tax_periods_for_tax_year``.
    Returns the latest amendment per EIN (highest SUB_DATE wins).
    """
    lo, hi = tax_periods_for_tax_year(tax_year)
    period = index["TAX_PERIOD"].fillna("")
    mask = (period >= lo) & (period <= hi) & (index["RETURN_TYPE"] == RETURN_TYPE_990)
    matched = index.loc[mask].copy()
    # SUB_DATE is the submission/release year — sort descending and dedupe per EIN.
    matched = matched.sort_values("SUB_DATE", ascending=False)
    deduped = matched.drop_duplicates(subset=["EIN"], keep="first").reset_index(drop=True)
    return deduped
