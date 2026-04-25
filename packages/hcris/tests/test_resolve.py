import pandas as pd
import pytest
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


def test_resolve_range_sums_across_lines() -> None:
    """Range variables expand to every line in [line_num, line_num_end] and sum per report."""
    range_var = Variable(
        name="total_icu_beds",
        source="nmrc",
        type="int",
        wksht_cd="S300001",
        line_num="00800",
        clmn_num="00200",
        description="",
        line_num_end="00899",
        aggregation="sum",
    )
    nmrc = pd.DataFrame(
        {
            # Report 1 has two rows in the ICU line range; report 2 has one.
            "rpt_rec_num": [1, 1, 2, 1],
            "wksht_cd": ["S300001", "S300001", "S300001", "S300001"],
            "line_num": ["00800", "00801", "00800", "00900"],  # 00900 is outside range
            "clmn_num": ["00200", "00200", "00200", "00200"],
            "itm_val_num": [10.0, 5.0, 20.0, 100.0],
        }
    )
    resolved = resolve_numeric(nmrc, (range_var,)).set_index("rpt_rec_num")
    assert resolved.loc[1, "value"] == 15.0  # 10 + 5, not 100 (out of range)
    assert resolved.loc[2, "value"] == 20.0


def test_resolve_range_requires_sum_aggregation() -> None:
    bad_range = Variable(
        name="x",
        source="nmrc",
        type="currency_usd",
        wksht_cd="S",
        line_num="00100",
        clmn_num="00100",
        description="",
        line_num_end="00200",
        aggregation="mean",
    )
    nmrc = pd.DataFrame(
        {
            "rpt_rec_num": [1],
            "wksht_cd": ["S"],
            "line_num": ["00150"],
            "clmn_num": ["00100"],
            "itm_val_num": [42.0],
        }
    )
    with pytest.raises(ValueError, match="aggregation"):
        resolve_numeric(nmrc, (bad_range,))


def test_resolve_mixed_scalar_and_range() -> None:
    """A dictionary with both scalar and range entries resolves both correctly."""
    scalar = Variable("total_beds", "nmrc", "int", "S300001", "01400", "00200", "")
    rng = Variable(
        "icu_beds",
        "nmrc",
        "int",
        "S300001",
        "00800",
        "00200",
        "",
        line_num_end="00899",
        aggregation="sum",
    )
    nmrc = pd.DataFrame(
        {
            "rpt_rec_num": [1, 1, 1],
            "wksht_cd": ["S300001", "S300001", "S300001"],
            "line_num": ["01400", "00800", "00801"],
            "clmn_num": ["00200", "00200", "00200"],
            "itm_val_num": [400.0, 12.0, 8.0],
        }
    )
    resolved = resolve_numeric(nmrc, (scalar, rng)).set_index("variable_name")
    assert resolved.loc["total_beds", "value"] == 400.0
    assert resolved.loc["icu_beds", "value"] == 20.0
