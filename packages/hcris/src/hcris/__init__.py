"""Parser for CMS Medicare Cost Reports (HCRIS) — Hospital 2552-10 form."""

from hcris.dictionary import Variable, load_dictionary
from hcris.download import download_year, hospital_2552_10_url
from hcris.parquet import write_parquet
from hcris.parse import HcrisFiles, parse_zip
from hcris.pivot import pivot_wide
from hcris.resolve import resolve_alpha, resolve_numeric

__version__ = "0.2.0"

__all__ = [
    "HcrisFiles",
    "Variable",
    "__version__",
    "download_year",
    "hospital_2552_10_url",
    "load_dictionary",
    "parse_zip",
    "pivot_wide",
    "resolve_alpha",
    "resolve_numeric",
    "write_parquet",
]
