"""End-to-end checks against real CMS data.

Skipped unless data/raw/hcris/HOSP10FY2023.zip is present locally — CI won't
have it. Run `uv run python -m hcris.download 2023` or call
`hcris.download_year(2023)` once to populate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hcris import parse_zip

FY2023_ZIP = Path("data/raw/hcris/HOSP10FY2023.zip")

pytestmark = pytest.mark.skipif(
    not FY2023_ZIP.exists(),
    reason=f"{FY2023_ZIP} not present; run download_year(2023) first",
)


@pytest.fixture(scope="module")
def fy2023():
    return parse_zip(FY2023_ZIP)


def test_fy2023_report_row_count(fy2023) -> None:
    """Pinned as of CMS build dated 2026-01-12. Bump if CMS rebuilds FY2023 and counts drift."""
    assert len(fy2023.rpt) == 6105


def test_fy2023_distinct_ccns(fy2023) -> None:
    assert fy2023.rpt["prvdr_num"].nunique() == 6042


def test_fy2023_nmrc_row_count(fy2023) -> None:
    assert len(fy2023.nmrc) == 19_539_796


def test_fy2023_alpha_row_count(fy2023) -> None:
    assert len(fy2023.alpha) == 3_765_093


def test_fy2023_invariants_hold(fy2023) -> None:
    rpt_ids = set(fy2023.rpt["rpt_rec_num"])
    assert fy2023.rpt["rpt_rec_num"].is_unique
    assert fy2023.nmrc["itm_val_num"].notna().all()
    assert set(fy2023.nmrc["rpt_rec_num"]).issubset(rpt_ids)
    assert set(fy2023.alpha["rpt_rec_num"]).issubset(rpt_ids)
