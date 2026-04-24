from hcris.schema import ALPHA_COLUMNS, NMRC_COLUMNS, REPORT_STATUS_CODES, RPT_COLUMNS


def test_rpt_has_18_columns() -> None:
    assert len(RPT_COLUMNS) == 18


def test_rpt_starts_with_rpt_rec_num() -> None:
    assert RPT_COLUMNS[0] == "rpt_rec_num"


def test_nmrc_columns() -> None:
    assert NMRC_COLUMNS == (
        "rpt_rec_num",
        "wksht_cd",
        "line_num",
        "clmn_num",
        "itm_val_num",
    )


def test_alpha_columns() -> None:
    assert ALPHA_COLUMNS == (
        "rpt_rec_num",
        "wksht_cd",
        "line_num",
        "clmn_num",
        "itm_val_str",
    )


def test_report_status_codes_cover_1_to_5() -> None:
    assert set(REPORT_STATUS_CODES) == {1, 2, 3, 4, 5}
