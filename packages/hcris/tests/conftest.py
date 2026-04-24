"""Shared fixtures for hcris tests — synthetic HOSP10FY<year>.zip builder."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

_RPT_ROWS: tuple[str, ...] = (
    # rpt_rec_num=1001, as-submitted, with two numeric cells and one alpha cell
    "1001,1,123456,1234567890,1,1/1/2023,12/31/2023,2/15/2024,N,Y,1,99,1,3/1/2024,,,,",
    # rpt_rec_num=1002, settled without audit
    "1002,2,654321,0987654321,2,7/1/2023,6/30/2024,8/15/2024,N,Y,2,99,1,9/1/2024,,,,",
)

_NMRC_ROWS: tuple[str, ...] = (
    "1001,S300001,00100,00200,12345.67",
    "1001,G300000,00100,00100,500000",
    # Trailing whitespace on wksht_cd — parser must strip.
    "1002,S300001   ,00100,00200,67890.12",
    # clmn_num with a letter — parser must preserve as string.
    "1002,S300001,00100,01A,100",
)

_ALPHA_ROWS: tuple[str, ...] = (
    '1001,S200000,00100,00100,"Test Hospital A"',
    '1002,S200000,00100,00100,"Test Hospital B"',
)


@pytest.fixture
def fake_zip_factory(tmp_path: Path):
    """Return a callable that builds a HOSP10FY{year}.zip in tmp_path."""

    def build(year: int = 2023) -> Path:
        path = tmp_path / f"HOSP10FY{year}.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr(f"HOSP10_{year}_RPT.CSV", "\r\n".join(_RPT_ROWS) + "\r\n")
            zf.writestr(f"HOSP10_{year}_NMRC.CSV", "\r\n".join(_NMRC_ROWS) + "\r\n")
            zf.writestr(f"HOSP10_{year}_ALPHA.CSV", "\r\n".join(_ALPHA_ROWS) + "\r\n")
        return path

    return build
