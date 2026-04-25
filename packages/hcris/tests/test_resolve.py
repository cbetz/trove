import pandas as pd
from hcris.dictionary import Variable
from hcris.resolve import resolve_alpha, resolve_numeric


def _single_var(name: str, source: str, wksht_cd: str, line_num: str, clmn_num: str) -> Variable:
    return Variable(
        name=name,
        source=source,  # type: ignore[arg-type]
        type="int",
        wksht_cd=wksht_cd,
        line_num=line_num,
        clmn_num=clmn_num,
        description="",
    )


def test_resolve_numeric_filters_to_matching_rows() -> None:
    nmrc = pd.DataFrame(
        {
            "rpt_rec_num": [1, 1, 2],
            "wksht_cd": ["S300001", "G300000", "S300001"],
            "line_num": ["01400", "00300", "01400"],
            "clmn_num": ["00200", "00100", "00200"],
            "itm_val_num": [450.0, 1_000_000.0, 200.0],
        }
    )
    dictionary = (_single_var("total_beds", "nmrc", "S300001", "01400", "00200"),)
    resolved = resolve_numeric(nmrc, dictionary)
    assert len(resolved) == 2
    assert set(resolved["variable_name"]) == {"total_beds"}
    assert resolved["value"].tolist() == [450.0, 200.0]


def test_resolve_numeric_drops_unmatched() -> None:
    nmrc = pd.DataFrame(
        {
            "rpt_rec_num": [1],
            "wksht_cd": ["X"],
            "line_num": ["00001"],
            "clmn_num": ["00001"],
            "itm_val_num": [42.0],
        }
    )
    dictionary = (_single_var("foo", "nmrc", "S3", "00001", "00001"),)
    resolved = resolve_numeric(nmrc, dictionary)
    assert resolved.empty


def test_resolve_numeric_ignores_alpha_source() -> None:
    nmrc = pd.DataFrame(
        {
            "rpt_rec_num": [1],
            "wksht_cd": ["S200001"],
            "line_num": ["00300"],
            "clmn_num": ["00100"],
            "itm_val_num": [0.0],
        }
    )
    dictionary = (_single_var("hospital_name", "alpha", "S200001", "00300", "00100"),)
    resolved = resolve_numeric(nmrc, dictionary)
    assert resolved.empty


def test_resolve_alpha_filters_to_matching_rows() -> None:
    alpha = pd.DataFrame(
        {
            "rpt_rec_num": [1, 2],
            "wksht_cd": ["S200001", "S200001"],
            "line_num": ["00300", "00300"],
            "clmn_num": ["00100", "00100"],
            "itm_val_str": ["Hospital A", "Hospital B"],
        }
    )
    dictionary = (_single_var("hospital_name", "alpha", "S200001", "00300", "00100"),)
    resolved = resolve_alpha(alpha, dictionary)
    assert resolved["value"].tolist() == ["Hospital A", "Hospital B"]


def test_resolve_skips_range_variables() -> None:
    """Range variables require aggregation — not implemented yet, should be skipped."""
    range_var = Variable(
        name="range_sum",
        source="nmrc",
        type="currency_usd",
        wksht_cd="D30A180",
        line_num="03000",
        clmn_num="00200",
        description="",
        line_num_end="03599",
        aggregation="sum",
    )
    nmrc = pd.DataFrame(
        {
            "rpt_rec_num": [1],
            "wksht_cd": ["D30A180"],
            "line_num": ["03100"],
            "clmn_num": ["00200"],
            "itm_val_num": [500.0],
        }
    )
    resolved = resolve_numeric(nmrc, (range_var,))
    assert resolved.empty
