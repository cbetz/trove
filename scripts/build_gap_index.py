"""Build the ranked index — single-facility, same-period rows, with components.

The full gap dataset (build_gap_dataset.py) is a per-hospital lookup table. A naive
"biggest gap" ranking over it is misleading: the largest raw gaps are dominated by
multi-facility systems reported under one EIN (misleading single-facility names) and
by rows whose two filings cover different fiscal years or different-scale entities.

This script derives the subset where the two filings describe the same hospital for
the same year, and publishes — next to the two headline figures — the components each
form reports, so a reader can see what the difference is made of.

A row is in the index when ALL of these hold (definition unchanged since v1):

  1. ccn_count == 1          exactly one of the EIN's crosswalk CCNs has a cost report
                             in the HCRIS files used, so nothing is summed across
                             facilities. This is NOT "the crosswalk lists one CCN":
                             the crosswalk can list further CCNs that have no cost
                             report (retired or merged numbers). Rows publish both
                             counts and carry the ``multi_ccn_crosswalk`` flag.
  2. period-aligned          the HCRIS cost report's period END is within 1 calendar
                             month of the 990's tax-period end (year*12+month
                             difference <= 1). build_gap_dataset.py already picked,
                             per CCN, the cost report closest to the 990's period
                             from the FY2022 and FY2023 HCRIS files.
  3. both numbers material   S-10 line 23 col 3 (cost of charity care) >= $1M AND
                             Schedule H Part I line 7a col (e) >= $1M. A missing
                             value is not a zero and never passes; neither does a
                             negative one (the test is on the value, not its size).
  4. expense bases agree     both total-expense figures (HCRIS G-3 line 4, Form 990
                             total expenses) are > 0 and max/min <= 1.05 — confirms
                             the two forms describe the same-scale entity for the same
                             period (catches stub periods, partial filings, mismatches)

Rows are ranked by the absolute net difference, S-10 line 23 col 3 minus 7a col (e).
"% difference" is |difference| / max(the two figures); "over 50%" means > 0.5.

Output:
  artifacts/charity_care_gap_index_2022.md          committed, GitHub-viewable table
  artifacts/community_benefit_gap_2022_summary.md   method, funnel, caveats for the full dataset
  web/data/charity_care_gap_index_2022.json         ranked rows + filter metadata for the site

The scatter chart is injected into the site pages only with ``--inject-chart``
(it rewrites HTML between GAP_CHART markers); without the flag no HTML is touched.
With the flag, every target page must exist and contain exactly one START and one
END marker, in that order — otherwise nothing is written and the script exits 1.
"""

import argparse
import csv
import html
import json
import math
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "artifacts" / "community_benefit_gap_2022.csv"
MD_OUT = ROOT / "artifacts" / "charity_care_gap_index_2022.md"
SUMMARY_OUT = ROOT / "artifacts" / "community_benefit_gap_2022_summary.md"
XML_ALL = ROOT / "data" / "raw" / "form990" / "xml_ty2022"
XML_KEEP = ROOT / "data" / "raw" / "form990" / "xml_keep"
JSON_OUT = ROOT / "web" / "data" / "charity_care_gap_index_2022.json"
# Written by build_gap_dataset.py: what the source files say about their own vintage.
SOURCES_JSON = ROOT / "artifacts" / "community_benefit_gap_2022_sources.json"
CHART_TARGETS = (
    ROOT / "web" / "notes" / "charity-care-gap" / "index.html",
    ROOT / "web" / "hospitals" / "index.html",
)
CHART_START = "<!-- GAP_CHART:START -->"
CHART_END = "<!-- GAP_CHART:END -->"

MATERIAL_FLOOR = 1_000_000
# The lower noise floor used for the "aligned + material" statistics in the summary
# and on the site (scripts/build_web_data.py); the index itself uses MATERIAL_FLOOR.
SUMMARY_FLOOR = 500_000
EXPENSE_BASE_TOLERANCE = 1.05
ALIGNMENT_MONTHS = 1
# irs_7a_inconsistent fires when the return's own |(c) - (d) - (e)| exceeds this.
INCONSISTENCY_TOLERANCE = 1_000
# How many dots the chart names: the N largest absolute dollar differences.
CHART_LABELS = 5

# Mechanical display notes on index rows. Each is a fact read off the two filings
# or the crosswalk; none is a judgement about the hospital or the difference.
NOTE_CODES = {
    "irs_7a_inconsistent": (
        "on the return itself, Schedule H line 7a (c) - (d) differs from (e) by more than "
        f"${INCONSISTENCY_TOLERANCE:,} (a blank (d) is read as 0)"
    ),
    "irs_offset_reported": "Schedule H line 7a col (d), direct offsetting revenue, is greater than 0",
    "cms_line5_reported": "Worksheet S-10 line 5 has a value (positive or negative)",
    "multi_ccn_crosswalk": (
        "the crosswalk lists more than one CCN for this EIN; only one has a cost report "
        "in the HCRIS files used"
    ),
    "cms_report_as_submitted": "the cost report's status is as submitted (not yet settled, amended or reopened)",
    "irs_amended_return": "the 990 used is marked as an amended return",
}

# Chart mark colors. These are NOT the site's --pos/--neg text tokens: those are
# tuned for text legibility and fail the mark checks in dark mode (both above the
# lightness band; the blue drops under the chroma floor and reads gray). These
# steps were validated per-mode as a diverging pair against each surface —
# all-pairs CVD ΔE 19.0 light / 26.8 dark, normal-vision 24.6 / 31.8, contrast
# ≥3:1 on both. Warm = reported more to CMS, cool = reported more to the IRS;
# the parity line is the neutral midpoint.
MARK_POS_LIGHT, MARK_NEG_LIGHT = "#a04413", "#1f5793"
MARK_POS_DARK, MARK_NEG_DARK = "#d95926", "#3987e5"


def _f(v):
    """Float for threshold tests. Missing -> 0.0, which fails every ``>= floor`` test."""
    n = _num(v)
    return 0.0 if n is None else n


def _num(v):
    """Float, or None when the CSV field is blank — missing must stay missing."""
    if v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(n) else n


def _round(v):
    n = _num(v)
    return None if n is None else round(n)


def _parse_date(s):
    if not s:
        return None
    try:
        y, m, d = (int(x) for x in s[:10].split("-"))
        return date(y, m, d)
    except (ValueError, AttributeError):
        return None


def _months_apart(a, b):
    da, db = _parse_date(a), _parse_date(b)
    if da is None or db is None:
        return None
    return abs((da.year - db.year) * 12 + (da.month - db.month))


def _title(s):
    if not s:
        return ""
    letters = [c for c in s if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) >= 0.8:
        return s.title()
    return s


def load_rows():
    with open(SRC) as f:
        return list(csv.DictReader(f))


def row_notes(r):
    """The NOTE_CODES that apply to one index row, in NOTE_CODES order."""
    notes = []
    gross, net = r.get("irs_7a_gross"), r.get("irs_7a")
    offset = r.get("irs_7a_offset")
    if (
        gross is not None
        and net is not None
        and abs(gross - (offset or 0) - net) > INCONSISTENCY_TOLERANCE
    ):
        notes.append("irs_7a_inconsistent")
    if offset is not None and offset > 0:
        notes.append("irs_offset_reported")
    if r.get("cms_s10_line5") is not None:
        notes.append("cms_line5_reported")
    if r.get("multi_ccn_crosswalk"):
        notes.append("multi_ccn_crosswalk")
    if "as_submitted" in (r.get("hcris_status") or "").split(";"):
        notes.append("cms_report_as_submitted")
    if r.get("amended_990"):
        notes.append("irs_amended_return")
    return notes


def clean_index(rows):
    out = []
    for r in rows:
        if r.get("ccn_count") != "1":
            continue
        hc = _f(r["hcris_charity_care_cost"])
        sh = _f(r["sched_h_financial_assistance_at_cost"])
        he = _f(r["hcris_total_operating_expenses"])
        se = _f(r["sched_h_total_expenses"])
        if hc < MATERIAL_FLOOR or sh < MATERIAL_FLOOR:
            continue
        if he <= 0 or se <= 0:
            continue
        if max(he, se) / min(he, se) > EXPENSE_BASE_TOLERANCE:
            continue
        months = _months_apart(r["hcris_fy_end_dt"], r["sched_h_tax_period_end"])
        if months is None or months > ALIGNMENT_MONTHS:
            continue
        gap = hc - sh
        denom = max(hc, sh)
        out.append(
            {
                "ein": r["ein"],
                "name": _title(r["hospital_name"]),
                "irs_7a": round(sh),
                "cms_s10": round(hc),
                "gap": round(gap),
                "gap_pct": round(abs(gap) / denom, 4) if denom else None,
                "expense_base": round((he + se) / 2),
                "hcris_fy_end": (r["hcris_fy_end_dt"] or "")[:10],
                "period_end": (r["sched_h_tax_period_end"] or "")[:10],
                "svi_overall_pct": _f(r["svi_overall_pct"]) if r.get("svi_overall_pct") else None,
                # --- components: what each form reports around the headline figure ---
                "city": _title(r.get("city") or ""),
                "state": r.get("state") or None,
                "ccn": r.get("ccn_list") or None,
                # Schedule H Part I line 7a: (c) gross expense, (d) direct offsetting
                # revenue; irs_7a above is (e) = (c) - (d).
                "irs_7a_gross": _round(r.get("sched_h_financial_assistance_gross")),
                "irs_7a_offset": _round(r.get("sched_h_financial_assistance_offset_revenue")),
                # Schedule H Part I line 7b (Medicaid): (c), (d), (e).
                "irs_7b_gross": _round(r.get("sched_h_unreimbursed_medicaid_gross")),
                "irs_7b_offset": _round(r.get("sched_h_unreimbursed_medicaid_offset_revenue")),
                "irs_7b": _round(r.get("sched_h_unreimbursed_medicaid")),
                # S-10 line 23 cols 1 and 2; cms_s10 above is col 3.
                "cms_s10_uninsured": _round(r.get("hcris_charity_care_cost_uninsured")),
                "cms_s10_insured": _round(r.get("hcris_charity_care_cost_insured")),
                # S-10 lines 20-22 col 3: charges, cost before payments, payments.
                "cms_s10_charges": _round(r.get("hcris_charity_care_charges")),
                "cms_s10_cost_before_payments": _round(
                    r.get("hcris_charity_care_cost_before_payments")
                ),
                "cms_s10_payments": _round(r.get("hcris_charity_care_partial_payments")),
                # S-10 line 5: Medicaid DSH/supplemental payments net of provider taxes.
                "cms_s10_line5": _round(r.get("hcris_medicaid_dsh_supplemental")),
                # S-10 line 23 col 3 minus 7a col (c).
                "gap_gross": _round(r.get("charity_gap_gross")),
                "hcris_fy_begin": (r.get("hcris_fy_bgn_dt") or "")[:10] or None,
                "period_begin": (r.get("sched_h_tax_period_begin") or "")[:10] or None,
                "hcris_status": r.get("hcris_report_status") or None,
                "object_id": r.get("sched_h_object_id") or None,
                "release_year": _round(r.get("sched_h_release_year")),
                "amended_990": (r.get("sched_h_amended_return") == "True"),
                # Does the return's own 7a arithmetic hold, (c) - (d) = (e)? None = not checkable.
                "irs_7a_consistent": {"True": True, "False": False}.get(
                    r.get("sched_h_fa_7a_consistent")
                ),
                # CCNs with a cost report in the HCRIS files used (always 1 here) and
                # CCNs the crosswalk lists for the EIN (can be more).
                "ccns_with_cost_report": int(r["ccn_count"]),
                "crosswalk_ccn_count": _round(r.get("crosswalk_ccn_count")),
                "multi_ccn_crosswalk": (_num(r.get("crosswalk_ccn_count")) or 0) > 1,
            }
        )
        out[-1]["notes"] = row_notes(out[-1])
    out.sort(key=lambda x: -abs(x["gap"]))
    return out


def funnel(rows, index):
    """matched -> computable -> aligned -> clean -> over 50%, from the full CSV."""

    def computable(r):
        return (
            _num(r["hcris_charity_care_cost"]) is not None
            and _num(r["sched_h_financial_assistance_at_cost"]) is not None
        )

    comp = [r for r in rows if computable(r)]
    aligned = [r for r in comp if r.get("period_aligned") == "True"]
    material = material_subset(aligned)
    return {
        "aligned_material": len(material),
        "aligned_material_50pct_or_more": sum(1 for v in _abs_pcts(material) if v >= 0.5),
        "clean_multi_ccn_crosswalk": sum(1 for r in index if r["multi_ccn_crosswalk"]),
        "matched": len(rows),
        "computable": len(comp),
        "aligned": len(aligned),
        "aligned_single_facility": sum(1 for r in aligned if r.get("ccn_count") == "1"),
        "clean_aligned": len(index),
        "clean_aligned_over_50pct": sum(1 for r in index if r["gap_pct"] and r["gap_pct"] > 0.5),
        "clean_states": len({r["state"] for r in index if r["state"]}),
    }


def material_subset(aligned):
    """Aligned rows with both figures at or above SUMMARY_FLOOR.

    The test is on the value, not its absolute size: a negative 7a (e) of
    -$3M is not "at least $500K".
    """
    return [
        r
        for r in aligned
        if _f(r["hcris_charity_care_cost"]) >= SUMMARY_FLOOR
        and _f(r["sched_h_financial_assistance_at_cost"]) >= SUMMARY_FLOOR
    ]


def _abs_pcts(subset):
    """|S-10 - 7a| / max(|S-10|, |7a|) per row; 0 when both are 0."""
    out = []
    for r in subset:
        h = _num(r["hcris_charity_care_cost"])
        f = _num(r["sched_h_financial_assistance_at_cost"])
        denom = max(abs(h), abs(f))
        out.append(abs(h - f) / denom if denom else 0.0)
    return out


def load_sources():
    """Source-file vintage recorded by build_gap_dataset.py (never a literal here)."""
    if not SOURCES_JSON.exists():
        raise SystemExit(
            f"missing {SOURCES_JSON.relative_to(ROOT)}; run scripts/build_gap_dataset.py first"
        )
    return json.loads(SOURCES_JSON.read_text())


def cms_vintage_sentence(sources):
    """'... FY2022 and FY2023 files, CMS extract generated ..., posted ..., latest ...'.

    One wording everywhere: the extract date is the newest timestamp of the files
    inside the CMS ZIPs; the posted date is the Last-Modified header of the CMS
    download (recorded by ``build_gap_dataset.py --check-posted``). Either part is
    left out when the build did not record it for every file.
    """
    files = sources["cms_hcris"]["files"]
    fys = " and ".join(f"FY{f['fiscal_year']}" for f in files)
    procs = sorted({f["latest_proc_dt"] for f in files if f.get("latest_proc_dt")})

    def span(key):
        if not all(f.get(key) for f in files):
            return None
        days = sorted({f[key] for f in files})
        return days[0] if len(days) == 1 else f"{days[0]} to {days[-1]}"

    parts = [f"CMS HCRIS Hospital 2552-10 {fys} files"]
    extract, posted = span("extract_date"), span("posted_date")
    if extract:
        parts.append(f"CMS extract generated {extract}")
    if posted:
        parts.append(f"posted {posted}")
    if procs:
        parts.append(f"latest cost-report processing date {procs[-1]}")
    return ", ".join(parts)


# The two definitions and the paragraph under them are the lede of the site's
# /hospitals/ page; keep the wording in step with web/hospitals/index.html.
LINE_DEFINITIONS = (
    "- **IRS Form 990, Schedule H, Part I, line 7a** is financial assistance at cost: "
    "column (c) total community benefit expense, column (d) direct offsetting revenue, "
    "column (e) net = (c) − (d).\n"
    "- **CMS cost report (form 2552-10), Worksheet S-10, line 23, column 3** is the cost of "
    "charity care after patient payments: uninsured patients (column 1) plus insured "
    "patients (column 2)."
)
WHY_THEY_DIFFER = (
    "**The two lines are defined differently, so they can differ even when both are filed "
    "correctly.** The IRS Schedule H instructions (Worksheet 1, line 4) let a filer include "
    "Medicaid or provider taxes in the line 7a cost when payments from its state's "
    "uncompensated care pool or DSH program are intended primarily to offset the cost of "
    "financial assistance, with that pool revenue reported as offsetting revenue "
    "(Worksheet 1, line 6); otherwise those amounts belong on line 7b. The cost report keeps "
    "Medicaid DSH and supplemental payments, net of provider taxes, on a separate line "
    "(S-10 line 5) that is not part of line 23. The S-10 insured column counts deductibles "
    "and coinsurance written off."
)
HOSPITALS_PAGE = "https://troveproject.com/hospitals/"

# The worked example: the largest dollar difference in the index.
WORKED_EXAMPLE_EIN = "060646652"
# The other hospitals of the same system in the data (Greenwich, Lawrence + Memorial,
# Bridgeport); with the worked example they are the four the return's narrative covers.
WORKED_EXAMPLE_SISTERS = ("060646659", "060646704", "060646554")
# Read from the Schedule H Part III line 4 narrative of the worked example's return
# (IRS object id 202422269349301652; the sister returns carry the same text): what the
# system paid into Connecticut's DSH program assessment and what it received in
# distributions, fiscal year ended 2023-09-30. The sentence built on these is only
# written when the published rows add up to them.
NARRATIVE_OBJECT_ID = "202422269349301652"
NARRATIVE_ASSESSMENT_PAID = 317_900_000
NARRATIVE_DISTRIBUTIONS = 198_200_000


def pct_text(p):
    """'69%' for a proportion; one decimal where a whole number would print '50%'.

    "Differ by more than 50%" is counted on the exact value, so a 49.5% row must
    not read as 50%. The site's table applies the same rule.
    """
    if p is None:
        return "—"
    if 0.495 <= p < 0.505:
        return f"{p * 100:.1f}%"
    return f"{round(p * 100)}%"


def _prose_name(name):
    """Title-cased name for prose; the hospital writes itself "Lawrence + Memorial".

    Prose only: table cells and the JSON keep the name as the cost report has it.
    """
    return _title(name).replace("Lawrence & Memorial", "Lawrence + Memorial")


def _m(v, digits=1):
    """'$77.5M' for a dollar amount, sign dropped (the prose says which way)."""
    return f"${abs(v) / 1e6:.{digits}f}M"


def worked_example(index, rows):
    """Markdown for the worked example, every figure read from the rows.

    Returns [] when the example hospital is not in the index or lacks a
    component, so a rebuild can never print a stale reconciliation.
    """
    by_ein = {r["ein"]: r for r in index}
    r = by_ein.get(WORKED_EXAMPLE_EIN)
    need = ("irs_7a_gross", "irs_7a_offset", "irs_7a", "cms_s10", "cms_s10_line5")
    if r is None or any(r.get(k) is None for k in need) or r["cms_s10_line5"] >= 0:
        return []
    out = [
        "## A worked example",
        "",
        f"{r['name']} (EIN {r['ein'][:2]}-{r['ein'][2:]}, CCN {r['ccn']}, fiscal year ending "
        f"{r['period_end']}), from the two filings:",
        "",
        "| Line | Amount |",
        "|---|--:|",
        f"| IRS Schedule H line 7a, column (c) | ${r['irs_7a_gross']:,} |",
        f"| IRS Schedule H line 7a, column (d) | ${r['irs_7a_offset']:,} |",
        f"| IRS Schedule H line 7a, column (e) | ${r['irs_7a']:,} |",
        f"| CMS S-10 line 23, column 3 | ${r['cms_s10']:,} |",
        f"| CMS S-10 line 5 | −${abs(r['cms_s10_line5']):,} |",
        f"| Difference between (e) and line 23 | ${abs(r['gap']):,} |",
        "",
        f"Of the {_m(r['gap'])} difference, about {_m(r['cms_s10_line5'])} appears to be "
        "Connecticut's hospital provider tax net of the state supplemental payments it funds: "
        "the amount on S-10 line 5, which the cost report keeps separate from charity care. "
        "The worksheet behind the IRS line is not public, so this is a reconciliation from the "
        "hospital's own filings, not a figure the hospital has stated.",
        "",
    ]
    full = {x["ein"]: x for x in rows}
    sisters = [full[e] for e in WORKED_EXAMPLE_SISTERS if e in full]
    shown = []
    for x in sisters:
        l5, gap = _num(x.get("hcris_medicaid_dsh_supplemental")), _num(x.get("charity_gap"))
        if l5 is None or gap is None:
            continue
        shown.append(
            f"{_prose_name(x['hospital_name'])} (line 5 −{_m(l5, 2)}, difference −{_m(gap, 2)})"
            if l5 < 0 and gap < 0
            else None
        )
    if shown and all(shown):
        out += [
            "The other hospitals of the same system in the data show the same pattern: "
            + "; ".join(shown)
            + ".",
            "",
        ]
    group = [full.get(WORKED_EXAMPLE_EIN), *sisters]
    if len(group) == 1 + len(WORKED_EXAMPLE_SISTERS) and all(group):
        offsets = [_num(x.get("sched_h_financial_assistance_offset_revenue")) for x in group]
        line5s = [_num(x.get("hcris_medicaid_dsh_supplemental")) for x in group]
        if all(v is not None for v in offsets + line5s):
            d_sum, l5_sum = sum(offsets), sum(line5s)
            net = NARRATIVE_DISTRIBUTIONS - NARRATIVE_ASSESSMENT_PAID
            if abs(d_sum - NARRATIVE_DISTRIBUTIONS) < 50_000 and abs(l5_sum - net) < 50_000:
                out += [
                    "The return's own Schedule H narrative (Part III, line 4) says the system paid "
                    f"{_m(NARRATIVE_ASSESSMENT_PAID)} into Connecticut's DSH program assessment and "
                    f"received {_m(NARRATIVE_DISTRIBUTIONS)} in distributions that year. Across the "
                    "system's four Connecticut hospitals in this data, line 7a column (d) "
                    f"sums to {_m(d_sum)} and S-10 line 5 sums to −{_m(l5_sum)}, the difference "
                    "between those two amounts. This is still a reconciliation: the return does "
                    "not say what is in line 7a.",
                    "",
                ]
    out += [
        "A reading of the two filings behind each of the 25 largest differences, sorted by "
        f"what the published components show, is on the [hospitals page]({HOSPITALS_PAGE}#how-to-read). "
        "For some of them neither filing shows a mechanism; those are open questions.",
        "",
    ]
    return out


def unreported_ccn_sentence(sources):
    """What the files say about crosswalk CCNs that have no cost report (no full stop)."""
    cw = sources.get("crosswalk") or {}
    n = cw.get("ccns_without_cost_report")
    if n is None:
        return "How many crosswalk CCNs have no cost report was not recorded for this build"
    loaded = " or ".join(f"FY{f['fiscal_year']}" for f in sources["cms_hcris"]["files"])
    lead = (
        f"Across all matched EINs the crosswalk lists {n:,} CCNs that have no cost report in "
        f"the {loaded} file"
    )
    extra = cw.get("also_checked_fiscal_years") or []
    found = cw.get("found_in_also_checked")
    if not extra or found is None:
        return f"{lead}; no later file was checked for them"
    extra_txt = " or ".join(f"FY{y}" for y in extra)
    if found == 0:
        return (
            f"{lead}; none of them appears in the {extra_txt} file either, which is "
            "consistent with retired or merged provider numbers"
        )
    return (
        f"{lead}; {found:,} of them do have a report in the {extra_txt} file "
        "(a later period than the one compared here)"
    )


def filing_url(r):
    """ProPublica deep link to the Schedule H of the exact return used."""
    base = f"https://projects.propublica.org/nonprofits/organizations/{int(r['ein'])}"
    return f"{base}/{r['object_id']}/IRS990ScheduleH" if r.get("object_id") else base


def usd(v):
    if v is None:
        return "—"
    a = abs(v)
    sign = "−" if v < 0 else ""
    if a >= 1e9:
        return f"{sign}${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}${a / 1e3:.0f}K"
    return f"{sign}${a:.0f}"


def write_markdown(index, rows, counts, sources):
    n = len(index)
    big = counts["clean_aligned_over_50pct"]
    lines = []
    lines.append("# Hospital charity care on two public filings: the ranked index — TY2022")
    lines.append("")
    cms_larger = sum(1 for r in index if r["gap"] > 0)
    irs_larger = sum(1 for r in index if r["gap"] < 0)
    equal = n - cms_larger - irs_larger
    lines.append(
        "Nonprofit hospitals publish a financial-assistance figure on their IRS Form 990 and "
        "a charity-care figure on their Medicare cost report. This table puts the two public "
        "figures next to each other for every hospital that can be matched to a single cost "
        "report for the same fiscal period, with the components from each filing that show "
        "what is in the difference."
    )
    lines.append("")
    lines.append(LINE_DEFINITIONS)
    lines.append("")
    lines.append(WHY_THEY_DIFFER)
    lines.append("")
    lines.append(
        "The table is the part of the full [matched dataset](community_benefit_gap_2022.csv) "
        "where one 990 can be set against one cost report for the same period. "
        "Each hospital below is:"
    )
    lines.append("")
    lines.append(
        "- a **single reporting facility in the cost-report data** (the EIN has exactly one CCN with a cost report in the HCRIS files used, so nothing is summed across facilities);"
    )
    lines.append(
        f"- **period-aligned** (the cost report's period ends within {ALIGNMENT_MONTHS} month of the 990's tax period — the two filings cover the same year);"
    )
    lines.append(
        "- **material** (S-10 line 23 col 3 and Schedule H line 7a col (e) are both at least $1M); and"
    )
    lines.append(
        f"- reporting **the same-scale entity** (the two forms' total expenses agree within {int((EXPENSE_BASE_TOLERANCE - 1) * 100)}%)."
    )
    lines.append("")
    lines.append(
        f"**{n} hospitals in {counts['clean_states']} states** meet all four conditions "
        f"(funnel: {counts['matched']:,} matched systems → {counts['computable']:,} with both "
        f"figures present → {counts['aligned']:,} period-aligned → {n} in this index). "
        f"The S-10 figure is the larger one for {cms_larger}, the Schedule H figure for "
        f"{irs_larger}"
        + (f", and {equal} show the same amount. " if equal else ". ")
        + f"For **{big}** of the {n} the two figures differ by more than 50% of the larger one."
    )
    lines.append("")
    lines.append(
        f"**† {counts['clean_multi_ccn_crosswalk']} rows are marked †.** For those, the CCN↔EIN crosswalk "
        "(December 2024 vintage) lists more than one CCN under the EIN, but only one of them has a "
        "cost report in the FY2022 or FY2023 HCRIS files, so the row compares that one cost report "
        "with the EIN's 990, and the total-expense test above still has to pass. "
        f"{unreported_ccn_sentence(sources)}. The JSON carries both counts "
        "(`ccns_with_cost_report`, `crosswalk_ccn_count`)."
    )
    lines.append("")
    lines.append("## The columns")
    lines.append("")
    lines.append(
        "- **7a (c) gross** — Schedule H Part I line 7a column (c): total community benefit expense "
        "for financial assistance at cost. Under the Schedule H instructions (Worksheet 1, line 4) a "
        "filer includes Medicaid or provider taxes here when payments from the state's uncompensated care pool "
        "or DSH program are intended primarily to offset the cost of financial assistance.\n"
        "- **7a (d) offset** — column (d): direct offsetting revenue. Under Worksheet 1 (lines 6 and 7) "
        "this is revenue from uncompensated care pools or programs plus other direct offsetting "
        "revenue. The return does not itemise it.\n"
        "- **7a (e) net** — column (e) = (c) − (d). This is the IRS figure in the comparison.\n"
        "- **S-10 L23** — Worksheet S-10 line 23 column 3: cost of charity care after patient "
        "payments. This is the CMS figure in the comparison. "
        "Columns 1 (uninsured) and 2 (insured) are in the JSON and CSV.\n"
        "- **S-10 L5** — Worksheet S-10 line 5: Medicaid DSH and supplemental payments not already in "
        "line 2, *net of associated provider taxes or assessments*. It is negative when the taxes "
        "netted against it exceed the payments. It is not part of S-10 line 23. The Schedule H "
        "instructions (Worksheet 1, line 4) let a filer include provider taxes in line 7a cost "
        "under a stated condition, so where line 5 is negative it is worth comparing with the "
        "difference.\n"
        "- **Net diff** — S-10 L23 − 7a (e). **Gross diff** — S-10 L23 − 7a (c). "
        "**%** — |net diff| as a share of the larger of the two net figures."
    )
    lines.append("")
    lines.append(
        "> A difference does not by itself show that either filing is incorrect. The two lines "
        "are defined differently and the forms give filers choices. Each row links to the exact "
        "Schedule H used, so the figures can be checked against the return. A blank cell means "
        "the form has no value on that line; it is never a reported $0."
    )
    lines.append("")
    lines.append(
        "| # | Hospital | St | 7a (c) gross | 7a (d) offset | 7a (e) net | S-10 L23 | S-10 L5 | Net diff | Gross diff | % | Period end | Sch. H |"
    )
    lines.append(
        "|--:|----------|----|-------------:|--------------:|-----------:|---------:|--------:|---------:|-----------:|--:|------------|--------|"
    )
    for i, r in enumerate(index, 1):
        pct = pct_text(r["gap_pct"])
        gross_diff = r["gap_gross"]
        lines.append(
            f"| {i} | {r['name']}{' †' if r['multi_ccn_crosswalk'] else ''} | {r['state'] or ''} | {usd(r['irs_7a_gross'])} | "
            f"{usd(r['irs_7a_offset'])} | {usd(r['irs_7a'])} | {usd(r['cms_s10'])} | "
            f"{usd(r['cms_s10_line5'])} | {'+' if r['gap'] > 0 else ''}{usd(r['gap'])} | "
            f"{'+' if gross_diff is not None and gross_diff > 0 else ''}{usd(gross_diff)} | "
            f"{pct} | {r['period_end']} | [990 ↗]({filing_url(r)}) |"
        )
    lines.append("")
    lines.append(
        "**Reading the sign:** a positive difference means the S-10 figure is larger than the Schedule H figure; negative means the Schedule H figure is larger."
    )
    lines.append("")
    lines.append("## Notes in the JSON")
    lines.append("")
    lines.append(
        "Each row of [`charity_care_gap_index_2022.json`](../web/data/charity_care_gap_index_2022.json) "
        "has a `notes` list of fixed codes. They are facts read off the filings and the crosswalk, "
        "not judgements:"
    )
    lines.append("")
    for code, text in NOTE_CODES.items():
        hits = sum(1 for r in index if code in r["notes"])
        lines.append(f"- `{code}` ({hits} row{'' if hits == 1 else 's'}) — {text}.")
    lines.append("")
    lines.append("## Why the two figures can differ")
    lines.append("")
    lines.append(
        "These are differences in what the two lines are defined to hold. None of them means "
        "a filing is incorrect."
    )
    lines.append("")
    lines.append(
        "- **Provider taxes and pool payments.** The Schedule H instructions (Worksheet 1, line 4) "
        "let a filer put Medicaid or provider taxes in line 7a column (c) when its state's "
        "uncompensated care pool or DSH payments are intended primarily to offset the cost of "
        "financial assistance, and report the pool revenue in column (d); otherwise both go to "
        "line 7b, and where state law does not make the purpose clear the instructions allow a "
        "proportional split. The cost report puts Medicaid DSH and supplemental payments, net of "
        "provider taxes, on S-10 line 5, outside line 23. Compare the S-10 L5 column with the "
        "difference."
    )
    lines.append(
        "- **Offsetting revenue.** Schedule H line 7a column (e) is net of direct offsetting "
        "revenue (column d); S-10 line 23 is net only of patient payments. The gross difference "
        "column shows the comparison before that offset."
    )
    lines.append(
        "- **Insured patients.** S-10 line 23 column 2 counts deductibles and coinsurance written "
        "off for insured patients. A hospital whose IRS figure is close to its S-10 uninsured "
        "column (column 1) will show a difference about the size of column 2."
    )
    lines.append(
        "- **Costing method.** S-10 applies the cost-to-charge ratio from the cost report; the "
        "Schedule H instructions let a filer use the ratio from their Worksheet 2 or a cost "
        "accounting method it considers more accurate."
    )
    lines.append("")
    lines.extend(worked_example(index, rows))
    lines.append("## Method & reproduction")
    lines.append("")
    lines.append(
        "Generated by [`scripts/build_gap_index.py`](../scripts/build_gap_index.py) "
        "from [`community_benefit_gap_2022.csv`](community_benefit_gap_2022.csv). "
        f"The full dataset ({counts['matched']:,} matched systems, {counts['computable']:,} computable) and its caveats are documented in "
        "[`community_benefit_gap_2022_summary.md`](community_benefit_gap_2022_summary.md). "
        f"{cms_vintage_sentence(sources)} (each cost report matched to the 990's own period) × "
        "IRS 990 Schedule H TY2022 (e-file releases 2023–2026). US-government-work source data, public domain."
    )
    lines.append("")
    lines.append("```bash")
    lines.append("uv run python scripts/build_gap_dataset.py   # builds the full gap CSV")
    lines.append("uv run python scripts/build_gap_index.py     # builds this index")
    lines.append("```")
    lines.append("")
    MD_OUT.write_text("\n".join(lines))


def _pctile(values, q):
    """Linear-interpolated percentile (same convention as numpy's default)."""
    v = sorted(values)
    if not v:
        return float("nan")
    k = (len(v) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def write_summary(rows, index, counts, sources):
    """Method + funnel + caveats for the full dataset, every number computed from the CSV."""

    def n(r, col):
        return _num(r.get(col))

    matched = counts["matched"]
    computable = [
        r
        for r in rows
        if n(r, "hcris_charity_care_cost") is not None
        and n(r, "sched_h_financial_assistance_at_cost") is not None
    ]
    aligned = [r for r in computable if r.get("period_aligned") == "True"]
    material = material_subset(aligned)
    s10_missing = [r for r in rows if n(r, "hcris_charity_care_cost") is None]
    s10_not_filed = [r for r in s10_missing if r.get("hcris_s10_filed") != "True"]
    partial = [r for r in s10_missing if n(r, "hcris_charity_care_cost_reporting_ccns") is not None]
    fa_missing = [r for r in rows if n(r, "sched_h_financial_assistance_at_cost") is None]
    md_rows = [r for r in rows if r.get("state") == "MD"]
    md_missing = [r for r in md_rows if n(r, "hcris_charity_care_cost") is None]
    unaligned = [r for r in rows if r.get("period_aligned") != "True"]
    multi = [r for r in rows if r.get("ccn_count") != "1"]
    # Crosswalk lists more CCNs for the EIN than have a cost report in the files.
    unreported = [r for r in rows if (n(r, "crosswalk_ccn_count") or 0) > (n(r, "ccn_count") or 0)]
    unreported_single = [r for r in unreported if r.get("ccn_count") == "1"]
    with_offset = [
        r for r in rows if (n(r, "sched_h_financial_assistance_offset_revenue") or 0) > 0
    ]
    inconsistent = [r for r in rows if r.get("sched_h_fa_7a_consistent") == "False"]
    line5 = [r for r in rows if n(r, "hcris_medicaid_dsh_supplemental") is not None]
    line5_neg = [r for r in line5 if n(r, "hcris_medicaid_dsh_supplemental") < 0]
    by_release = {}
    for r in rows:
        by_release[r.get("sched_h_release_year")] = (
            by_release.get(r.get("sched_h_release_year"), 0) + 1
        )
    by_status = {}
    for r in rows:
        for st in (r.get("hcris_report_status") or "").split(";"):
            if st:
                by_status[st] = by_status.get(st, 0) + 1

    def gaps(subset):
        return [abs(n(r, "charity_gap")) for r in subset]

    mp, mg = _abs_pcts(material), gaps(material)
    # ">= 0.5" to match totals.aligned_material_big_gaps in the site JSON
    # (scripts/build_web_data.py); the index's own "over 50%" count is a strict ">".
    over50 = sum(1 for v in mp if v >= 0.5)
    abs_gap = sum(mg)
    cb = sum(n(r, "sched_h_total_community_benefit") or 0 for r in material)
    cms_larger = sum(1 for r in material if n(r, "charity_gap") > 0)
    cols = list(rows[0].keys())

    def m(v):
        return f"${v / 1e6:.1f}M"

    L = []
    L.append(
        "# Community Benefit Cross-Form Dataset — TY2022 (CMS HCRIS S-10 × IRS 990 Schedule H)"
    )
    L.append("")
    L.append(
        "Generated by `scripts/build_gap_index.py` from `community_benefit_gap_2022.csv` — "
        "every number below is computed from that file; do not hand-edit."
    )
    L.append("")
    L.append("## What changed in this version")
    L.append("")
    L.append(
        "- **Missing is no longer published as $0.** CMS's numeric file never stores a zero, so an "
        "absent Worksheet S-10 line is *blank or zero*, not a reported $0. Earlier versions summed "
        "an all-missing S-10 into `0`; those cells are now empty and the difference is empty with them.\n"
        "- **The IRS 2023 e-file release is included.** It carries most calendar-year filers' TY2022 "
        "returns and was never ingested before. Releases 2023, 2024, 2025 and 2026 are all read, ZIP "
        "by ZIP, without relying on the IRS index to locate returns.\n"
        "- **Cost reports are matched to the 990's own fiscal period.** CMS files a cost report under "
        "the federal fiscal year in which its period *begins*, so the FY2023 file alone holds the "
        "right year only for October–December fiscal-year starts. The FY2022 and FY2023 files are now "
        "both loaded and, per CCN, the report ending closest to the 990's tax-period end is used. "
        "Worksheet S-10 is `S100000` for periods beginning before 2022-10-01 and `S100001` (Part I) "
        "after; the line and column numbers used are the same in both.\n"
        "- **Components are published**, not just two totals: Schedule H line 7a columns (c), (d), (e) "
        "and line 7b; S-10 line 23 columns 1–3, lines 20–22, and line 5; report status, period dates, "
        "CCNs, and the IRS object id of the exact return."
    )
    L.append("")
    L.append("## The funnel — read this first")
    L.append("")
    L.append(
        f"- **{matched:,} matched systems** (one row per EIN with a TY2022 Schedule H and at least one crosswalked CCN with a cost report)."
    )
    L.append(
        f"- **{len(computable):,} are computable** — both S-10 line 23 col 3 and Schedule H 7a col (e) are present. "
        f"Of the other {matched - len(computable):,}: {len(s10_missing):,} have no S-10 charity-care figure "
        f"({len(s10_not_filed):,} filed no Worksheet S-10 at all on at least one CCN; {len(partial):,} are multi-CCN "
        f"systems where only some CCNs report it — see `hcris_charity_care_cost_reporting_ccns`) and "
        f"{len(fa_missing):,} have a blank Schedule H 7a (some rows are both)."
    )
    L.append(
        f"- **{len(aligned):,} of the computable are period-aligned** — every CCN under the EIN has a cost report "
        f"ending within 1 calendar month of the 990's tax-period end. {len(unaligned):,} of all matched rows are "
        "not aligned (no cost report for that period in the FY2022/FY2023 files, or a multi-CCN system with a "
        "facility on a different fiscal year); they stay in the file with `period_aligned = False`."
    )
    L.append(
        f"- **{len(material):,} of those also have both figures ≥ ${SUMMARY_FLOOR // 1000}K** — a noise floor, not a comparability test. "
        "(A negative figure does not pass it.)"
    )
    L.append(
        f"- **{len(index)} are in the [ranked index](charity_care_gap_index_2022.md)** — one CCN with a cost report, "
        f"period-aligned, both figures ≥ $1M, total expenses within 5% — across {counts['clean_states']} states; "
        f"**{counts['clean_aligned_over_50pct']}** of them differ by more than 50%."
    )
    L.append("")
    L.append("## Method")
    L.append("")
    L.append(
        "For every EIN that appears in both the CBI CCN↔EIN crosswalk and the TY2022 Schedule H feed, the "
        "return of record is the full-year return with the latest period end, then the latest e-file timestamp "
        "(so an amendment supersedes the original). For each of the EIN's CCNs, the cost report whose period end "
        "is closest to that return's tax-period end is selected from the FY2022 and FY2023 HCRIS files; S-10 "
        "figures are summed across the EIN's CCNs."
    )
    L.append("")
    L.append("`charity_gap = S-10 line 23 col 3 − Schedule H Part I line 7a col (e)` (net basis)")
    L.append("")
    L.append(
        "`charity_gap_gross = S-10 line 23 col 3 − Schedule H Part I line 7a col (c)` (gross basis)"
    )
    L.append("")
    L.append(
        "Positive → the S-10 figure is larger. Both are empty when either side is. "
        f"{len(with_offset):,} matched rows report direct offsetting revenue on line 7a (column d), which is "
        "exactly the part of a net-basis difference that the gross basis removes."
    )
    L.append("")
    L.append(f"## Aligned + material subset ({len(material):,} systems)")
    L.append("")
    L.append(f"- Median absolute proportional difference: **{_pctile(mp, 0.5) * 100:.1f}%**")
    L.append(f"- **{over50} systems ({over50 / len(material) * 100:.0f}%)** differ by 50% or more")
    L.append(
        f"- S-10 figure larger in {cms_larger:,}; Schedule H figure larger in {len(material) - cms_larger - sum(1 for r in material if n(r, 'charity_gap') == 0):,}"
    )
    L.append(
        f"- **${abs_gap / 1e9:.2f}B** total absolute difference against **${cb / 1e9:.2f}B** Schedule H total community benefit (line 7k) reported by the same systems ({abs_gap / cb * 100:.1f}%)"
    )
    L.append("")
    L.append("**Absolute dollar difference (`|charity_gap|`):**")
    L.append("")
    L.append("| P25 | P50 (median) | P75 | P90 | Max |")
    L.append("|-----|--------------|-----|-----|-----|")
    L.append("| " + " | ".join(m(_pctile(mg, q)) for q in (0.25, 0.5, 0.75, 0.9, 1.0)) + " |")
    L.append("")
    L.append("**Proportional difference (`|charity_gap| / max(S-10, 7a)`):**")
    L.append("")
    L.append("| P25 | P50 (median) | P75 | P90 | Max |")
    L.append("|-----|--------------|-----|-----|-----|")
    L.append(
        "| "
        + " | ".join(f"{_pctile(mp, q) * 100:.1f}%" for q in (0.25, 0.5, 0.75, 0.9, 1.0))
        + " |"
    )
    L.append("")
    L.append(
        "This summary reports the distribution rather than a ranking; the ranked subset (single cost report, "
        "same fiscal period) is the [ranked index](charity_care_gap_index_2022.md)."
    )
    L.append("")
    L.append("## How to read a difference")
    L.append("")
    L.append(
        "Schedule H Part I line 7a is financial assistance at cost: column (c) total community benefit "
        "expense, column (d) direct offsetting revenue, column (e) net = (c) − (d). Worksheet S-10 line 23 "
        "column 3 is the cost of charity care after patient payments: uninsured patients (column 1) plus "
        "insured patients (column 2). The two lines are defined differently, so they can differ even when "
        "both are filed correctly. The components in the file show where to look:"
    )
    L.append("")
    L.append(
        "- **Medicaid supplemental payments and provider taxes.** S-10 line 5 (`hcris_medicaid_dsh_supplemental`) is "
        f"Medicaid DSH/supplemental payments net of provider taxes; it is present on {len(line5):,} matched rows and "
        f"negative on {len(line5_neg):,}. It is not part of S-10 line 23. The Schedule H instructions "
        "(Worksheet 1, line 4) let a filer include provider taxes in line 7a cost under a stated condition, so where "
        "line 5 is negative it is worth comparing with the difference.\n"
        "- **Offsetting revenue.** Schedule H 7a column (e) is net of direct offsetting revenue (column d); "
        "S-10 line 23 is net only of patient payments. Compare `charity_gap_gross` with `charity_gap`.\n"
        "- **Insured patients.** S-10 line 23 column 2 (`hcris_charity_care_cost_insured`) counts deductibles and "
        "coinsurance written off for insured patients; column 1 (`hcris_charity_care_cost_uninsured`) is uninsured "
        "patients only. Compare the Schedule H figure with each.\n"
        "- **Costing method.** S-10 applies the cost-to-charge ratio from the cost report; the Schedule H "
        "instructions let a filer use the ratio from their Worksheet 2 or a cost accounting method it considers "
        "more accurate.\n"
        "- **Return arithmetic.** `sched_h_fa_7a_consistent` is False where the return's own line 7a does not "
        f"satisfy (c) − (d) = (e) ({len(inconsistent):,} matched rows); on those rows the difference rests on a "
        "figure that cannot be read at face value."
    )
    L.append("")
    L.append(
        "S-10 charity care is **all-payer**, so a difference where the Schedule H figure is the larger one is not "
        f"explained by low Medicare volume. **Missing is not zero:** {len(s10_missing):,} matched rows have no S-10 "
        f"line 23 figure ({len(s10_not_filed):,} of them with no Worksheet S-10 at all on at least one CCN)"
        + (
            f", including {len(md_missing):,} of the {len(md_rows):,} Maryland rows"
            if md_rows and md_missing
            else ""
        )
        + ". Those rows are empty here, never $0, and no difference is computed for them."
    )
    L.append("")
    L.append("## Files")
    L.append("")
    L.append(
        f"- [`community_benefit_gap_2022.csv`](community_benefit_gap_2022.csv) — full {matched:,}-row table (alphabetical by filer name), {len(cols)} columns"
    )
    L.append(
        "- [`charity_care_gap_index_2022.md`](charity_care_gap_index_2022.md) — the ranked subset (single cost report, same fiscal period) with components"
    )
    L.append("")
    L.append("### Columns")
    L.append("")
    L.append(
        "The first 20 columns are unchanged from earlier versions (same names, same order); the rest are new."
    )
    L.append("")
    L.append("`" + "`, `".join(cols) + "`")
    L.append("")
    L.append(
        "`ccn_list` and `hcris_rpt_rec_num` are `;`-joined, lead facility (largest operating expenses) first. "
        "`hcris_fy_bgn_dt` / `hcris_fy_end_dt` are the dates of the worst-matching CCN's report, so a date "
        "comparison on a multi-CCN row agrees with `period_aligned`. Read `ein`, `ccn_list` and "
        "`sched_h_object_id` as text (leading zeros, 18 digits)."
    )
    L.append("")
    L.append("## Home-county SVI columns (proxy)")
    L.append("")
    L.append(
        "Each row carries `svi_overall_pct` (0-100) plus four sub-theme percentiles. These are county-level "
        "CDC/ATSDR Social Vulnerability Index 2022 ranks for the home county of each facility, taken as the median "
        "across a system's facilities. This is a **home-county proxy**, not a catchment-area measure; do not use it "
        "to infer service-area need or the adequacy of charity care. CDC SVI is US government work, public domain."
    )
    L.append("")
    L.append("## Coverage and caveats")
    L.append("")
    L.append(
        f"- **Sources and vintage.** {cms_vintage_sentence(sources)} "
        "(extract date: the timestamps of the files inside the CMS ZIPs; posted date: the "
        "Last-Modified date of the CMS download). "
        "The FY2024 file was checked and adds no period-matched report. "
        "IRS e-file releases 2023–2026; "
        "returns used, by release: "
        + ", ".join(f"{k}: {v:,}" for k, v in sorted(by_release.items()))
        + ".\n"
        "- **Cost report status** of the reports used (a multi-CCN row counts once per distinct status): "
        + ", ".join(
            f"{k.replace('_', ' ')}: {v:,}"
            for k, v in sorted(by_status.items(), key=lambda kv: -kv[1])
        )
        + ". As-submitted and amended reports can still change.\n"
        "- **Alignment is end-date based** (within 1 calendar month). In the index the total-expense test additionally "
        "screens out stub periods and scope mismatches; the full file does not apply it.\n"
        f"- **Multi-facility EINs.** {len(multi):,} rows roll more than one CCN into one EIN; the row is named for "
        "the largest facility. System-level sums can hide facility-level differences. `hcris_charity_care_cost` "
        "is empty if any CCN lacks line 23.\n"
        f"- **Crosswalk CCNs with no cost report.** `ccn_count` counts the EIN's CCNs that have a cost report in the "
        f"FY2022/FY2023 files; `crosswalk_ccn_count` counts the CCNs the crosswalk lists. They differ on "
        f"{len(unreported):,} rows ({len(unreported_single):,} of them with `ccn_count` = 1). S-10 figures are summed "
        "over the CCNs that have a report, so a CCN with no report at all contributes nothing and does not empty the "
        f'total. {unreported_ccn_sentence(sources)}. Either way, `ccn_count` = 1 means "one CCN with a cost '
        'report", not "the crosswalk lists one facility".\n'
        "- **Crosswalk.** The CBI CCN↔EIN crosswalk is frozen at its December 2024 vintage (2,385 EINs). Hospitals "
        "that are for-profit, government-owned without a 990, covered only by a group return under another EIN, or "
        "missing from CBI are not matched.\n"
        "- **Short-year returns.** Where an EIN filed both a full-year and a short-year return on TY2022 forms, the "
        "full-year return is used.\n"
        "- **Parser validation.** The Yale New Haven Hospital row (EIN 060646652, CCN 070022, period ending 2023-09-30) "
        "is pinned in the test suite against both source filings to the dollar."
    )
    L.append("")
    L.append("Reproduce with:")
    L.append("")
    L.append("```bash")
    L.append("uv run python scripts/build_gap_dataset.py")
    L.append("uv run python scripts/build_gap_index.py")
    L.append(
        "uv run python scripts/build_web_data.py && uv run python scripts/build_web_bundles.py"
    )
    L.append("```")
    L.append("")
    SUMMARY_OUT.write_text("\n".join(L))


def keep_source_xml(index, top=50):
    """Copy the raw 990 XML behind the top rows into ``data/raw/form990/xml_keep/``.

    A local evidence trail (``data/`` is gitignored): a no-op when the full
    ``xml_ty2022`` cache written by build_gap_dataset.py is not on disk.
    """
    if not XML_ALL.is_dir():
        return 0
    XML_KEEP.mkdir(parents=True, exist_ok=True)
    kept = 0
    for r in index[:top]:
        src = XML_ALL / f"{r['object_id']}_public.xml"
        if r.get("object_id") and src.exists():
            (XML_KEEP / src.name).write_bytes(src.read_bytes())
            kept += 1
    return kept


def _usd_axis(v):
    """Axis tick label: $1M, $10M, $100M — no decimals, they're log decades."""
    if v >= 1e9:
        return f"${v / 1e9:.0f}B"
    if v >= 1e6:
        return f"${v / 1e6:.0f}M"
    return f"${v / 1e3:.0f}K"


def _overlap(a, b):
    """Do two (x0, y0, x1, y1) boxes intersect?"""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _place_labels(named, dots, plot, taken, char_w=6.7, height=14):
    """Pick a spot beside each named dot for its label.

    ``named`` is [(x, y, text)], ``dots`` every dot's (x, y), ``plot`` the plot box,
    ``taken`` boxes labels must avoid (the legend). For each label eight positions
    around the dot are tried; positions that leave the plot or hit an earlier label
    are rejected, and of the rest the one covering the fewest dots wins. Returns
    [(x, y, text, anchor, lx, ly)] where (lx, ly) is the text position.
    """
    placed = []
    boxes = list(taken)
    rings = [(nx - 9, ny - 9, nx + 9, ny + 9) for nx, ny, _ in named]
    for i, (x, y, text) in enumerate(named):
        others = rings[:i] + rings[i + 1 :]
        w = len(text) * char_w
        gap = 9
        options = []
        # Nearest positions first: beside the dot, then diagonally off it, then
        # centred above/below, then one more step out.
        for dy in (4, -9, 17):
            for anchor, dx in (("start", gap), ("end", -gap)):
                options.append((anchor, x + dx, y + dy))
        for dy in (-13, 23):
            options.append(("middle", x, y + dy))
        for dy in (-22, 30):
            for anchor, dx in (("start", gap), ("end", -gap)):
                options.append((anchor, x + dx, y + dy))
        best = None
        for order, (anchor, lx, ly) in enumerate(options):
            x0 = lx if anchor == "start" else lx - w if anchor == "end" else lx - w / 2
            box = (x0 - 2, ly - height + 3, x0 + w + 2, ly + 3)
            if box[0] < plot[0] or box[2] > plot[2] or box[1] < plot[1] or box[3] > plot[3]:
                continue
            if any(_overlap(box, b) for b in boxes + others):
                continue
            covered = sum(
                1 for dx_, dy_ in dots if box[0] <= dx_ <= box[2] and box[1] <= dy_ <= box[3]
            )
            if best is None or (covered, order) < best[0]:
                best = ((covered, order), anchor, lx, ly, box)
        if best is None:
            continue  # no clean spot: leave the dot unlabeled rather than collide
        _, anchor, lx, ly, box = best
        boxes.append(box)
        placed.append((x, y, text, anchor, lx, ly))
    return placed


def svg_chart(index):
    """A log-log scatter of the two reported figures, one dot per hospital.

    The form follows the data's job. Both axes carry the same unit (dollars of
    charity-care cost), so they share one scale and one range — that is what makes
    the 45-degree parity line meaningful: a hospital reporting the same number to
    both forms lands exactly on it; distance from the line is the difference.
    Two axes of the same measure is the opposite of a dual-axis chart; forcing
    independent scales here would manufacture the very divergence being measured.

    Color encodes polarity (which form shows the larger number), diverging from
    the parity line as a neutral midpoint; the legend carries it in words and
    position (above / below the diagonal) carries it without color.

    Sized for several hundred dots: small translucent marks with a thin surface
    ring so dense regions read as density instead of a solid blob, and two faint
    guide lines where one figure is twice the other, so "differs by more than
    half" is visible as a band rather than something to estimate.

    Only ``CHART_LABELS`` dots are named — the largest absolute dollar differences,
    a rule stated in the caption, not a selection. Everything else is identified
    on hover/tap and in the ranked table beside the chart.

    Log scale because the values span more than two orders of magnitude from the
    $1M floor; a linear axis would pack most hospitals into the bottom-left corner.
    """
    pts = [r for r in index if r["irs_7a"] > 0 and r["cms_s10"] > 0]
    if not pts:
        return ""

    W, H = 720, 600
    M = {"t": 24, "r": 20, "b": 66, "l": 92}
    pw, ph = W - M["l"] - M["r"], H - M["t"] - M["b"]

    lo = min(min(p["irs_7a"], p["cms_s10"]) for p in pts) * 0.8
    hi = max(max(p["irs_7a"], p["cms_s10"]) for p in pts) * 1.25
    l10, h10 = math.log10(lo), math.log10(hi)

    def sx(v):
        return M["l"] + (math.log10(v) - l10) / (h10 - l10) * pw

    def sy(v):
        return M["t"] + ph - (math.log10(v) - l10) / (h10 - l10) * ph

    ticks = [t for t in (1e6, 2e6, 5e6, 1e7, 2e7, 5e7, 1e8, 2e8, 5e8, 1e9) if lo <= t <= hi]
    over = sum(1 for p in pts if p["gap_pct"] is not None and p["gap_pct"] > 0.5)
    above = sum(1 for p in pts if p["gap"] > 0)
    below = sum(1 for p in pts if p["gap"] < 0)

    o = []
    o.append(
        f'<svg class="gapchart" viewBox="0 0 {W} {H}" role="img" '
        f'aria-labelledby="gapchart-t gapchart-d" preserveAspectRatio="xMidYMid meet">'
    )
    o.append(
        '<title id="gapchart-t">CMS S-10 line 23 against IRS Schedule H line 7a, '
        f"{len(pts)} hospitals, tax year 2022</title>"
    )
    o.append(
        f'<desc id="gapchart-d">Scatter plot with logarithmic axes from {_usd_axis(ticks[0])} to '
        f"{_usd_axis(ticks[-1])}. Each of the {len(pts)} dots is one hospital: horizontal position "
        "is the amount on IRS Form 990 Schedule H line 7a, vertical position the amount on CMS "
        "Worksheet S-10 line 23. On the diagonal the two amounts are equal. "
        f"{above} dots are above it (larger amount on the CMS form) and {below} below it (larger "
        f"amount on the IRS form). {over} dots lie outside the two guide lines that mark where one "
        "amount is twice the other. Every hospital and both amounts are listed in the table on "
        "this page.</desc>"
    )

    # Grid — hairline, solid, recessive. Never dashed.
    for t in ticks:
        o.append(
            f'<line class="grid" x1="{sx(t):.1f}" y1="{M["t"]}" '
            f'x2="{sx(t):.1f}" y2="{M["t"] + ph}"/>'
        )
        o.append(
            f'<line class="grid" x1="{M["l"]}" y1="{sy(t):.1f}" '
            f'x2="{M["l"] + pw}" y2="{sy(t):.1f}"/>'
        )
        o.append(
            f'<text class="tick tick-x" x="{sx(t):.1f}" y="{M["t"] + ph + 23}">'
            f"{_usd_axis(t)}</text>"
        )
        o.append(
            f'<text class="tick tick-y" x="{M["l"] - 10}" y="{sy(t) + 4:.1f}">{_usd_axis(t)}</text>'
        )

    # Guide lines where one figure is exactly twice the other (a 50% difference),
    # clipped to the plot. Fainter than the parity line they flank.
    o.append(
        f'<line class="half" x1="{sx(lo):.1f}" y1="{sy(lo * 2):.1f}" '
        f'x2="{sx(hi / 2):.1f}" y2="{sy(hi):.1f}"/>'
    )
    o.append(
        f'<line class="half" x1="{sx(lo * 2):.1f}" y1="{sy(lo):.1f}" '
        f'x2="{sx(hi):.1f}" y2="{sy(hi / 2):.1f}"/>'
    )
    # Parity line — the neutral reference the whole chart is read against.
    o.append(
        f'<line class="parity" x1="{sx(lo):.1f}" y1="{sy(lo):.1f}" '
        f'x2="{sx(hi):.1f}" y2="{sy(hi):.1f}"/>'
    )
    # Legend, top-left, in the one corner the cloud leaves empty. Every key is a
    # swatch or a line-key beside muted text — identity never comes from coloring
    # the text, and never from color alone.
    lx, ly = M["l"] + 14, M["t"] + 16
    legend = (
        ("parity", "on the diagonal: the two amounts are equal"),
        ("half", "guide lines: one amount is twice the other"),
        ("pos", f"above the diagonal: larger on the CMS form ({above})"),
        ("neg", f"below the diagonal: larger on the IRS form ({below})"),
    )
    o.append('<g class="legend">')
    for i, (kind, text) in enumerate(legend):
        y = ly + i * 19
        if kind in ("parity", "half"):
            o.append(f'<line class="{kind}" x1="{lx}" y1="{y}" x2="{lx + 16}" y2="{y}"/>')
        else:
            o.append(f'<circle class="swatch {kind}" cx="{lx + 8}" cy="{y}" r="4.5"/>')
        o.append(f'<text class="region" x="{lx + 24}" y="{y + 4}">{text}</text>')
    o.append("</g>")
    legend_box = (lx - 6, ly - 12, lx + 24 + max(len(t) for _, t in legend) * 6.7, ly + 3 * 19 + 10)

    # Dots above the grid. Smallest differences first so the largest sit on top.
    xy = [(sx(p["irs_7a"]), sy(p["cms_s10"])) for p in pts]
    for p, (cx, cy) in sorted(zip(pts, xy, strict=True), key=lambda t: abs(t[0]["gap"])):
        cls = "pos" if p["gap"] > 0 else "neg" if p["gap"] < 0 else "eq"
        pct = pct_text(p["gap_pct"])
        place = ", ".join(x for x in (p.get("city"), p.get("state")) if x)
        o.append(
            f'<circle class="dot {cls}" cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" '
            f'data-n="{html.escape(p["name"], quote=True)}" '
            f'data-p="{html.escape(place, quote=True)}" '
            # usd(), not the axis formatter — the tooltip must match the $113.1M
            # precision used in the table and prose, not round to whole millions.
            f'data-irs="{usd(p["irs_7a"])}" data-cms="{usd(p["cms_s10"])}" '
            f'data-pct="{pct}" data-end="{p["period_end"]}"/>'
        )

    # Names for the few largest dollar differences, each with a ring on its dot.
    top = sorted(zip(pts, xy, strict=True), key=lambda t: -abs(t[0]["gap"]))[:CHART_LABELS]
    plot = (M["l"] + 2, M["t"] + 2, M["l"] + pw - 2, M["t"] + ph - 2)
    for _, (cx, cy) in top:
        o.append(f'<circle class="ring" cx="{cx:.1f}" cy="{cy:.1f}" r="6.5"/>')
    for cx, cy, text, anchor, tx, ty in _place_labels(
        [(cx, cy, p["name"]) for p, (cx, cy) in top], xy, plot, [legend_box]
    ):
        # Leader from the ring to the near end of the label when they are apart.
        ex = tx - 3 if anchor == "start" else tx + 3 if anchor == "end" else tx
        ey = ty - 4 if anchor != "middle" else (ty + 3 if ty < cy else ty - 11)
        dist = math.hypot(ex - cx, ey - cy)
        if dist > 13:
            ux, uy = (ex - cx) / dist, (ey - cy) / dist
            o.append(
                f'<line class="lead" x1="{cx + ux * 7.5:.1f}" y1="{cy + uy * 7.5:.1f}" '
                f'x2="{ex:.1f}" y2="{ey:.1f}"/>'
            )
        o.append(
            f'<text class="name" x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anchor}">'
            f"{html.escape(text)}</text>"
        )

    o.append(
        f'<text class="axis-title" x="{M["l"] + pw / 2:.0f}" y="{H - 12}">'
        "IRS Schedule H line 7a (e), financial assistance at cost</text>"
    )
    o.append(
        f'<text class="axis-title" transform="translate(18,{M["t"] + ph / 2:.0f}) rotate(-90)" '
        'x="0" y="0">CMS Worksheet S-10 line 23, cost of charity care</text>'
    )
    o.append("</svg>")
    return "\n".join(o)


CHART_CSS = f"""
<style>
  .gapfig {{ margin: 2rem 0; }}
  .gapfig figcaption {{ color: var(--muted); font-size: 0.85rem; line-height: 1.5; margin-top: 0.6rem; }}
  .gapchart {{ width: 100%; height: auto; display: block; overflow: visible; touch-action: pan-y;
    --mark-pos: {MARK_POS_LIGHT}; --mark-neg: {MARK_NEG_LIGHT};
    --grid: rgba(127,127,127,0.2); --parity: rgba(100,100,100,0.75); --half: rgba(127,127,127,0.42); }}
  @media (prefers-color-scheme: dark) {{
    .gapchart {{ --mark-pos: {MARK_POS_DARK}; --mark-neg: {MARK_NEG_DARK};
      --grid: rgba(255,255,255,0.11); --parity: rgba(255,255,255,0.55); --half: rgba(255,255,255,0.26); }}
  }}
  .gapchart .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .gapchart .parity {{ stroke: var(--parity); stroke-width: 1.5; }}
  .gapchart .half {{ stroke: var(--half); stroke-width: 1; }}
  .gapchart .tick, .gapchart .axis-title, .gapchart .region, .gapchart .name {{
    font-family: ui-monospace, Menlo, monospace; }}
  .gapchart .tick, .gapchart .axis-title, .gapchart .region {{ fill: var(--muted); }}
  .gapchart .tick {{ font-size: 12px; }}
  .gapchart .tick-x {{ text-anchor: middle; }}
  .gapchart .tick-y {{ text-anchor: end; }}
  .gapchart .axis-title {{ font-size: 12.5px; text-anchor: middle; }}
  .gapchart .region {{ font-size: 11.5px; text-anchor: start; }}
  .gapchart .name {{ font-size: 11px; fill: var(--fg); stroke: var(--bg); stroke-width: 3.5;
    stroke-linejoin: round; paint-order: stroke; pointer-events: none; }}
  .gapchart .ring {{ fill: none; stroke: var(--fg); stroke-width: 1.25; pointer-events: none; }}
  .gapchart .lead {{ stroke: var(--fg); stroke-width: 0.75; stroke-opacity: 0.65; pointer-events: none; }}
  .gapkey {{ display: none; list-style: none; margin: 0.5rem 0 0; padding: 0; color: var(--muted);
    font: 0.78rem/1.6 ui-monospace, Menlo, monospace; }}
  .gapkey i {{ display: inline-block; width: 0.65rem; height: 0.65rem; border-radius: 50%;
    margin-right: 0.45rem; vertical-align: -0.05rem; }}
  .gapkey i.pos {{ background: {MARK_POS_LIGHT}; }}
  .gapkey i.neg {{ background: {MARK_NEG_LIGHT}; }}
  .gapkey i.ln {{ height: 0; border-radius: 0; border-top: 2px solid var(--muted); vertical-align: 0.25rem; }}
  .gapkey i.ln.half {{ border-top-width: 1px; opacity: 0.7; }}
  @media (prefers-color-scheme: dark) {{
    .gapkey i.pos {{ background: {MARK_POS_DARK}; }}
    .gapkey i.neg {{ background: {MARK_NEG_DARK}; }}
  }}
  /* Phones: the SVG is scaled to about half size, so its text is enlarged, the
     in-plot legend moves below the chart as HTML, and the five names (placed for
     the wide layout) are dropped; their rings stay. */
  @media (max-width: 560px) {{
    .gapchart .tick {{ font-size: 18px; }}
    .gapchart .axis-title {{ font-size: 19px; }}
    .gapchart .legend, .gapchart .name, .gapchart .lead {{ display: none; }}
    .gapchart .dot {{ r: 4.5; }}
    .gapchart .ring {{ r: 8.5; stroke-width: 2; }}
    .gapkey {{ display: block; }}
  }}
  .gapchart .swatch {{ stroke: var(--bg); stroke-width: 1.5; }}
  .gapchart .swatch.pos {{ fill: var(--mark-pos); }}
  .gapchart .swatch.neg {{ fill: var(--mark-neg); }}
  .gapchart .dot {{ stroke: var(--bg); stroke-width: 0.75; fill-opacity: 0.78; }}
  .gapchart .dot.pos {{ fill: var(--mark-pos); }}
  .gapchart .dot.neg {{ fill: var(--mark-neg); }}
  .gapchart .dot.eq {{ fill: var(--muted); }}
  .gapchart .dot.hl {{ r: 6.5; fill-opacity: 1; stroke: var(--fg); stroke-width: 1.5; }}
  .gaptip {{ position: fixed; z-index: 20; pointer-events: none; opacity: 0;
    transition: opacity 0.1s; background: var(--bg); color: var(--fg);
    border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem 0.7rem;
    font: 12px/1.5 ui-monospace, Menlo, monospace; max-width: 18rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.18); }}
  .gaptip b {{ display: block; margin-bottom: 0.2rem; }}
  .gaptip span {{ display: block; }}
  .gaptip .sub {{ color: var(--muted); }}
  @media (forced-colors: active) {{
    .gapchart .dot.pos {{ fill: CanvasText; }}
    .gapchart .dot.neg {{ fill: Canvas; stroke: CanvasText; stroke-width: 1; }}
  }}
</style>
"""

# The tooltip finds the NEAREST dot within reach of the pointer rather than waiting
# for the pointer to be exactly on a 7px mark, and builds its content with
# textContent — hospital names come from a federal filing, never from innerHTML.
CHART_JS = """
<script>
(function () {
  var svg = document.querySelector('.gapchart');
  if (!svg || !svg.createSVGPoint) return;
  var dots = Array.prototype.map.call(svg.querySelectorAll('.dot'), function (el) {
    return { el: el, x: +el.getAttribute('cx'), y: +el.getAttribute('cy') };
  });
  var tip = document.createElement('div');
  tip.className = 'gaptip';
  tip.setAttribute('role', 'status');
  document.body.appendChild(tip);
  var current = null;
  var REACH = 16;
  function line(cls, text) {
    var s = document.createElement(cls === 'b' ? 'b' : 'span');
    if (cls && cls !== 'b') s.className = cls;
    s.textContent = text;
    tip.appendChild(s);
  }
  function clear() {
    if (current) current.el.classList.remove('hl');
    current = null;
    tip.style.opacity = '0';
  }
  function nearest(e) {
    var ctm = svg.getScreenCTM();
    if (!ctm) return null;
    var pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    var p = pt.matrixTransform(ctm.inverse());
    var best = null, bestD = REACH * REACH;
    for (var i = 0; i < dots.length; i++) {
      var dx = dots[i].x - p.x, dy = dots[i].y - p.y, d = dx * dx + dy * dy;
      if (d <= bestD) { bestD = d; best = dots[i]; }
    }
    return best;
  }
  function onMove(e) {
    var hit = nearest(e);
    if (!hit) { clear(); return; }
    if (hit !== current) {
      if (current) current.el.classList.remove('hl');
      current = hit;
      hit.el.classList.add('hl');
      var d = hit.el.dataset;
      tip.textContent = '';
      line('b', d.n);
      if (d.p) line('sub', d.p);
      line('', 'IRS Schedule H 7a: ' + d.irs);
      line('', 'CMS Worksheet S-10: ' + d.cms);
      line('sub', 'differ by ' + d.pct + ' \\u00b7 period ended ' + d.end);
      tip.style.opacity = '1';
    }
    var r = tip.getBoundingClientRect();
    var x = Math.max(8, Math.min(e.clientX + 14, window.innerWidth - r.width - 8));
    var y = e.clientY - r.height - 12;
    if (y < 8) y = e.clientY + 18;
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }
  svg.addEventListener('pointermove', onMove);
  svg.addEventListener('pointerdown', onMove);
  svg.addEventListener('pointerleave', clear);
  window.addEventListener('scroll', clear, { passive: true });
})();
</script>
"""


class ChartMarkerError(RuntimeError):
    """A chart target page is missing, or its GAP_CHART markers are not usable."""


def chart_fragment(index):
    """Everything that goes between the markers, markers included."""
    n = len([r for r in index if r["irs_7a"] > 0 and r["cms_s10"] > 0])
    big = sum(1 for r in index if r["gap_pct"] and r["gap_pct"] > 0.5)
    above = sum(1 for r in index if r["gap"] > 0 and r["irs_7a"] > 0 and r["cms_s10"] > 0)
    below = sum(1 for r in index if r["gap"] < 0 and r["irs_7a"] > 0 and r["cms_s10"] > 0)
    key = (
        '<ul class="gapkey" aria-hidden="true">'
        '<li><i class="ln"></i>on the diagonal: the two amounts are equal</li>'
        '<li><i class="ln half"></i>guide lines: one amount is twice the other</li>'
        f'<li><i class="pos"></i>above it: larger on the CMS form ({above})</li>'
        f'<li><i class="neg"></i>below it: larger on the IRS form ({below})</li>'
        "</ul>"
    )
    return (
        f'{CHART_START}\n{CHART_CSS}\n<figure class="gapfig">\n{svg_chart(index)}\n{key}\n'
        f"<figcaption>Each dot is one of the {n} hospitals in the index: one CCN with a "
        f"cost report, periods ending within a month of each other, both figures at "
        f"least $1M, and total expenses within 5%. A hospital whose two lines show the "
        f"same amount sits on the diagonal. The two fainter lines mark where "
        f"one amount is twice the other; {big} hospitals are outside them, meaning the "
        f"two figures differ by more than half. Both axes are log-scaled. The "
        f"{CHART_LABELS} ringed dots are the {CHART_LABELS} largest dollar differences, "
        f"picked by that rule alone; they are named on wider screens and are the first "
        f"{CHART_LABELS} rows of the table. Hover or tap any dot for the hospital and "
        f"its two figures; all {n} are in the table. "
        f"Sources: CMS HCRIS Worksheet S-10 (FY2022 and FY2023 files) and IRS Form 990 "
        f"Schedule H (TY2022).</figcaption>\n</figure>\n{CHART_JS}\n{CHART_END}"
    )


def splice_chart(text, fragment, where="page"):
    """Return ``text`` with everything from the START to the END marker replaced.

    Raises ChartMarkerError unless ``text`` holds exactly one START marker and
    exactly one END marker, with START first. A page with no markers, a
    half-deleted pair or a duplicated pair is never guessed at.
    """
    starts, ends = text.count(CHART_START), text.count(CHART_END)
    if starts != 1 or ends != 1:
        raise ChartMarkerError(
            f"{where}: expected exactly one {CHART_START} and one {CHART_END}, "
            f"found {starts} and {ends}"
        )
    a, b = text.index(CHART_START), text.index(CHART_END)
    if b < a:
        raise ChartMarkerError(f"{where}: {CHART_END} comes before {CHART_START}")
    return text[:a] + fragment + text[b + len(CHART_END) :]


def write_chart(index, targets=CHART_TARGETS):
    """Inject the generated figure between markers on every target page.

    Marker-delimited so the chart is regenerated, never hand-maintained — the same
    reason sitemap.xml lives in a build script. All targets are checked before any
    is written: a missing page or unusable markers raises ChartMarkerError and
    leaves every page untouched.
    """
    fragment = chart_fragment(index)
    if not svg_chart(index):
        raise ChartMarkerError("no plottable rows; refusing to inject an empty chart")
    updated = []
    for path in targets:
        if not path.exists():
            raise ChartMarkerError(f"{path}: chart target page does not exist")
        updated.append((path, splice_chart(path.read_text(), fragment, where=str(path))))
    for path, text in updated:
        path.write_text(text)
    return [path for path, _ in updated]


def write_json(index, counts, sources):
    payload = {
        "tax_year": 2022,
        "filter": {
            "ccn_count": 1,
            "alignment_months_max": ALIGNMENT_MONTHS,
            "material_floor_usd": MATERIAL_FLOOR,
            "expense_base_tolerance": EXPENSE_BASE_TOLERANCE,
            "description": "One CCN with a cost report in the HCRIS files used (ccn_count == 1; the crosswalk may list more, see multi_ccn_crosswalk), period-aligned, material (>=$1M both sides), same-scale (expense bases within 5%).",
        },
        "sources": {
            "cms": "HCRIS Hospital 2552-10, FY2022 and FY2023 files; Worksheet S-10 (S100000 for periods beginning before 2022-10-01, S100001 Part I after)",
            "irs": "Form 990 Schedule H, tax year 2022, e-file releases 2023-2026",
            # What the source files say about their own vintage (build_gap_dataset.py).
            "cms_files": sources["cms_hcris"]["files"],
            "crosswalk": sources.get("crosswalk"),
        },
        "fields": {
            "irs_7a": "Schedule H Part I line 7a col (e), net community benefit expense",
            "irs_7a_gross": "Schedule H Part I line 7a col (c), total community benefit expense",
            "irs_7a_offset": "Schedule H Part I line 7a col (d), direct offsetting revenue",
            "irs_7b": "Schedule H Part I line 7b (Medicaid) col (e); _gross is col (c), _offset col (d)",
            "cms_s10": "Worksheet S-10 line 23 col 3, cost of charity care",
            "cms_s10_uninsured": "Worksheet S-10 line 23 col 1",
            "cms_s10_insured": "Worksheet S-10 line 23 col 2",
            "cms_s10_charges": "Worksheet S-10 line 20 col 3",
            "cms_s10_cost_before_payments": "Worksheet S-10 line 21 col 3",
            "cms_s10_payments": "Worksheet S-10 line 22 col 3",
            "cms_s10_line5": "Worksheet S-10 line 5, Medicaid DSH/supplemental payments net of provider taxes (can be negative)",
            "irs_7a_consistent": "whether (c) - (d) = (e) within $1 on the return itself; null when (c) is blank",
            "ccns_with_cost_report": "CCNs under the EIN that have a cost report in the HCRIS files used; always 1 in this index",
            "crosswalk_ccn_count": "CCNs the CCN-EIN crosswalk lists for the EIN; can exceed ccns_with_cost_report",
            "multi_ccn_crosswalk": "true when crosswalk_ccn_count > 1: the crosswalk lists further CCNs that have no cost report in the HCRIS files used",
            "notes": "list of fixed codes (see note_codes) that apply to the row; mechanical facts for display, not judgements; empty list when none apply",
            "gap": "cms_s10 - irs_7a",
            "gap_gross": "cms_s10 - irs_7a_gross",
            "gap_pct": "abs(gap) / max(cms_s10, irs_7a)",
            "null": "a null is a line with no value on the form, never a reported $0",
        },
        "note_codes": NOTE_CODES,
        "counts": {
            # The first two keys are read by the site; keep them.
            "clean_aligned": counts["clean_aligned"],
            "clean_aligned_over_50pct": counts["clean_aligned_over_50pct"],
            "matched": counts["matched"],
            "computable": counts["computable"],
            "aligned": counts["aligned"],
            "aligned_single_facility": counts["aligned_single_facility"],
            "clean_states": counts["clean_states"],
            "clean_multi_ccn_crosswalk": counts["clean_multi_ccn_crosswalk"],
            # Aligned rows with both figures >= $500K (the summary's noise floor),
            # and how many of those differ by 50% or more.
            "aligned_material": counts["aligned_material"],
            "aligned_material_50pct_or_more": counts["aligned_material_50pct_or_more"],
            "notes": {code: sum(1 for r in index if code in r["notes"]) for code in NOTE_CODES},
        },
        "rows": index,
    }
    JSON_OUT.write_text(json.dumps(payload, separators=(",", ":")))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--inject-chart",
        action="store_true",
        help="rewrite the scatter chart between GAP_CHART markers in the site's HTML pages",
    )
    args = ap.parse_args()

    rows = load_rows()
    index = clean_index(rows)
    counts = funnel(rows, index)
    sources = load_sources()
    write_markdown(index, rows, counts, sources)
    write_summary(rows, index, counts, sources)
    write_json(index, counts, sources)
    print(
        f"{len(index)} clean+aligned hospitals -> {MD_OUT.relative_to(ROOT)} and {JSON_OUT.relative_to(ROOT)}"
    )
    print(
        "  funnel: matched {matched:,} -> computable {computable:,} -> aligned {aligned:,} "
        "(single-facility {aligned_single_facility:,}) -> clean {clean_aligned:,} "
        "-> over 50% {clean_aligned_over_50pct:,}; {clean_states} states".format(**counts)
    )
    print(
        "  aligned, both >= $500K: {aligned_material:,} ({aligned_material_50pct_or_more:,} differ "
        "by 50% or more); index rows with a multi-CCN crosswalk EIN: "
        "{clean_multi_ccn_crosswalk}".format(**counts)
    )
    print(
        "  notes: "
        + ", ".join(f"{c} {sum(1 for r in index if c in r['notes'])}" for c in NOTE_CODES)
    )
    kept = keep_source_xml(index)
    if kept:
        print(f"  kept source XML for the top {kept} rows -> {XML_KEEP.relative_to(ROOT)}")
    if args.inject_chart:
        try:
            charted = write_chart(index)
        except ChartMarkerError as e:
            raise SystemExit(f"--inject-chart failed, no page was changed: {e}") from e
        print(f"  chart -> {', '.join(str(p.relative_to(ROOT)) for p in charted)}")
    else:
        print("  chart -> not injected (pass --inject-chart to rewrite the site pages)")
    print("\nTop 25:")
    for i, r in enumerate(index[:25], 1):
        pct = pct_text(r["gap_pct"] or None)
        print(
            f"{i:2d}. {r['name'][:34]:34s} {r['state'] or '':2s} 7a(c) {usd(r['irs_7a_gross']):>8s} (d) {usd(r['irs_7a_offset']):>8s} (e) {usd(r['irs_7a']):>8s}  S10 {usd(r['cms_s10']):>8s}  L5 {usd(r['cms_s10_line5']):>8s}  gap {('+' if r['gap'] > 0 else '') + usd(r['gap']):>9s} ({pct})"
        )


if __name__ == "__main__":
    main()
