"""Refresh the bundled CBI crosswalk by re-downloading from the CBI API.

The Community Benefit Insight project (RTI International, funded by RWJF)
published an API serving a CCN <-> EIN mapping for U.S. nonprofit hospitals,
derived from CMS HCRIS, IRS Form 990, and AHA Annual Survey. RTI's funding
ended Jan 15 2025; the API is currently still live but frozen at the Dec 6
2024 vintage. Mirror this artifact while it's reachable.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

CBI_URL: str = "https://www.communitybenefitinsight.org/api/get_hospitals.php"
USER_AGENT: str = "trove/crosswalk (+https://github.com/cbetz/trove)"


def refresh_from_cbi(out_path: Path | str) -> Path:
    """Download the CBI hospital list and write a tidy crosswalk Parquet."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = _fetch_cbi()
    df = _normalize(json.loads(blob))
    df.to_parquet(out_path, index=False)
    return out_path


def _fetch_cbi() -> bytes:
    req = Request(CBI_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp:
        return resp.read()


_FLAG_MAP = {"Y": True, "N": False, "": pd.NA}


def _normalize(records: list[dict]) -> pd.DataFrame:
    raw = pd.DataFrame.from_records(records)
    return pd.DataFrame(
        {
            # CCN comes through as 6 digits in CBI; HCRIS RPT also stores it as a 6-digit
            # provider number. Keep as string to preserve leading zeros.
            "ccn": raw["medicare_provider_number"].str.zfill(6).astype("string"),
            "ein": raw["ein"].str.zfill(9).astype("string"),
            "hospital_name": raw["name"].astype("string"),
            "hospital_name_cost_report": raw["name_cr"].astype("string"),
            "street_address": raw["street_address"].astype("string"),
            "city": raw["city"].astype("string"),
            "state": raw["state"].astype("string"),
            "zip_code": raw["zip_code"].astype("string"),
            "county": raw["county"].astype("string"),
            "county_fips": raw["fips_state_and_county_code"].str.zfill(5).astype("string"),
            "bed_count": pd.to_numeric(raw["hospital_bed_count"], errors="coerce").astype("Int64"),
            "bed_size_band": raw["hospital_bed_size"].astype("string"),
            "urban": raw["urban_location_f"].map(_FLAG_MAP).astype("boolean"),
            "children_hospital": raw["children_hospital_f"].map(_FLAG_MAP).astype("boolean"),
            "teaching_hospital": raw["memb_counc_teach_hosps_f"].map(_FLAG_MAP).astype("boolean"),
            "church_affiliated": raw["chrch_affl_f"].map(_FLAG_MAP).astype("boolean"),
            "source": "cbi",
            "vintage": pd.to_datetime(raw["updated_dt"]).iloc[0].date().isoformat(),
        }
    )
