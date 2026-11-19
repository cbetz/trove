"""Fetch IRS 990 bulk XML ZIPs and the per-year index CSV."""

from __future__ import annotations

import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

IRS_BASE: str = "https://apps.irs.gov/pub/epostcard/990/xml"
USER_AGENT: str = "trove/form990 (+https://github.com/cbetz/trove)"


def index_url(release_year: int) -> str:
    """URL for the IRS index CSV listing all e-filed returns released in ``release_year``."""
    return f"{IRS_BASE}/{release_year}/index_{release_year}.csv"


def zip_url(release_year: int, batch_id: str) -> str:
    """URL for one bulk XML ZIP. ``batch_id`` is e.g. ``"2024_TEOS_XML_01A"``."""
    return f"{IRS_BASE}/{release_year}/{batch_id}.zip"


def batch_id(release_year: int, month: int, letter: str) -> str:
    """Bulk ZIP id, e.g. ``batch_id(2025, 5, "B") == "2025_TEOS_XML_05B"``."""
    return f"{release_year}_TEOS_XML_{month:02d}{letter}"


def discover_batches(release_year: int, *, max_letters: int = 8) -> list[str]:
    """Probe the IRS server for every bulk ZIP published for ``release_year``.

    The index CSV cannot be trusted to enumerate ZIPs: the 2023 index has no
    batch column at all, and the 2025/2026 indexes label every May return ``05A``
    although the returns are split across ``05A`` and ``05B``. So ask the server:
    for each month 01-12 try letters A, B, C… and stop at the first one that is
    not there (HTTP 404). Any other failure is retried and then raised — see
    ``_exists`` — so a throttled probe can never shorten the list.
    """
    found: list[str] = []
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:max_letters]
    for month in range(1, 13):
        for letter in letters:
            bid = batch_id(release_year, month, letter)
            if not _exists(zip_url(release_year, bid)):
                break
            found.append(bid)
    return found


def _exists(url: str, *, attempts: int = 4) -> bool:
    """Whether the IRS serves ``url``. Only a 404 means "this ZIP does not exist".

    Anything else that is not a 200 (403 when the server throttles, 429, 5xx, a
    dropped connection) says nothing about existence. Reading it as "absent"
    would silently end ZIP discovery early and drop every later return, so those
    are retried with a back-off and then raised.
    """
    req = Request(url, headers={"User-Agent": USER_AGENT}, method="HEAD")
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(req, timeout=60) as resp:
                if resp.status == 200:
                    return True
                error: Exception = OSError(f"unexpected HTTP {resp.status} probing {url}")
        except HTTPError as e:
            if e.code == 404:
                return False
            error = OSError(f"HTTP {e.code} probing {url}; cannot tell whether it exists")
        except (OSError, TimeoutError) as e:
            error = e
        if attempt < attempts:
            time.sleep(5 * attempt)
    raise error


def download_index(
    release_year: int,
    cache_dir: Path | str = "data/raw/form990",
    *,
    force: bool = False,
) -> Path:
    """Download the per-release-year index CSV and return its local path."""
    return _download(index_url(release_year), Path(cache_dir) / f"index_{release_year}.csv", force)


def download_zip(
    release_year: int,
    batch_id: str,
    cache_dir: Path | str = "data/raw/form990",
    *,
    force: bool = False,
) -> Path:
    """Download one bulk XML ZIP and return its local path."""
    return _download(zip_url(release_year, batch_id), Path(cache_dir) / f"{batch_id}.zip", force)


def _download(url: str, target: Path, force: bool, *, attempts: int = 4) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        return target
    req = Request(url, headers={"User-Agent": USER_AGENT})
    tmp = target.with_suffix(target.suffix + ".partial")
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(req, timeout=120) as resp, tmp.open("wb") as f:
                expected = resp.headers.get("Content-Length")
                while chunk := resp.read(1 << 20):
                    f.write(chunk)
            if expected is not None and tmp.stat().st_size != int(expected):
                raise OSError(f"short download: {tmp.stat().st_size} of {expected} bytes")
            break
        except (OSError, TimeoutError):
            tmp.unlink(missing_ok=True)
            if attempt == attempts:
                raise
            time.sleep(5 * attempt)
    tmp.replace(target)
    return target
