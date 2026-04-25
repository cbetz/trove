import pandas as pd
from hcris.dictionary import Variable
from hcris.parse import HcrisFiles
from hcris.pivot import pivot_wide


def _files() -> HcrisFiles:
    rpt = pd.DataFrame(
        {
            "rpt_rec_num": [1, 2],
            "prvdr_num": ["123456", "654321"],
            "fy_bgn_dt": pd.to_datetime(["2023-01-01", "2023-07-01"]),
            "fy_end_dt": pd.to_datetime(["2023-12-31", "2024-06-30"]),
        }
    )
    nmrc = pd.DataFrame(
        {
            "rpt_rec_num": [1, 1, 2],
            "wksht_cd": ["S300001", "G300000", "S300001"],
            "line_num": ["01400", "00300", "01400"],
            "clmn_num": ["00200", "00100", "00200"],
            "itm_val_num": [450.0, 10_000_000.0, 200.0],
        }
    )
    alpha = pd.DataFrame(
        {
            "rpt_rec_num": [1, 2],
            "wksht_cd": ["S200001", "S200001"],
            "line_num": ["00300", "00300"],
            "clmn_num": ["00100", "00100"],
            "itm_val_str": ["Hospital A", "Hospital B"],
        }
    )
    return HcrisFiles(rpt=rpt, nmrc=nmrc, alpha=alpha)


def _dictionary() -> tuple[Variable, ...]:
    return (
        Variable("hospital_name", "alpha", "string", "S200001", "00300", "00100", ""),
        Variable("total_beds", "nmrc", "int", "S300001", "01400", "00200", ""),
        Variable("net_patient_revenue", "nmrc", "currency_usd", "G300000", "00300", "00100", ""),
    )


def test_pivot_produces_one_row_per_report() -> None:
    wide = pivot_wide(_files(), _dictionary())
    assert len(wide) == 2
    assert set(wide["rpt_rec_num"]) == {1, 2}


def test_pivot_exposes_variable_columns() -> None:
    wide = pivot_wide(_files(), _dictionary())
    assert "hospital_name" in wide.columns
    assert "total_beds" in wide.columns
    assert "net_patient_revenue" in wide.columns


def test_pivot_values_line_up_per_report() -> None:
    wide = pivot_wide(_files(), _dictionary()).set_index("rpt_rec_num")
    assert wide.loc[1, "hospital_name"] == "Hospital A"
    assert wide.loc[1, "total_beds"] == 450.0
    assert wide.loc[1, "net_patient_revenue"] == 10_000_000.0
    assert wide.loc[2, "hospital_name"] == "Hospital B"
    assert wide.loc[2, "total_beds"] == 200.0
    # Report 2 has no G300000 row → net_patient_revenue should be NaN
    assert pd.isna(wide.loc[2, "net_patient_revenue"])


def test_pivot_preserves_rpt_metadata() -> None:
    wide = pivot_wide(_files(), _dictionary())
    assert "prvdr_num" in wide.columns
    assert "fy_bgn_dt" in wide.columns
    assert "fy_end_dt" in wide.columns
