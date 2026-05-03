"""CDC Social Vulnerability Index — load and summarize the county-level release.

Source: CDC/ATSDR Social Vulnerability Index 2022 county-level CSV. The
underlying file is US government work and public domain — trove can
redistribute derived columns freely with citation.

CDC SVI builds a composite score from 16 census-derived variables across
four themes:
  Theme 1 — Socioeconomic Status (poverty, unemployment, income, education)
  Theme 2 — Household Characteristics (age, disability, single-parent, ESL)
  Theme 3 — Racial & Ethnic Minority Status
  Theme 4 — Housing Type & Transportation (multi-unit, mobile, crowding, no vehicle)

The headline column is ``RPL_THEMES``, an overall percentile rank in [0, 1]
where higher = more socially vulnerable. CDC encodes missing values as
``-999.0``; we treat those as NaN.

Citation: Centers for Disease Control and Prevention/ Agency for Toxic
Substances and Disease Registry/ Geospatial Research, Analysis, and
Services Program. CDC/ATSDR Social Vulnerability Index 2022 Database US.
https://www.atsdr.cdc.gov/place-health/php/svi/index.html
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# CDC encodes missing data as -999. Treat those as NaN before any rounding.
SVI_MISSING = -999.0


def load_svi_county(path: Path | str) -> pd.DataFrame:
    """Read the CDC SVI county-level CSV and return a tidy frame.

    Returns one row per county with columns ``county_fips`` (5-char zero-
    padded), ``state``, ``county``, ``svi_overall_pct`` (RPL_THEMES on a
    0-100 scale, NaN for counties where CDC suppressed the rank), and the
    four per-theme percentile ranks ``svi_socio_pct``, ``svi_household_pct``,
    ``svi_minority_pct``, ``svi_housing_pct`` on the same 0-100 scale.
    """
    df = pd.read_csv(
        path,
        usecols=[
            "STCNTY",
            "STATE",
            "COUNTY",
            "RPL_THEMES",
            "RPL_THEME1",
            "RPL_THEME2",
            "RPL_THEME3",
            "RPL_THEME4",
        ],
        dtype={"STCNTY": "string", "STATE": "string", "COUNTY": "string"},
    )
    df = df.rename(
        columns={
            "STCNTY": "county_fips",
            "STATE": "state",
            "COUNTY": "county",
            "RPL_THEMES": "svi_overall_pct",
            "RPL_THEME1": "svi_socio_pct",
            "RPL_THEME2": "svi_household_pct",
            "RPL_THEME3": "svi_minority_pct",
            "RPL_THEME4": "svi_housing_pct",
        }
    )
    df["county_fips"] = df["county_fips"].str.zfill(5)
    rank_cols = [
        "svi_overall_pct",
        "svi_socio_pct",
        "svi_household_pct",
        "svi_minority_pct",
        "svi_housing_pct",
    ]
    for col in rank_cols:
        # CDC publishes ranks on a 0-1 scale with -999 for missing.
        df[col] = df[col].where(df[col] != SVI_MISSING) * 100
    return df.reset_index(drop=True)
