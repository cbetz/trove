"""FDA novel drug approvals — index + document links."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from fda_sba.cber import build_cber_index
from fda_sba.compilation import (
    enrich_with_designations,
    fetch_compilation,
    parse_compilation,
    read_source_metadata,
)
from fda_sba.overview import (
    enrich_with_approval_documents,
    enrich_with_sponsor,
    fetch_application_overview,
    parse_original_approval_date,
    parse_original_approval_documents,
    parse_sponsor,
    reconcile_approval_dates,
)
from fda_sba.scrape import build_index as build_cder_index
from fda_sba.scrape import fetch_nme_year_html, scrape_nme_year

__version__ = "0.4.0"


def build_index(
    years: Iterable[int],
    cache_dir: Path | str = "data/raw/fda",
    *,
    include_cber: bool = True,
    compilation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the combined FDA novel-approvals index (CDER + CBER).

    CDER comes from FDA's annual Novel Drug Approvals pages
    (small molecules + most antibody biologics). CBER comes from the
    Approved Cellular and Gene Therapy Products page (gene therapies,
    cell therapies, etc.). Each row carries a ``regulatory_center`` of
    either ``"CDER"`` or ``"CBER"``.

    CDER rows also carry the documents FDA posted with the original approval
    (approval letter, review package, label) from drugs@FDA, and the regulatory
    characteristics FDA records in its NME compilation (review designation,
    orphan, accelerated approval, breakthrough, fast track). Pass an already
    parsed ``compilation`` to avoid reading the spreadsheet twice. CBER rows
    have none of these: neither source covers CBER products.
    """
    cder = build_cder_index(years, cache_dir=cache_dir)
    cder = enrich_with_sponsor(cder, cache_dir=Path(cache_dir) / "overview")
    cder = reconcile_approval_dates(cder, cache_dir=Path(cache_dir) / "overview")
    cder = enrich_with_approval_documents(cder, cache_dir=Path(cache_dir) / "overview")
    if compilation is None:
        compilation = parse_compilation(fetch_compilation(Path(cache_dir) / "compilation"))
    cder = enrich_with_designations(cder, compilation)
    cder = cder.sort_values(["year", "approval_date"], ascending=[False, False]).reset_index(
        drop=True
    )
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
    "enrich_with_approval_documents",
    "enrich_with_designations",
    "enrich_with_sponsor",
    "fetch_application_overview",
    "fetch_compilation",
    "fetch_nme_year_html",
    "parse_compilation",
    "parse_original_approval_date",
    "parse_original_approval_documents",
    "parse_sponsor",
    "read_source_metadata",
    "reconcile_approval_dates",
    "scrape_nme_year",
]
