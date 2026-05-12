"""FDA novel drug approvals — index + document links."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from fda_sba.cber import build_cber_index
from fda_sba.overview import (
    enrich_with_sponsor,
    fetch_application_overview,
    parse_sponsor,
)
from fda_sba.scrape import build_index as build_cder_index
from fda_sba.scrape import fetch_nme_year_html, scrape_nme_year

__version__ = "0.3.0"


def build_index(
    years: Iterable[int],
    cache_dir: Path | str = "data/raw/fda",
    *,
    include_cber: bool = True,
) -> pd.DataFrame:
    """Build the combined FDA novel-approvals index (CDER + CBER).

    CDER comes from FDA's annual Novel Drug Approvals pages
    (small molecules + most antibody biologics). CBER comes from the
    Approved Cellular and Gene Therapy Products page (gene therapies,
    cell therapies, etc.). Each row carries a ``regulatory_center`` of
    either ``"CDER"`` or ``"CBER"``.
    """
    cder = build_cder_index(years, cache_dir=cache_dir)
    cder = enrich_with_sponsor(cder, cache_dir=Path(cache_dir) / "overview")
    cder["regulatory_center"] = "CDER"

    if not include_cber:
        return cder

    cber = build_cber_index(years=set(years), cache_dir=Path(cache_dir) / "cber")
    if cber.empty:
        return cder

    combined = pd.concat([cder, cber], ignore_index=True)
    return combined.sort_values(["year", "approval_date"], ascending=[False, False]).reset_index(
        drop=True
    )


__all__ = [
    "__version__",
    "build_cber_index",
    "build_cder_index",
    "build_index",
    "enrich_with_sponsor",
    "fetch_application_overview",
    "fetch_nme_year_html",
    "parse_sponsor",
    "scrape_nme_year",
]
