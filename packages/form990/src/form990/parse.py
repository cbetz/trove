"""Parse 990 e-file XMLs from IRS bulk ZIPs into a tidy Schedule H DataFrame."""

from __future__ import annotations

import re
import struct
import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import inflate64
import pandas as pd
from lxml import etree

from form990.download import discover_batches, download_zip
from form990.schedule_h import OUTPUT_COLUMNS, PART_I_EXTRA_COLUMNS, PART_I_LINE_GROUPS

# IRS bulk ZIPs starting with the 2025 release year use DEFLATE64 (compress_type
# 9), which Python's stdlib zipfile can index but cannot decompress.
ZIP_DEFLATED64 = 9

_NS_URI = "http://www.irs.gov/efile"
_NSMAP = {"e": _NS_URI}

# A return covering at least this many days counts as a full-year return; a
# shorter one is a stub filed when an organization changes its fiscal year.
FULL_YEAR_MIN_DAYS = 330

# Cheap byte-level filter so we skip parsing returns that don't have Schedule H.
_SCH_H_MARKER = b"IRS990ScheduleH"
_OBJECT_ID_RE = re.compile(r"(\d{6,})_public\.xml$")


def parse_zip(zip_path: Path | str) -> pd.DataFrame:
    """Parse one bulk-XML ZIP and return a DataFrame of Schedule H filers."""
    rows = list(iter_schedule_h_filings(Path(zip_path)))
    return _frame(rows)


def _frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return _coerce_dtypes(pd.DataFrame(columns=list(OUTPUT_COLUMNS)))
    return _coerce_dtypes(pd.DataFrame(rows, columns=list(OUTPUT_COLUMNS)))


def parse_tax_year(
    tax_year: int,
    release_year: int,
    cache_dir: Path | str = "data/raw/form990",
    *,
    progress: bool = True,
    keep_zips: bool = True,
    batches: Sequence[str] | None = None,
    xml_dir: Path | str | None = None,
    batch_cache_dir: Path | str | None = None,
) -> pd.DataFrame:
    """Parse Schedule H for ``tax_year`` out of EVERY bulk ZIP in ``release_year``.

    Returns are located by scanning each ZIP's members, not through the IRS index:
    the 2023 index has no batch column, and later indexes mislabel split batches
    (May 2025/2026 is ``05A`` + ``05B`` on the server but all ``05A`` in the index).
    ``batches`` defaults to ``discover_batches(release_year)``.

    ZIPs are handled one at a time. With ``keep_zips=False`` each ZIP is deleted
    as soon as it has been parsed, so peak disk use is one ZIP (the largest are
    ~1.2 GB) rather than a whole release (4-5 GB).

    ``xml_dir``, when given, receives the raw XML of every Schedule H return for
    ``tax_year`` as ``{object_id}_public.xml`` — the evidence trail for the rows.

    ``batch_cache_dir``, when given, stores one small Parquet per parsed ZIP so an
    interrupted run resumes without re-downloading.

    The parser itself extracts every Schedule H filer in a ZIP regardless of tax
    year; the result is narrowed to ``tax_year`` (the XML's ``TaxYr``) here. The
    returned frame carries ``release_year`` and ``batch_id`` columns.
    """
    cache = Path(cache_dir)
    if batches is None:
        batches = discover_batches(release_year)
    xml_out = Path(xml_dir) if xml_dir is not None else None
    if xml_out is not None:
        xml_out.mkdir(parents=True, exist_ok=True)
    bcache = Path(batch_cache_dir) if batch_cache_dir is not None else None
    if bcache is not None:
        bcache.mkdir(parents=True, exist_ok=True)

    parts: list[pd.DataFrame] = []
    for i, batch in enumerate(batches, start=1):
        cached = bcache / f"ty{tax_year}_{batch}.parquet" if bcache is not None else None
        if cached is not None and cached.exists():
            if progress:
                print(f"  [{i}/{len(batches)}] {batch} (cached)", flush=True)
            parts.append(pd.read_parquet(cached))
            continue
        if progress:
            print(f"  [{i}/{len(batches)}] {batch}", flush=True)
        zip_path = download_zip(release_year, batch, cache)
        rows: list[dict[str, Any]] = []
        for row, blob in iter_schedule_h_filings(zip_path, with_blob=True):
            if str(row.get("tax_year")) != str(tax_year):
                continue
            rows.append(row)
            if xml_out is not None and row.get("object_id"):
                (xml_out / f"{row['object_id']}_public.xml").write_bytes(blob)
        part = _frame(rows)
        part["release_year"] = pd.Series([release_year] * len(part), dtype="Int64")
        part["batch_id"] = pd.Series([batch] * len(part), dtype="string")
        if cached is not None:
            part.to_parquet(cached, index=False)
        if not keep_zips:
            zip_path.unlink()
        if progress:
            print(f"      {len(part)} Schedule H returns for TY{tax_year}", flush=True)
        parts.append(part)

    if not parts:
        df = _frame([])
        df["release_year"] = pd.Series(dtype="Int64")
        df["batch_id"] = pd.Series(dtype="string")
        return df
    return pd.concat(parts, ignore_index=True)


def latest_return_per_ein(schedule_h: pd.DataFrame) -> pd.DataFrame:
    """One row per EIN: the return to treat as that filer's return of record.

    An EIN can appear more than once for one tax year — an amended return, the
    same return republished in a later release, or a short-year return alongside
    a full-year one. Preference order: latest ``tax_period_end``, then latest
    ``return_ts`` (the e-file timestamp, so an amendment beats the original), then
    newest ``release_year``. Columns absent from the frame are skipped.

    A full-year return (at least ``FULL_YEAR_MIN_DAYS`` long) is preferred over a
    short-year one: filers that change fiscal year file a stub return on the same
    year's forms, and the stub is not the year being compared.

    This is the single implementation; ``analytics.community_benefit`` imports it.
    """
    keys = [c for c in ("tax_period_end", "return_ts", "release_year") if c in schedule_h.columns]
    ordered = schedule_h
    ascending = [False] * len(keys)
    if {"tax_period_begin", "tax_period_end"} <= set(schedule_h.columns):
        days = (
            pd.to_datetime(schedule_h["tax_period_end"])
            - pd.to_datetime(schedule_h["tax_period_begin"])
        ).dt.days
        # Unknown length counts as full-year; only a known short period is demoted.
        ordered = schedule_h.assign(_short_year=(days < FULL_YEAR_MIN_DAYS).fillna(False))
        keys = ["_short_year", *keys]
        ascending = [True, *ascending]
    ordered = ordered.sort_values(keys, ascending=ascending, na_position="last", kind="stable")
    ordered = ordered.drop_duplicates(subset=["ein"], keep="first")
    return ordered.drop(columns=["_short_year"], errors="ignore").reset_index(drop=True)


def iter_schedule_h_filings(zip_path: Path, *, with_blob: bool = False) -> Iterator[Any]:
    """Yield one row dict per filing that contains a Schedule H.

    With ``with_blob=True`` yields ``(row, xml_bytes)`` pairs instead.
    """
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.endswith(".xml"):
                continue
            blob = _read_zip_entry(zf, info)
            if _SCH_H_MARKER not in blob:
                continue
            row = _extract(blob)
            if row is None:
                continue
            row["object_id"] = _object_id(info.filename)
            yield (row, blob) if with_blob else row


def _object_id(member_name: str) -> str | None:
    """``2023_TEOS_XML_05A/202341319349301234_public.xml`` → ``202341319349301234``."""
    m = _OBJECT_ID_RE.search(member_name)
    return m.group(1) if m else None


def _read_zip_entry(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.compress_type != ZIP_DEFLATED64:
        return zf.read(info)
    fp = zf.fp
    if fp is None:
        raise RuntimeError("ZipFile has no open file handle")
    fp.seek(info.header_offset)
    local_header = fp.read(30)
    if local_header[:4] != b"PK\x03\x04":
        raise zipfile.BadZipFile(f"bad local file header at {info.header_offset}")
    fname_len, extra_len = struct.unpack("<HH", local_header[26:30])
    fp.read(fname_len + extra_len)
    compressed = fp.read(info.compress_size)
    return inflate64.Inflater().inflate(compressed)


def _extract(xml_blob: bytes) -> dict[str, Any] | None:
    try:
        root = etree.fromstring(xml_blob)
    except etree.XMLSyntaxError:
        return None
    ns = _NSMAP

    header = root.find("e:ReturnHeader", ns)
    sch_h = root.find(".//e:IRS990ScheduleH", ns)
    if header is None or sch_h is None:
        return None
    main_990 = root.find(".//e:IRS990", ns)

    row: dict[str, Any] = dict.fromkeys(OUTPUT_COLUMNS)
    row["return_version"] = root.get("returnVersion")
    row["ein"] = _text(header, "e:Filer/e:EIN")
    row["organization_name"] = _text(header, "e:Filer/e:BusinessName/e:BusinessNameLine1Txt")
    row["tax_period_begin"] = _text(header, "e:TaxPeriodBeginDt")
    row["tax_period_end"] = _text(header, "e:TaxPeriodEndDt")
    row["tax_year"] = _text(header, "e:TaxYr")
    row["return_ts"] = _text(header, "e:ReturnTs")
    row["filer_city"] = _text(header, "e:Filer/e:USAddress/e:CityNm")
    row["filer_state"] = _text(header, "e:Filer/e:USAddress/e:StateAbbreviationCd")

    if main_990 is not None:
        row["total_revenue"] = _text(main_990, "e:CYTotalRevenueAmt")
        row["total_expenses"] = _text(main_990, "e:CYTotalExpensesAmt")
        row["amended_return"] = main_990.find("e:AmendedReturnInd", ns) is not None

    for element_name, var_name in PART_I_LINE_GROUPS.items():
        group = sch_h.find(f".//e:{element_name}", ns)
        if group is None:
            continue
        row[var_name] = _text(group, "e:NetCommunityBenefitExpnsAmt")
        for suffix, child in PART_I_EXTRA_COLUMNS.items():
            row[f"{var_name}{suffix}"] = _text(group, f"e:{child}")
        if var_name == "total_community_benefit":
            row["total_community_benefit_pct"] = _text(group, "e:TotalExpensePct")

    row["bad_debt_expense"] = _text(sch_h, ".//e:BadDebtExpenseAmt")
    row["hospital_facility_count"] = _text(sch_h, ".//e:HospitalFacilitiesCnt")

    return row


def _text(element: etree._Element, xpath: str) -> str | None:
    found = element.find(xpath, _NSMAP)
    if found is None or found.text is None:
        return None
    return found.text.strip() or None


def _coerce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    string_cols = (
        "ein",
        "organization_name",
        "return_version",
        "object_id",
        "filer_city",
        "filer_state",
    )
    int_cols = ("tax_year", "hospital_facility_count")
    money_cols = (
        "total_revenue",
        "total_expenses",
        "bad_debt_expense",
        *PART_I_LINE_GROUPS.values(),
        *(f"{v}{sfx}" for v in PART_I_LINE_GROUPS.values() for sfx in PART_I_EXTRA_COLUMNS),
    )
    ratio_cols = ("total_community_benefit_pct",)
    date_cols = ("tax_period_begin", "tax_period_end")

    for c in string_cols:
        df[c] = df[c].astype("string")
    for c in int_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in money_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ratio_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in date_cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    # Offsets vary by filer; normalize to UTC so amendments order correctly.
    df["return_ts"] = pd.to_datetime(df["return_ts"], errors="coerce", utc=True)
    df["amended_return"] = df["amended_return"].astype("boolean")
    return df
