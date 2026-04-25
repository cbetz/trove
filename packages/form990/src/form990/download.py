"""Fetch IRS 990 bulk XML ZIPs and the per-year index CSV."""

from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

IRS_BASE: str = "https://apps.irs.gov/pub/epostcard/990/xml"
USER_AGENT: str = "trove/form990 (+https://github.com/cbetz/trove)"


def index_url(release_year: int) -> str:
    """URL for the IRS index CSV listing all e-filed returns released in ``release_year``."""
    return f"{IRS_BASE}/{release_year}/index_{release_year}.csv"


def zip_url(release_year: int, batch_id: str) -> str:
    """URL for one bulk XML ZIP. ``batch_id`` is e.g. ``"2024_TEOS_XML_01A"``."""
    return f"{IRS_BASE}/{release_year}/{batch_id}.zip"


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


def _download(url: str, target: Path, force: bool) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        return target
    req = Request(url, headers={"User-Agent": USER_AGENT})
    tmp = target.with_suffix(target.suffix + ".partial")
    with urlopen(req) as resp, tmp.open("wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
    tmp.replace(target)
    return target
