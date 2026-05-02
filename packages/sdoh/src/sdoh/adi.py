"""Area Deprivation Index — load, normalize, and aggregate UW's block-group release.

Source: University of Wisconsin School of Medicine and Public Health Neighborhood
Atlas — `https://www.neighborhoodatlas.medicine.wisc.edu/`. Per UW's terms, the
raw block-group CSV is **not** redistributed by trove; users must download it
themselves. This module produces derived **county-level aggregates**, which are
publishable per standard practice in the literature with citation.

Citation: Kind AJH, Buckingham W. Making Neighborhood Disadvantage Metrics
Accessible: The Neighborhood Atlas. *N Engl J Med* 2018;378:2456-2458.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# UW marks block groups whose ADI can't be computed reliably with these codes
# instead of numbers. Treat them as missing for any quantitative aggregation.
SUPPRESSION_CODES = frozenset({"GQ", "PH", "GQ-PH", "QDI"})


def load_adi_block_group(path: Path | str) -> pd.DataFrame:
    """Read the UW block-group ADI CSV into a tidy DataFrame.

    Returns columns ``gisjoin``, ``fips`` (12-char zero-padded block-group
    Census ID), ``adi_natrank`` (1-100, ``NaN`` for suppressed rows), and
    ``adi_state_decile`` (1-10, ``NaN`` for suppressed rows). Suppression
    codes (``GQ``, ``PH``, ``GQ-PH``, ``QDI``) are recorded as missing.
    """
    df = pd.read_csv(
        path,
        dtype={
            "GISJOIN": "string",
            "FIPS": "string",
            "ADI_NATRANK": "string",
            "ADI_STATERNK": "string",
        },
    )
    df = df[["GISJOIN", "FIPS", "ADI_NATRANK", "ADI_STATERNK"]].rename(
        columns={
            "GISJOIN": "gisjoin",
            "FIPS": "fips",
            "ADI_NATRANK": "adi_natrank",
            "ADI_STATERNK": "adi_state_decile",
        }
    )
    df["fips"] = df["fips"].str.zfill(12)
    df["adi_natrank"] = pd.to_numeric(
        df["adi_natrank"].where(~df["adi_natrank"].isin(SUPPRESSION_CODES)),
        errors="coerce",
    )
    df["adi_state_decile"] = pd.to_numeric(
        df["adi_state_decile"].where(~df["adi_state_decile"].isin(SUPPRESSION_CODES)),
        errors="coerce",
    )
    return df.reset_index(drop=True)


def county_adi_from_block_group(path: Path | str) -> pd.DataFrame:
    """Aggregate block-group ADI to 5-digit county FIPS.

    Returns one row per county with median ``adi_natrank`` and median
    ``adi_state_decile`` across that county's block groups (suppressed rows
    excluded from medians but counted in ``block_group_count``).

    Aggregating ranks is not the same as ranking aggregates — treat the
    output as the **typical block-group score** for this county, not as a
    single composite rank of the county itself among all counties.
    """
    bg = load_adi_block_group(path)
    bg["county_fips"] = bg["fips"].str[:5]
    grouped = bg.groupby("county_fips", as_index=False).agg(
        adi_natrank=("adi_natrank", "median"),
        adi_state_decile=("adi_state_decile", "median"),
        block_group_count=("fips", "size"),
    )
    return grouped
