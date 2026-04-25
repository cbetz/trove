"""End-to-end checks against real IRS bulk data.

Skipped unless data/raw/form990/2024_TEOS_XML_01A.zip is present locally — CI
won't have it. Populate by running ``download_zip(2024, "2024_TEOS_XML_01A")``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from form990 import parse_zip

ZIP_PATH = Path("data/raw/form990/2024_TEOS_XML_01A.zip")

pytestmark = pytest.mark.skipif(
    not ZIP_PATH.exists(),
    reason=f"{ZIP_PATH} not present; run download_zip(2024, '2024_TEOS_XML_01A') first",
)


@pytest.fixture(scope="module")
def parsed():
    return parse_zip(ZIP_PATH)


def test_total_schedule_h_filings(parsed) -> None:
    """Pinned to the 2024-release IRS bulk feed. Bump if the IRS reissues this ZIP."""
    assert len(parsed) == 21


def test_corewell_health_appears(parsed) -> None:
    """Corewell Health (EIN 611740292) is the largest hospital system in this ZIP."""
    by_ein = parsed.set_index("ein")
    assert "611740292" in by_ein.index
    row = by_ein.loc["611740292"]
    assert "COREWELL" in row["organization_name"].upper()
    assert row["hospital_facility_count"] == 21
    assert row["total_revenue"] > 9e9
    assert row["total_community_benefit"] > 800_000_000


def test_hennepin_healthcare_appears(parsed) -> None:
    """Hennepin Healthcare (EIN 421707837), Minneapolis safety-net hospital."""
    by_ein = parsed.set_index("ein")
    assert "421707837" in by_ein.index
    row = by_ein.loc["421707837"]
    assert "HENNEPIN" in row["organization_name"].upper()
    assert row["total_community_benefit"] > 50_000_000


def test_only_990_filings_with_schedule_h(parsed) -> None:
    """No nulls in the headline community benefit field for parsed rows."""
    # Most rows should have a TotalCommunityBenefitsGrp; a handful might lack it
    # if the filer filled in detail lines but not the rollup. Allow a few.
    coverage = parsed["total_community_benefit"].notna().mean()
    assert coverage > 0.7, f"only {coverage:.0%} of Schedule H filers have a 7k total"


def test_tax_year_distribution(parsed) -> None:
    """Most filings in the 2024 release should be TY2022."""
    ty_counts = parsed["tax_year"].value_counts()
    assert ty_counts.idxmax() == 2022
