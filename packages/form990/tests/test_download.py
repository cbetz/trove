from pathlib import Path

from form990.download import download_index, download_zip, index_url, zip_url


def test_index_url() -> None:
    assert index_url(2024) == "https://apps.irs.gov/pub/epostcard/990/xml/2024/index_2024.csv"


def test_zip_url() -> None:
    assert zip_url(2024, "2024_TEOS_XML_01A") == (
        "https://apps.irs.gov/pub/epostcard/990/xml/2024/2024_TEOS_XML_01A.zip"
    )


def test_download_index_uses_cache(tmp_path: Path) -> None:
    cached = tmp_path / "index_2024.csv"
    cached.write_bytes(b"cached")
    assert download_index(2024, cache_dir=tmp_path) == cached
    assert cached.read_bytes() == b"cached"


def test_download_zip_uses_cache(tmp_path: Path) -> None:
    cached = tmp_path / "2024_TEOS_XML_01A.zip"
    cached.write_bytes(b"cached")
    assert download_zip(2024, "2024_TEOS_XML_01A", cache_dir=tmp_path) == cached
    assert cached.read_bytes() == b"cached"
