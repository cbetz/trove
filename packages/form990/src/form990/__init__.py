"""Parser for IRS Form 990 — scoped to Schedule H (hospital community benefit)."""

from form990.download import download_index, download_zip, index_url, zip_url
from form990.index import filter_990s_for_tax_year, read_index
from form990.parquet import write_parquet
from form990.parse import iter_schedule_h_filings, parse_zip
from form990.schedule_h import OUTPUT_COLUMNS, PART_I_LINE_GROUPS

__version__ = "0.1.0"

__all__ = [
    "OUTPUT_COLUMNS",
    "PART_I_LINE_GROUPS",
    "__version__",
    "download_index",
    "download_zip",
    "filter_990s_for_tax_year",
    "index_url",
    "iter_schedule_h_filings",
    "parse_zip",
    "read_index",
    "write_parquet",
    "zip_url",
]
