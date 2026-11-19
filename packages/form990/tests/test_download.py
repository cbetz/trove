from pathlib import Path
from urllib.error import HTTPError, URLError

import form990.download as dl
import pytest
from form990.download import discover_batches, download_index, download_zip, index_url, zip_url


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


class _Resp:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> "_Resp":
        return self

    def __exit__(self, *exc) -> None:
        return None


def _http_error(url: str, code: int) -> HTTPError:
    return HTTPError(url, code, "x", None, None)  # type: ignore[arg-type]


def _script(monkeypatch, outcomes: list) -> list[str]:
    """Make ``urlopen`` play back ``outcomes`` (a status code or an exception) in order."""
    calls: list[str] = []
    queue = list(outcomes)

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        nxt = queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return _Resp(nxt)

    monkeypatch.setattr(dl, "urlopen", fake_urlopen)
    monkeypatch.setattr(dl.time, "sleep", lambda s: None)
    return calls


def test_probe_200_exists_and_404_does_not(monkeypatch) -> None:
    url = zip_url(2025, "2025_TEOS_XML_01A")
    _script(monkeypatch, [200])
    assert dl._exists(url) is True
    calls = _script(monkeypatch, [_http_error(url, 404)])
    assert dl._exists(url) is False
    assert len(calls) == 1  # a 404 is an answer; no retry


@pytest.mark.parametrize("code", [403, 429, 500, 503])
def test_probe_does_not_read_throttling_or_server_errors_as_absent(monkeypatch, code) -> None:
    """A 403 from a throttling server used to be read as "this ZIP does not exist",
    which would silently cut ZIP discovery short."""
    url = zip_url(2025, "2025_TEOS_XML_01A")
    calls = _script(monkeypatch, [_http_error(url, code)] * 4)
    with pytest.raises(OSError, match=str(code)):
        dl._exists(url)
    assert len(calls) == 4


def test_probe_retries_then_succeeds(monkeypatch) -> None:
    url = zip_url(2025, "2025_TEOS_XML_01A")
    calls = _script(monkeypatch, [_http_error(url, 403), URLError("reset"), 200])
    assert dl._exists(url) is True
    assert len(calls) == 3
    calls = _script(monkeypatch, [_http_error(url, 503), _http_error(url, 404)])
    assert dl._exists(url) is False
    assert len(calls) == 2


def test_discovery_fails_loudly_instead_of_returning_a_short_list(monkeypatch) -> None:
    def fake_urlopen(req, timeout=None):
        name = req.full_url.rsplit("/", 1)[1]
        if name == "2025_TEOS_XML_01A.zip":
            return _Resp(200)
        if name == "2025_TEOS_XML_01B.zip":
            raise _http_error(req.full_url, 404)
        raise _http_error(req.full_url, 403)  # throttled from February on

    monkeypatch.setattr(dl, "urlopen", fake_urlopen)
    monkeypatch.setattr(dl.time, "sleep", lambda s: None)
    with pytest.raises(OSError, match="403"):
        discover_batches(2025)
