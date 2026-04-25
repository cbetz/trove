"""Constants and column orderings for the IRS Form 990 e-file XML format."""

from __future__ import annotations

from typing import Final

NAMESPACE: Final[str] = "http://www.irs.gov/efile"
NS_MAP: Final[dict[str, str]] = {"e": NAMESPACE}

# Columns from the IRS index CSV (one row per filing in the bulk feed).
# https://apps.irs.gov/pub/epostcard/990/xml/{year}/index_{year}.csv
INDEX_COLUMNS: Final[tuple[str, ...]] = (
    "RETURN_ID",
    "FILING_TYPE",
    "EIN",
    "TAX_PERIOD",
    "SUB_DATE",
    "TAXPAYER_NAME",
    "RETURN_TYPE",
    "DLN",
    "OBJECT_ID",
    "XML_BATCH_ID",
)

RETURN_TYPE_990: Final[str] = "990"
