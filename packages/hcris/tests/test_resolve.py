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


def test_s10_alias_resolves_old_and_new_worksheet_codes() -> None:
    """Worksheet S-10 is S100000 for periods beginning before 2022-10-01 and
    S100001 (Part I) after; one variable must resolve from either. S100002
    (Part II, hospital-CCN-only subset) must NOT be picked up."""
    nmrc = pd.DataFrame(
        {
            "rpt_rec_num": [1, 2, 2, 3],
            "wksht_cd": ["S100000", "S100001", "S100002", "S100002"],
            "line_num": ["02300", "02300", "02300", "02300"],
            "clmn_num": ["00300", "00300", "00300", "00300"],
            "itm_val_num": [32_528_304.0, 35_568_680.0, 30_000_000.0, 1.0],
        }
    )
    var = Variable(
        name="charity_care_cost",
        source="nmrc",
        type="currency_usd",
        wksht_cd="S100001",
        line_num="02300",
        clmn_num="00300",
        description="",
        wksht_cd_aliases=("S100000",),
    )
    resolved = resolve_numeric(nmrc, (var,)).set_index("rpt_rec_num")["value"]
    assert resolved.to_dict() == {1: 32_528_304.0, 2: 35_568_680.0}


def test_report_with_both_worksheet_codes_is_not_double_counted() -> None:
    """No report in FY2022-FY2024 carries S100000 and S100001 together, but if one
    did, summing them would double the figure. The primary code wins, loudly."""
    nmrc = pd.DataFrame(
        {
            "rpt_rec_num": [1, 1, 2, 3, 3, 3, 3],
            "wksht_cd": [
                "S100001", "S100000", "S100000", "S100000", "S100000", "S100001", "S100001",
            ],
            "line_num": ["02300", "02300", "02300", "00700", "00800", "00700", "00800"],
            "clmn_num": ["00300"] * 7,
            "itm_val_num": [35_000_000.0, 32_000_000.0, 7.0, 1.0, 2.0, 10.0, 20.0],
        }
    )  # fmt: skip
    common = dict(source="nmrc", type="currency_usd", clmn_num="00300", description="")
    scalar = Variable(
        name="charity_care_cost",
        wksht_cd="S100001",
        line_num="02300",
        wksht_cd_aliases=("S100000",),
        **common,
    )
    rng = Variable(
        name="ranged",
        wksht_cd="S100001",
        line_num="00700",
        line_num_end="00800",
        aggregation="sum",
        wksht_cd_aliases=("S100000",),
        **common,
    )
    with pytest.warns(RuntimeWarning, match="more than one worksheet"):
        resolved = resolve_numeric(nmrc, (scalar, rng))
    got = resolved.set_index(["rpt_rec_num", "variable_name"])["value"].to_dict()
    assert got == {
        (1, "charity_care_cost"): 35_000_000.0,  # primary only, not 67M
        (2, "charity_care_cost"): 7.0,  # alias alone still resolves
        (3, "ranged"): 30.0,  # the primary worksheet's range, not 33
    }
    assert list(resolved.columns) == ["rpt_rec_num", "variable_name", "value"]


def test_single_worksheet_reports_resolve_without_a_warning() -> None:
    import warnings

    nmrc = pd.DataFrame(
        {
            "rpt_rec_num": [1, 2],
            "wksht_cd": ["S100000", "S100001"],
            "line_num": ["02300", "02300"],
            "clmn_num": ["00300", "00300"],
            "itm_val_num": [1.0, 2.0],
        }
    )
    var = Variable(
        name="charity_care_cost",
        source="nmrc",
        type="currency_usd",
        wksht_cd="S100001",
        line_num="02300",
        clmn_num="00300",
        description="",
        wksht_cd_aliases=("S100000",),
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        resolved = resolve_numeric(nmrc, (var,))
    assert resolved["value"].tolist() == [1.0, 2.0]


def test_every_s10_variable_in_the_shipped_dictionary_is_aliased() -> None:
    from hcris.dictionary import load_dictionary

    s10 = [v for v in load_dictionary() if v.wksht_cd.startswith("S10")]
    assert len(s10) >= 18
    for v in s10:
        assert v.wksht_cd == "S100001", v.name
        assert v.wksht_cd_aliases == ("S100000",), v.name
    by_name = {v.name: v for v in s10}
    # PRM 15-2 ch. 40 section 4012: line 23 col 3 cost of charity care; line 5
    # Medicaid DSH/supplemental payments net of provider taxes.
    assert (by_name["charity_care_cost"].line_num, by_name["charity_care_cost"].clmn_num) == (
        "02300",
        "00300",
    )
    assert by_name["charity_care_cost_uninsured"].clmn_num == "00100"
    assert by_name["charity_care_cost_insured"].clmn_num == "00200"
    line5 = by_name["medicaid_dsh_supplemental_payments"]
    assert (line5.line_num, line5.clmn_num) == ("00500", "00100")
