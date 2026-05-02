"""Tests for sdoh.adi."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sdoh import county_adi_from_block_group, load_adi_block_group


@pytest.fixture
def block_group_csv(tmp_path: Path) -> Path:
    """Tiny synthetic block-group ADI file for two counties."""
    rows = [
        # County 01001 — three valid block groups + one suppressed
        ("G01000100201001", "010010201001", "71", "4"),
        ("G01000100201002", "010010201002", "79", "5"),
        ("G01000100202001", "010010202001", "87", "7"),
        ("G01000100202002", "010010202002", "GQ", "GQ"),
        # County 01003 — two valid + one PH-suppressed
        ("G01000300101001", "010030101001", "45", "3"),
        ("G01000300101002", "010030101002", "55", "4"),
        ("G01000300101003", "010030101003", "PH", "PH"),
    ]
    df = pd.DataFrame(rows, columns=["GISJOIN", "FIPS", "ADI_NATRANK", "ADI_STATERNK"])
    path = tmp_path / "adi.csv"
    df.to_csv(path, index=False)
    return path


def test_load_handles_suppression_codes(block_group_csv: Path) -> None:
    bg = load_adi_block_group(block_group_csv)
    assert len(bg) == 7
    assert bg["adi_natrank"].isna().sum() == 2  # GQ + PH


def test_fips_is_zero_padded_to_12(block_group_csv: Path) -> None:
    bg = load_adi_block_group(block_group_csv)
    assert (bg["fips"].str.len() == 12).all()


def test_county_aggregation_uses_median(block_group_csv: Path) -> None:
    counties = county_adi_from_block_group(block_group_csv).set_index("county_fips")
    # County 01001: median of [71, 79, 87] = 79; suppressed row excluded from median
    assert counties.loc["01001", "adi_natrank"] == 79
    assert counties.loc["01001", "block_group_count"] == 4  # count includes suppressed
    # County 01003: median of [45, 55] = 50; median of [3, 4] = 3.5
    assert counties.loc["01003", "adi_natrank"] == 50
    assert counties.loc["01003", "adi_state_decile"] == 3.5


def test_two_counties_produced(block_group_csv: Path) -> None:
    counties = county_adi_from_block_group(block_group_csv)
    assert len(counties) == 2
    assert set(counties["county_fips"]) == {"01001", "01003"}
