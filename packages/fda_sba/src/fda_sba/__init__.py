"""FDA novel drug approvals — index + document links."""

from fda_sba.scrape import build_index, fetch_nme_year_html, scrape_nme_year

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "build_index",
    "fetch_nme_year_html",
    "scrape_nme_year",
]
