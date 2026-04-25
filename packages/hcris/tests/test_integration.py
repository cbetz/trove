"""End-to-end checks against real CMS data.

Skipped unless data/raw/hcris/HOSP10FY2023.zip is present locally — CI won't
have it. Run `uv run python -m hcris.download 2023` or call
`hcris.download_year(2023)` once to populate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hcris import parse_zip, pivot_wide

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


@pytest.fixture(scope="module")
def fy2023_wide(fy2023):
    return pivot_wide(fy2023)


def test_fy2023_pivot_all_variables_resolve(fy2023_wide) -> None:
    """Every seed variable should resolve on at least some FY2023 reports."""
    from hcris import load_dictionary

    dictionary = load_dictionary()
    expected = {v.name for v in dictionary}
    assert expected.issubset(set(fy2023_wide.columns))
    for col in expected:
        assert fy2023_wide[col].notna().any(), f"{col} didn't resolve on any report"


def test_fy2023_range_variable_icu_beds(fy2023_wide) -> None:
    """Range variables sum ICU bed sub-categories across all lines in 800-899."""
    icu = fy2023_wide["icu_beds"].dropna()
    coverage = len(icu) / len(fy2023_wide)
    # Roughly half of hospitals report ICU beds — small/rural hospitals often don't.
    assert 0.3 < coverage < 0.8, f"icu_beds coverage {coverage:.0%} outside plausible range"
    assert icu.max() > 100, "largest hospitals should report >100 ICU beds"
    assert (icu > 0).all(), "ICU bed counts should all be positive"


def test_fy2023_pivot_coverage_for_identity_fields(fy2023_wide) -> None:
    """Identity fields should be present on every report."""
    assert fy2023_wide["hospital_name"].notna().all()
    assert fy2023_wide["ownership_type"].notna().all()


def test_fy2023_nyp_is_biggest_hospital(fy2023_wide) -> None:
    """New York Presbyterian has had the largest net patient revenue for years.

    A useful vibe check: if the top 1 isn't a major AMC, the resolver is broken.
    """
    top1 = fy2023_wide.nlargest(1, "net_patient_revenue").iloc[0]
    assert "PRESBYTERIAN" in top1["hospital_name"].upper()
    assert top1["net_patient_revenue"] > 5e9
    assert top1["total_beds"] > 2000
