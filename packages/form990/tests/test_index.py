from pathlib import Path

import pandas as pd
from form990.index import filter_990s_for_tax_year, read_index


def _index_csv(tmp_path: Path) -> Path:
    """A tiny synthetic IRS index CSV."""
    rows = [
        # Two hospitals filing for TY2022, one with an amendment
        (
            "100",
            "EFILE",
            "111111111",
            "202212",
            "2024",
            "MEMORIAL",
            "990",
            "DLN1",
            "OBJ1",
            "2024_TEOS_XML_01A",
        ),
        (
            "101",
            "EFILE",
            "111111111",
            "202212",
            "2025",
            "MEMORIAL",
            "990",
            "DLN2",
            "OBJ2",
            "2025_TEOS_XML_03A",
        ),
        (
            "200",
            "EFILE",
            "222222222",
            "202212",
            "2024",
            "RIVER",
            "990",
            "DLN3",
            "OBJ3",
            "2024_TEOS_XML_02A",
        ),
        # 990EZ filing — should be excluded
        (
            "300",
            "EFILE",
            "333333333",
            "202212",
            "2024",
            "EZ ORG",
            "990EZ",
            "DLN4",
            "OBJ4",
            "2024_TEOS_XML_01A",
        ),
        # TY2021 filing — should be excluded by tax_year filter
        (
            "400",
            "EFILE",
            "444444444",
            "202112",
            "2024",
            "OLD HOSP",
            "990",
            "DLN5",
            "OBJ5",
            "2024_TEOS_XML_01A",
        ),
    ]
    cols = [
        "RETURN_ID",
        "FILING_TYPE",
        "EIN",
        "TAX_PERIOD",
        "SUB_DATE",
        "TAXPAYER_NAME",
        "RETURN_TYPE",
        "DLN",
        "OBJECT_ID",
        "XML_BATCH_ID",
    ]
    df = pd.DataFrame(rows, columns=cols)
    path = tmp_path / "index.csv"
    df.to_csv(path, index=False)
    return path


def test_read_index_columns(tmp_path: Path) -> None:
    df = read_index(_index_csv(tmp_path))
    assert list(df.columns) == [
        "RETURN_ID",
        "FILING_TYPE",
        "EIN",
        "TAX_PERIOD",
        "SUB_DATE",
        "TAXPAYER_NAME",
        "RETURN_TYPE",
        "DLN",
        "OBJECT_ID",
        "XML_BATCH_ID",
    ]


def test_filter_drops_non_990(tmp_path: Path) -> None:
    df = read_index(_index_csv(tmp_path))
    out = filter_990s_for_tax_year(df, 2022)
    # 990EZ excluded
    assert "333333333" not in set(out["EIN"])


def test_filter_drops_other_tax_years(tmp_path: Path) -> None:
    df = read_index(_index_csv(tmp_path))
    out = filter_990s_for_tax_year(df, 2022)
    assert "444444444" not in set(out["EIN"])


def test_filter_dedupes_amendments_keeping_latest(tmp_path: Path) -> None:
    df = read_index(_index_csv(tmp_path))
    out = filter_990s_for_tax_year(df, 2022)
    memorial = out[out["EIN"] == "111111111"]
    assert len(memorial) == 1
    # The 2025 amendment beats the 2024 original
    assert memorial.iloc[0]["SUB_DATE"] == "2025"
    assert memorial.iloc[0]["XML_BATCH_ID"] == "2025_TEOS_XML_03A"
