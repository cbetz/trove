import pandas as pd
from form990.parse import parse_zip
from form990.schedule_h import OUTPUT_COLUMNS


def test_returns_one_row_per_schedule_h_filer(fake_zip_factory) -> None:
    """Filings without Schedule H (e.g. a generic nonprofit) should be skipped."""
    df = parse_zip(fake_zip_factory())
    assert len(df) == 2
    assert set(df["ein"]) == {"111111111", "222222222"}


def test_columns_match_schema(fake_zip_factory) -> None:
    df = parse_zip(fake_zip_factory())
    assert tuple(df.columns) == OUTPUT_COLUMNS


def test_extracts_identity_fields(fake_zip_factory) -> None:
    df = parse_zip(fake_zip_factory()).set_index("ein")
    assert df.loc["111111111", "organization_name"] == "MEMORIAL HOSPITAL"
    assert df.loc["111111111", "tax_year"] == 2022
    assert df.loc["111111111", "tax_period_begin"] == pd.Timestamp("2022-01-01")
    assert df.loc["111111111", "tax_period_end"] == pd.Timestamp("2022-12-31")
    assert df.loc["111111111", "return_version"] == "2022v5.0"


def test_extracts_main_990_financials(fake_zip_factory) -> None:
    df = parse_zip(fake_zip_factory()).set_index("ein")
    assert df.loc["111111111", "total_revenue"] == 1_000_000_000
    assert df.loc["111111111", "total_expenses"] == 950_000_000


def test_extracts_schedule_h_part_i(fake_zip_factory) -> None:
    df = parse_zip(fake_zip_factory()).set_index("ein")
    assert df.loc["111111111", "financial_assistance_at_cost"] == 50_000_000
    assert df.loc["111111111", "unreimbursed_medicaid"] == 30_000_000
    assert df.loc["111111111", "total_community_benefit"] == 100_000_000
    assert df.loc["111111111", "total_community_benefit_pct"] == pytest_approx(0.10500)


def test_extracts_schedule_h_part_iii_and_v(fake_zip_factory) -> None:
    df = parse_zip(fake_zip_factory()).set_index("ein")
    assert df.loc["111111111", "bad_debt_expense"] == 5_000_000
    assert df.loc["111111111", "hospital_facility_count"] == 1


def test_handles_missing_optional_fields(fake_zip_factory) -> None:
    """Schedule H Part I groups are minOccurs=0; absent groups should yield NaN."""
    filings = [
        {
            "ein": "999999999",
            "name": "TINY HOSP",
            "tax_year": 2022,
            # Defaults provide the standard fields, but several Part I lines
            # we don't customize will simply not be in the XML — this test
            # confirms NaN comes out, not an error.
        }
    ]
    df = parse_zip(fake_zip_factory(filings=filings)).set_index("ein")
    assert pd.isna(df.loc["999999999", "subsidized_health_services"])
    assert pd.isna(df.loc["999999999", "research"])


def test_returns_empty_frame_when_no_schedule_h(fake_zip_factory) -> None:
    filings = [
        {"ein": "555555555", "name": "FOOD BANK", "tax_year": 2022, "schedule_h": False},
    ]
    df = parse_zip(fake_zip_factory(filings=filings))
    assert df.empty
    assert tuple(df.columns) == OUTPUT_COLUMNS


def pytest_approx(expected: float, rel: float = 1e-4):
    """Tiny shim so test files don't import pytest just for approx."""
    import pytest

    return pytest.approx(expected, rel=rel)
