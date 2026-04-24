"""Parse the three headerless CSVs inside a Hospital 2552-10 fiscal-year ZIP."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from hcris.schema import ALPHA_COLUMNS, NMRC_COLUMNS, RPT_COLUMNS

_DTYPES: dict[str, str] = {
    "rpt_rec_num": "int64",
    "prvdr_ctrl_type_cd": "Int8",
    "prvdr_num": "string",
    "npi": "string",
    "rpt_stus_cd": "Int8",
    "initl_rpt_sw": "string",
    "last_rpt_sw": "string",
    "trnsmtl_num": "string",
    "fi_num": "Int32",
    "adr_vndr_cd": "Int8",
    "util_cd": "string",
    "spec_ind": "string",
    "wksht_cd": "string",
    "line_num": "string",
    "clmn_num": "string",
    "itm_val_str": "string",
}

_DATE_COLUMNS: tuple[str, ...] = (
    "fy_bgn_dt",
    "fy_end_dt",
    "proc_dt",
    "fi_creat_dt",
    "npr_dt",
    "fi_rcpt_dt",
)


@dataclass(frozen=True)
class HcrisFiles:
    """The three CSVs from one Hospital 2552-10 fiscal-year ZIP, as DataFrames."""

    rpt: pd.DataFrame
    nmrc: pd.DataFrame
    alpha: pd.DataFrame


def parse_zip(zip_path: Path | str) -> HcrisFiles:
    """Read RPT, NMRC, and ALPHA CSVs from a HOSP10FY<year>.zip into DataFrames."""
    path = Path(zip_path)
    with zipfile.ZipFile(path) as zf:
        rpt = _read_member(zf, "_RPT.CSV", RPT_COLUMNS)
        nmrc = _read_member(zf, "_NMRC.CSV", NMRC_COLUMNS)
        alpha = _read_member(zf, "_ALPHA.CSV", ALPHA_COLUMNS)

    for df in (nmrc, alpha):
        df["wksht_cd"] = df["wksht_cd"].str.strip()

    for col in _DATE_COLUMNS:
        rpt[col] = pd.to_datetime(rpt[col], format="%m/%d/%Y", errors="coerce")

    return HcrisFiles(rpt=rpt, nmrc=nmrc, alpha=alpha)


def _read_member(
    zf: zipfile.ZipFile,
    suffix: str,
    columns: tuple[str, ...],
) -> pd.DataFrame:
    name = next((n for n in zf.namelist() if n.upper().endswith(suffix)), None)
    if name is None:
        raise ValueError(f"ZIP {zf.filename!r} is missing a file ending in {suffix!r}")
    dtypes = {col: _DTYPES[col] for col in columns if col in _DTYPES}
    with zf.open(name) as f:
        return pd.read_csv(
            f,
            names=list(columns),
            header=None,
            encoding="latin-1",
            dtype=dtypes,
            low_memory=False,
        )
