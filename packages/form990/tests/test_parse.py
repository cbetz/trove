from pathlib import Path

import form990.parse as parse_mod
import pandas as pd
from form990.download import discover_batches
from form990.parse import latest_return_per_ein, parse_tax_year, parse_zip
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


def test_extracts_line_7a_gross_and_offset(fake_zip_factory) -> None:
    """Schedule H Part I line 7a columns (c) and (d) sit beside the net column (e)."""
    filings = [
        {
            "ein": "060646652",
            "name": "YALE NEW HAVEN HOSPITAL",
            "tax_year": 2022,
            "fa_at_cost_gross": 257_262_512,
            "fa_at_cost_offset": 144_162_000,
            "fa_at_cost_net": 113_100_512,
        },
        {"ein": "111111111", "name": "NO OFFSET HOSPITAL", "tax_year": 2022},
    ]
    df = parse_zip(fake_zip_factory(filings=filings)).set_index("ein")
    yale = df.loc["060646652"]
    assert yale["financial_assistance_at_cost_gross"] == 257_262_512
    assert yale["financial_assistance_at_cost_offset_revenue"] == 144_162_000
    assert yale["financial_assistance_at_cost"] == 113_100_512
    # Absent columns stay missing — never 0.
    assert pd.isna(df.loc["111111111", "financial_assistance_at_cost_gross"])
    assert pd.isna(df.loc["111111111", "financial_assistance_at_cost_offset_revenue"])


def test_extracts_provenance_fields(fake_zip_factory) -> None:
    filings = [
        {
            "ein": "111111111",
            "name": "MEMORIAL HOSPITAL",
            "tax_year": 2022,
            "member": "2023_TEOS_XML_05A/202341319349301234_public.xml",
            "amended": True,
            "return_ts": "2024-08-14T20:42:27-05:00",
        },
        {"ein": "222222222", "name": "RIVER HOSPITAL", "tax_year": 2022},
    ]
    df = parse_zip(fake_zip_factory(filings=filings)).set_index("ein")
    assert df.loc["111111111", "object_id"] == "202341319349301234"
    assert bool(df.loc["111111111", "amended_return"]) is True
    assert bool(df.loc["222222222", "amended_return"]) is False
    assert df.loc["111111111", "return_ts"] == pd.Timestamp("2024-08-15T01:42:27Z")
    assert df.loc["111111111", "filer_city"] == "SPRINGFIELD"
    assert df.loc["111111111", "filer_state"] == "IL"


def _release(fake_zip_factory, monkeypatch, zips: dict[str, list[dict]]) -> dict[str, Path]:
    """Stand up fake bulk ZIPs and route ``download_zip`` to them."""
    paths = {
        batch: fake_zip_factory(filings=f, zip_name=f"{batch}.zip") for batch, f in zips.items()
    }
    monkeypatch.setattr(parse_mod, "download_zip", lambda _year, batch, _cache: paths[batch])
    return paths


def test_parse_tax_year_scans_every_zip_without_an_index(
    fake_zip_factory, monkeypatch, tmp_path
) -> None:
    """The 2023 release has no batch column in its index, and the 2025/2026 indexes
    label every May return 05A though the returns are split across 05A and 05B.
    Returns must be found by scanning each ZIP, so nothing in 05B is skipped."""
    paths = _release(
        fake_zip_factory,
        monkeypatch,
        {
            "2025_TEOS_XML_05A": [
                {
                    "ein": "111111111",
                    "name": "IN 05A",
                    "tax_year": 2022,
                    "member": "100001_public.xml",
                }
            ],
            "2025_TEOS_XML_05B": [
                {
                    "ein": "222222222",
                    "name": "IN 05B",
                    "tax_year": 2022,
                    "member": "100002_public.xml",
                },
                {
                    "ein": "333333333",
                    "name": "TY2023",
                    "tax_year": 2023,
                    "member": "100003_public.xml",
                },
            ],
        },
    )
    xml_dir = tmp_path / "xml"
    df = parse_tax_year(
        2022,
        2025,
        tmp_path,
        progress=False,
        keep_zips=False,
        batches=list(paths),
        xml_dir=xml_dir,
        batch_cache_dir=tmp_path / "batches",
    )
    assert set(df["ein"]) == {"111111111", "222222222"}  # 05B found; TY2023 dropped
    assert df.set_index("ein").loc["222222222", "batch_id"] == "2025_TEOS_XML_05B"
    assert (df["release_year"] == 2025).all()
    # One ZIP at a time: each is deleted once parsed.
    assert not any(p.exists() for p in paths.values())
    # Raw XML kept only for the returns in the result.
    assert sorted(p.name for p in xml_dir.iterdir()) == ["100001_public.xml", "100002_public.xml"]
    # A second run resumes from the per-ZIP cache without touching the (deleted) ZIPs.
    again = parse_tax_year(
        2022,
        2025,
        tmp_path,
        progress=False,
        batches=list(paths),
        batch_cache_dir=tmp_path / "batches",
    )
    assert set(again["ein"]) == {"111111111", "222222222"}


def test_discover_batches_probes_past_letter_a(monkeypatch) -> None:
    import form990.download as dl

    published = {"2025_TEOS_XML_01A", "2025_TEOS_XML_05A", "2025_TEOS_XML_05B", "2025_TEOS_XML_11A"}
    monkeypatch.setattr(dl, "_exists", lambda url: url.rsplit("/", 1)[1][:-4] in published)
    assert discover_batches(2025) == sorted(published)


def test_latest_return_prefers_amendment_then_full_year() -> None:
    df = pd.DataFrame(
        [
            # Original and amendment for the same period: the later e-file wins.
            ("111111111", "2022-01-01", "2022-12-31", "2023-11-15T00:00:00Z", 2023, 1.0),
            ("111111111", "2022-01-01", "2022-12-31", "2025-01-28T00:00:00Z", 2025, 2.0),
            # Full year plus a later short year filed on the same year's forms:
            # the full year is the year being compared.
            ("222222222", "2022-01-01", "2022-12-31", "2023-11-15T00:00:00Z", 2023, 3.0),
            ("222222222", "2023-01-01", "2023-06-30", "2024-05-15T00:00:00Z", 2024, 4.0),
        ],
        columns=[
            "ein",
            "tax_period_begin",
            "tax_period_end",
            "return_ts",
            "release_year",
            "financial_assistance_at_cost",
        ],
    )
    for c in ("tax_period_begin", "tax_period_end", "return_ts"):
        df[c] = pd.to_datetime(df[c], utc=(c == "return_ts"))
    out = latest_return_per_ein(df).set_index("ein")
    assert out.loc["111111111", "financial_assistance_at_cost"] == 2.0
    assert out.loc["222222222", "financial_assistance_at_cost"] == 3.0
