"""FDA's Compilation of CDER NME and New Biologic Approvals (1985 onward).

FDA publishes one spreadsheet listing every new molecular entity and new
biologic approved by the Center for Drug Evaluation and Research since 1985,
with the regulatory characteristics of each application at the time of
original approval: review designation, orphan designation, accelerated
approval, breakthrough therapy, fast track, QIDP and priority review vouchers.

Landing page:
https://www.fda.gov/drugs/drug-approvals-and-databases/compilation-cder-new-molecular-entity-nme-drug-and-new-biologic-approvals

FDA ships it as XLSX only. This module reads that file with the standard
library (an XLSX is a ZIP of XML, so no spreadsheet dependency is needed) and
returns a tidy DataFrame: ISO dates, six-digit application numbers that match
Drugs@FDA, trimmed text, and FDA's own values left as FDA wrote them.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

import pandas as pd

COMPILATION_PAGE_URL = (
    "https://www.fda.gov/drugs/drug-approvals-and-databases/"
    "compilation-cder-new-molecular-entity-nme-drug-and-new-biologic-approvals"
)
COMPILATION_XLSX_URL = "https://www.fda.gov/media/177921/download?attachment"
DATA_DICTIONARY_URL = "https://www.fda.gov/media/177920/download?attachment"
USER_AGENT = "trove/fda_sba (+https://github.com/cbetz/trove)"

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS = {"m": _MAIN}

# FDA's header text (whitespace-normalised) -> published column name.
_COLUMNS = {
    "Proprietary Name": "proprietary_name",
    "Active Ingredient/Moiety": "active_ingredient",
    "Applicant": "applicant",
    "NDA/BLA": "application_type",
    "Application Number(1)": "application_number",
    "Application Number(2)": "application_number_2",
    "Application Number(3)": "application_number_3",
    "Dosage Form(1)": "dosage_form",
    "Route of Administration(1)": "route_of_administration",
    "Dosage Form(2)": "dosage_form_2",
    "Route of Administration(2)": "route_of_administration_2",
    "Dosage Form(3)": "dosage_form_3",
    "Route of Administration(3)": "route_of_administration_3",
    "FDA Receipt Date": "fda_receipt_date",
    "FDA Approval Date": "fda_approval_date",
    "Approval Year": "approval_year",
    "Abbreviated Indication(s)": "abbreviated_indication",
    "Approved Use(s)": "approved_use",
    "Review Designation": "review_designation",
    "Orphan Drug Designation": "orphan_drug_designation",
    "Accelerated Approval": "accelerated_approval",
    "Breakthrough Therapy Designation": "breakthrough_therapy_designation",
    "Fast Track Designation": "fast_track_designation",
    "Qualified Infectious Disease Product": "qualified_infectious_disease_product",
    "Issued a Priority Review Voucher": "priority_review_voucher_issued",
    "Redeemed a Priority Review Voucher": "priority_review_voucher_redeemed",
    "Notes": "notes",
}

OUTPUT_COLUMNS = (
    "approval_year",
    "proprietary_name",
    "active_ingredient",
    "applicant",
    "application_type",
    "application_number",
    "application_number_2",
    "application_number_3",
    "dosage_form",
    "route_of_administration",
    "dosage_form_2",
    "route_of_administration_2",
    "dosage_form_3",
    "route_of_administration_3",
    "fda_receipt_date",
    "fda_approval_date",
    "days_receipt_to_approval",
    "abbreviated_indication",
    "approved_use",
    "review_designation",
    "orphan_drug_designation",
    "accelerated_approval",
    "breakthrough_therapy_designation",
    "fast_track_designation",
    "qualified_infectious_disease_product",
    "priority_review_voucher_issued",
    "priority_review_voucher_redeemed",
    "notes",
)

# The designation columns joined onto the novel-approvals index.
DESIGNATION_COLUMNS = (
    "review_designation",
    "orphan_drug_designation",
    "accelerated_approval",
    "breakthrough_therapy_designation",
    "fast_track_designation",
    "qualified_infectious_disease_product",
    "priority_review_voucher_issued",
    "priority_review_voucher_redeemed",
)


def fetch_compilation(
    cache_dir: Path | str = "data/raw/fda/compilation",
    *,
    force: bool = False,
) -> Path:
    """Download FDA's compilation spreadsheet and cache it.

    Writes ``compilation.xlsx`` and a ``compilation.meta.json`` sidecar holding
    the source URL, FDA's file name, the ``Last-Modified`` header and the
    download date, so a published bundle can say which FDA file it came from.
    """
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / "compilation.xlsx"
    if target.exists() and not force:
        return target
    req = Request(COMPILATION_XLSX_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=60) as resp:
        target.write_bytes(resp.read())
        disposition = resp.headers.get("Content-Disposition") or ""
        last_modified = resp.headers.get("Last-Modified")
    m = re.search(r'filename="([^"]+)"', disposition)
    meta = {
        "url": COMPILATION_XLSX_URL,
        "file_name": m.group(1) if m else None,
        "last_modified": last_modified,
        "fetched": date.today().isoformat(),
    }
    (cache / "compilation.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return target


def read_source_metadata(xlsx_path: Path | str) -> dict:
    """Provenance for a cached compilation file: sidecar fields plus its SHA-256."""
    path = Path(xlsx_path)
    meta: dict = {"url": COMPILATION_XLSX_URL, "page": COMPILATION_PAGE_URL}
    sidecar = path.with_name("compilation.meta.json")
    if sidecar.exists():
        meta.update(json.loads(sidecar.read_text()))
    meta["page"] = COMPILATION_PAGE_URL
    meta["data_dictionary"] = DATA_DICTIONARY_URL
    meta["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return meta


def read_xlsx_rows(path: Path | str) -> list[list[str | None]]:
    """Return the cell text of the first worksheet of an XLSX, row by row.

    Handles shared and inline strings and plain values. Dates stored as Excel
    serial numbers come back as their numeric text; ``_to_iso_date`` converts
    them.
    """
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{_MAIN}}}t")))
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        rels = {
            r.get("Id"): r.get("Target")
            for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        }
        first = workbook.find("m:sheets", _NS)[0]
        target = rels[first.get(f"{{{_REL}}}id")].lstrip("/")
        sheet_path = target if target.startswith("xl/") else f"xl/{target}"
        rows: list[list[str | None]] = []
        for row in ET.fromstring(z.read(sheet_path)).iter(f"{{{_MAIN}}}row"):
            cells: dict[int, str | None] = {}
            for c in row.findall("m:c", _NS):
                kind = c.get("t")
                v = c.find("m:v", _NS)
                if kind == "s" and v is not None:
                    value = shared[int(v.text)]
                elif kind == "inlineStr":
                    value = "".join(t.text or "" for t in c.iter(f"{{{_MAIN}}}t"))
                else:
                    value = v.text if v is not None else None
                cells[_column_index(c.get("r"))] = value
            if cells:
                rows.append([cells.get(i) for i in range(max(cells) + 1)])
    return rows


def _column_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    # Collapse runs of spaces but keep line breaks: FDA's approved-use text
    # uses them to separate indications and limitations of use.
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in value.splitlines()]
    text = "\n".join(line for line in lines if line)
    return text or None


def _to_iso_date(value: str | None) -> str | None:
    """FDA mixes Excel serial dates (older rows) with ``M/D/YYYY`` text."""
    value = _clean(value)
    if value is None:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", value):
        return (date(1899, 12, 30) + timedelta(days=int(float(value)))).isoformat()
    return datetime.strptime(value, "%m/%d/%Y").date().isoformat()


def _application_number(value: str | None) -> str | None:
    """Zero-pad to the six digits Drugs@FDA uses (``19010`` -> ``019010``)."""
    value = _clean(value)
    if value is None:
        return None
    if not value.isdigit():
        raise ValueError(f"unexpected application number {value!r}")
    return value.zfill(6)


def parse_compilation(path: Path | str) -> pd.DataFrame:
    """Parse FDA's compilation spreadsheet into one row per approval."""
    rows = read_xlsx_rows(path)
    header = [re.sub(r"\s+", " ", h or "").strip() for h in rows[0]]
    unknown = [h for h in header if h and h not in _COLUMNS]
    missing = [h for h in _COLUMNS if h not in header]
    if unknown or missing:
        raise ValueError(
            f"FDA changed the compilation layout: unknown columns {unknown}, missing {missing}"
        )
    names = [_COLUMNS[h] for h in header]
    records = []
    for raw in rows[1:]:
        raw = raw + [None] * (len(names) - len(raw))
        r = {n: _clean(v) for n, v in zip(names, raw, strict=False)}
        if not r.get("application_number"):
            continue
        for key in ("application_number", "application_number_2", "application_number_3"):
            r[key] = _application_number(r[key])
        r["fda_receipt_date"] = _to_iso_date(r["fda_receipt_date"])
        r["fda_approval_date"] = _to_iso_date(r["fda_approval_date"])
        r["approval_year"] = int(r["approval_year"])
        if r["fda_approval_date"] is None or int(r["fda_approval_date"][:4]) != r["approval_year"]:
            raise ValueError(
                f"{r['proprietary_name']}: approval date {r['fda_approval_date']} "
                f"does not fall in approval year {r['approval_year']}"
            )
        r["days_receipt_to_approval"] = (
            (
                date.fromisoformat(r["fda_approval_date"])
                - date.fromisoformat(r["fda_receipt_date"])
            ).days
            if r["fda_receipt_date"]
            else None
        )
        records.append(r)
    df = pd.DataFrame(records, columns=list(OUTPUT_COLUMNS))
    df["days_receipt_to_approval"] = df["days_receipt_to_approval"].astype("Int64")
    return df.sort_values(["fda_approval_date", "proprietary_name"]).reset_index(drop=True)


def is_yes(value: str | None) -> bool:
    """True for ``Yes`` and for qualified values such as ``Yes (indication [A] only)``."""
    return bool(value) and value.strip().lower().startswith("yes")


def is_priority(value: str | None) -> bool:
    """True for ``Priority`` and its qualified forms (voucher, single indication)."""
    return bool(value) and value.strip().lower().startswith("priority")


def _join_distinct(*values: object) -> str | None:
    seen: list[str] = []
    for v in values:
        if isinstance(v, str) and v and v not in seen:
            seen.append(v)
    return "; ".join(seen) or None


def enrich_with_designations(df: pd.DataFrame, compilation: pd.DataFrame) -> pd.DataFrame:
    """Join the compilation's regulatory characteristics onto the approvals index.

    Matches on application number, against any of the up-to-three numbers the
    compilation lists for a product (Ojemda's oral suspension, for example, is
    listed second). Rows with no match, including every CBER product, get
    ``None`` in the added columns.
    """
    lookup: dict[str, dict] = {}
    for rec in compilation.to_dict("records"):
        for key in ("application_number", "application_number_2", "application_number_3"):
            number = rec.get(key)
            if isinstance(number, str) and number:
                lookup.setdefault(number, rec)
    out = df.copy()
    added = (*DESIGNATION_COLUMNS, "fda_receipt_date", "dosage_form", "route_of_administration")
    values: dict[str, list] = {c: [] for c in added}
    for number in out["application_number"].tolist():
        rec = lookup.get(number) if isinstance(number, str) else None
        for c in added:
            if rec and c in ("dosage_form", "route_of_administration"):
                # A product with several applications lists one form and route
                # per application; show them all rather than guess which is ours.
                v = _join_distinct(rec.get(c), rec.get(f"{c}_2"), rec.get(f"{c}_3"))
            else:
                v = rec.get(c) if rec else None
            values[c].append(v if isinstance(v, str) and v else None)
    for c in added:
        out[c] = values[c]
    return out
