"""Tests for sdoh.svi."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sdoh import load_svi_county


@pytest.fixture
def svi_county_csv(tmp_path: Path) -> Path:
    """Tiny synthetic SVI county-level file with one suppressed row."""
    rows = [
        ("01001", "ALABAMA", "Autauga County", 0.5234, 0.40, 0.51, 0.62, 0.55),
        ("01003", "ALABAMA", "Baldwin County", 0.2150, 0.18, 0.20, 0.30, 0.25),
        # CDC encodes missing as -999.
        ("02013", "ALASKA", "Aleutians East", -999.0, -999.0, -999.0, -999.0, -999.0),
    ]
    cols = [
        "STCNTY",
        "STATE",
        "COUNTY",
        "RPL_THEMES",
        "RPL_THEME1",
        "RPL_THEME2",
        "RPL_THEME3",
        "RPL_THEME4",
    ]
    df = pd.DataFrame(rows, columns=cols)
    path = tmp_path / "svi.csv"
    df.to_csv(path, index=False)
    return path


def test_loads_three_counties(svi_county_csv: Path) -> None:
    svi = load_svi_county(svi_county_csv)
    assert len(svi) == 3
    assert set(svi["county_fips"]) == {"01001", "01003", "02013"}


def test_rescales_to_0_100(svi_county_csv: Path) -> None:
    svi = load_svi_county(svi_county_csv).set_index("county_fips")
    assert svi.loc["01001", "svi_overall_pct"] == pytest.approx(52.34)
    assert svi.loc["01003", "svi_overall_pct"] == pytest.approx(21.50)


def test_handles_missing_codes(svi_county_csv: Path) -> None:
    svi = load_svi_county(svi_county_csv).set_index("county_fips")
    assert pd.isna(svi.loc["02013", "svi_overall_pct"])
    for theme_col in (
        "svi_socio_pct",
        "svi_household_pct",
        "svi_minority_pct",
        "svi_housing_pct",
    ):
        assert pd.isna(svi.loc["02013", theme_col])


def test_county_fips_zero_padded(svi_county_csv: Path) -> None:
    svi = load_svi_county(svi_county_csv)
    assert (svi["county_fips"].str.len() == 5).all()
