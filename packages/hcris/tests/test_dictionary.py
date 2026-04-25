import pytest
from hcris.dictionary import Variable, _pad, _validate, load_dictionary


def test_load_returns_tuple() -> None:
    dictionary = load_dictionary("2552-10")
    assert isinstance(dictionary, tuple)
    assert len(dictionary) >= 15


def test_loaded_variables_have_padded_codes() -> None:
    dictionary = load_dictionary("2552-10")
    # line_num 300 should become "00300"
    net_patient = next(v for v in dictionary if v.name == "net_patient_revenue")
    assert net_patient.line_num == "00300"
    assert net_patient.clmn_num == "00100"


def test_loaded_variables_are_immutable() -> None:
    dictionary = load_dictionary("2552-10")
    with pytest.raises(Exception):  # noqa: B017 -- dataclass frozen raises FrozenInstanceError
        dictionary[0].name = "mutated"


def test_pad_zero_pads_ints() -> None:
    assert _pad(1) == "00001"
    assert _pad(1400) == "01400"
    assert _pad(14100) == "14100"


def test_pad_passes_through_strings() -> None:
    assert _pad("04A00") == "04A00"


def test_validate_rejects_duplicate_names() -> None:
    vars = (
        Variable("x", "nmrc", "int", "S1", "00100", "00200", ""),
        Variable("x", "nmrc", "int", "S1", "00100", "00300", ""),
    )
    with pytest.raises(ValueError, match="duplicate"):
        _validate(vars)


def test_validate_rejects_bad_source() -> None:
    vars = (Variable("x", "weird", "int", "S1", "00100", "00200", ""),)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="source"):
        _validate(vars)


def test_validate_rejects_range_without_aggregation() -> None:
    vars = (
        Variable(
            name="x",
            source="nmrc",
            type="currency_usd",
            wksht_cd="S1",
            line_num="02500",
            clmn_num="00200",
            description="",
            line_num_end="03099",
            aggregation=None,
        ),
    )
    with pytest.raises(ValueError, match="aggregation"):
        _validate(vars)


def test_default_form_is_2552_10() -> None:
    a = load_dictionary()
    b = load_dictionary("2552-10")
    assert a == b
