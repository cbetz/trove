from pathlib import Path

from hcris.download import download_year, hospital_2552_10_url


def test_url_pattern() -> None:
    assert hospital_2552_10_url(2023) == ("https://downloads.cms.gov/Files/hcris/HOSP10FY2023.zip")


def test_download_uses_cache_when_present(tmp_path: Path) -> None:
    cached = tmp_path / "HOSP10FY9999.zip"
    cached.write_bytes(b"cached-bytes")
    result = download_year(9999, cache_dir=tmp_path)
    assert result == cached
    assert result.read_bytes() == b"cached-bytes"
