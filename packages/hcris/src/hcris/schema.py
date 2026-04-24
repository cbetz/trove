"""Column definitions for the headerless CMS Medicare Cost Report CSVs.

Source: Sacarny's `import-source-cms.R` in asacarny/hospital-cost-reports.
"""

from __future__ import annotations

from typing import Final

RPT_COLUMNS: Final[tuple[str, ...]] = (
    "rpt_rec_num",
    "prvdr_ctrl_type_cd",
    "prvdr_num",
    "npi",
    "rpt_stus_cd",
    "fy_bgn_dt",
    "fy_end_dt",
    "proc_dt",
    "initl_rpt_sw",
    "last_rpt_sw",
    "trnsmtl_num",
    "fi_num",
    "adr_vndr_cd",
    "fi_creat_dt",
    "util_cd",
    "npr_dt",
    "spec_ind",
    "fi_rcpt_dt",
)

NMRC_COLUMNS: Final[tuple[str, ...]] = (
    "rpt_rec_num",
    "wksht_cd",
    "line_num",
    "clmn_num",
    "itm_val_num",
)

ALPHA_COLUMNS: Final[tuple[str, ...]] = (
    "rpt_rec_num",
    "wksht_cd",
    "line_num",
    "clmn_num",
    "itm_val_str",
)

REPORT_STATUS_CODES: Final[dict[int, str]] = {
    1: "as_submitted",
    2: "settled_without_audit",
    3: "settled_with_audit",
    4: "reopened",
    5: "amended",
}
