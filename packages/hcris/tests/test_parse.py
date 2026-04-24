import pandas as pd
from hcris.parse import HcrisFiles, parse_zip
from hcris.schema import ALPHA_COLUMNS, NMRC_COLUMNS, RPT_COLUMNS


def test_returns_hcris_files(fake_zip_factory) -> None:
    files = parse_zip(fake_zip_factory(2023))
    assert isinstance(files, HcrisFiles)


def test_row_counts(fake_zip_factory) -> None:
    files = parse_zip(fake_zip_factory(2023))
    assert len(files.rpt) == 2
    assert len(files.nmrc) == 4
    assert len(files.alpha) == 2


def test_column_orderings(fake_zip_factory) -> None:
    files = parse_zip(fake_zip_factory(2023))
    assert tuple(files.rpt.columns) == RPT_COLUMNS
    assert tuple(files.nmrc.columns) == NMRC_COLUMNS
    assert tuple(files.alpha.columns) == ALPHA_COLUMNS


def test_wksht_cd_whitespace_stripped(fake_zip_factory) -> None:
    """Trailing spaces in wksht_cd would silently break equality joins otherwise."""
    files = parse_zip(fake_zip_factory(2023))
    assert (files.nmrc["wksht_cd"] == "S300001").sum() == 3


def test_clmn_num_is_string(fake_zip_factory) -> None:
    """Some clmn_num values contain letters (e.g. '01A'); must stay as string."""
    files = parse_zip(fake_zip_factory(2023))
    assert files.nmrc["clmn_num"].dtype == "string"
    assert (files.nmrc["clmn_num"] == "01A").any()


def test_rpt_rec_num_is_int(fake_zip_factory) -> None:
    files = parse_zip(fake_zip_factory(2023))
    assert files.rpt["rpt_rec_num"].dtype == "int64"
    assert files.nmrc["rpt_rec_num"].dtype == "int64"


def test_dates_parsed(fake_zip_factory) -> None:
    files = parse_zip(fake_zip_factory(2023))
    assert pd.api.types.is_datetime64_any_dtype(files.rpt["fy_bgn_dt"])
    assert files.rpt["fy_bgn_dt"].iloc[0] == pd.Timestamp("2023-01-01")


def test_invariant_nmrc_values_non_null(fake_zip_factory) -> None:
    """Sacarny's invariant: NMRC itm_val_num should never be null."""
    files = parse_zip(fake_zip_factory(2023))
    assert files.nmrc["itm_val_num"].notna().all()


def test_invariant_nmrc_rpt_rec_nums_subset_of_rpt(fake_zip_factory) -> None:
    files = parse_zip(fake_zip_factory(2023))
    rpt_ids = set(files.rpt["rpt_rec_num"])
    assert set(files.nmrc["rpt_rec_num"]).issubset(rpt_ids)


def test_invariant_alpha_rpt_rec_nums_subset_of_rpt(fake_zip_factory) -> None:
    files = parse_zip(fake_zip_factory(2023))
    rpt_ids = set(files.rpt["rpt_rec_num"])
    assert set(files.alpha["rpt_rec_num"]).issubset(rpt_ids)


def test_invariant_rpt_rec_num_unique_in_rpt(fake_zip_factory) -> None:
    files = parse_zip(fake_zip_factory(2023))
    assert files.rpt["rpt_rec_num"].is_unique
