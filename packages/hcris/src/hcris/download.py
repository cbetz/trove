"""Fetch Hospital 2552-10 fiscal-year ZIPs from CMS with local file caching."""

from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

CMS_BASE: str = "https://downloads.cms.gov/Files/hcris"
USER_AGENT: str = "trove/hcris (+https://github.com/cbetz/trove)"


def hospital_2552_10_url(year: int) -> str:
    """CMS download URL for the Hospital 2552-10 form ZIP for a given fiscal year."""
    return f"{CMS_BASE}/HOSP10FY{year}.zip"


def download_year(
    year: int,
    cache_dir: Path | str = "data/raw/hcris",
    *,
    force: bool = False,
) -> Path:
    """Download a Hospital 2552-10 fiscal-year ZIP to cache_dir and return its path.

    Reuses the cached file if present unless ``force=True``.

    CMS rebuilds every yearly ZIP on each quarterly release, so in the long run you
    will want a freshness check (Last-Modified / content hash). For now, caller-controlled
    ``force`` is enough — add conditional refresh when it starts to bite.
    """
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"HOSP10FY{year}.zip"
    if target.exists() and not force:
        return target

    url = hospital_2552_10_url(year)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    tmp = target.with_suffix(".zip.partial")
    with urlopen(req) as resp, tmp.open("wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
    tmp.replace(target)
    return target
