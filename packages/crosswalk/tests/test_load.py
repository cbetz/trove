from crosswalk import load_seed


def test_load_seed_returns_dataframe() -> None:
    df = load_seed()
    assert len(df) > 3000


def test_seed_has_unique_ccns() -> None:
    df = load_seed()
    assert df["ccn"].is_unique


def test_seed_required_columns() -> None:
    df = load_seed()
    expected = {
        "ccn",
        "ein",
        "hospital_name",
        "city",
        "state",
        "bed_count",
        "teaching_hospital",
        "source",
        "vintage",
    }
    assert expected.issubset(set(df.columns))


def test_ccn_is_zero_padded_to_6_chars() -> None:
    df = load_seed()
    assert (df["ccn"].str.len() == 6).all()


def test_ein_is_zero_padded_to_9_chars() -> None:
    df = load_seed()
    assert (df["ein"].str.len() == 9).all()


def test_known_hospital_resolves() -> None:
    """NY-Presbyterian (CCN 330101) is a useful canary."""
    df = load_seed()
    nyp = df[df["ccn"] == "330101"]
    assert len(nyp) == 1
    assert nyp.iloc[0]["ein"] == "133957095"
    assert "PRESBYTERIAN" in nyp.iloc[0]["hospital_name"].upper()
    assert nyp.iloc[0]["state"] == "NY"
