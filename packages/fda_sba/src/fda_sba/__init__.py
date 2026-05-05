"""FDA novel drug approvals — index + document links."""

from fda_sba.overview import (
    enrich_with_sponsor,
    fetch_application_overview,
    parse_sponsor,
)
from fda_sba.scrape import build_index, fetch_nme_year_html, scrape_nme_year

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "build_index",
    "enrich_with_sponsor",
    "fetch_application_overview",
    "fetch_nme_year_html",
    "parse_sponsor",
    "scrape_nme_year",
]
