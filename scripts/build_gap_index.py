"""Build the Charity Care Gap Index — the credibility-hardened leaderboard.

The full gap dataset (build_gap_dataset.py) is a per-hospital lookup table. A naive
"biggest gap" ranking over it is misleading: the largest raw gaps are dominated by
multi-facility systems reported under one EIN (misleading single-facility names) and
by rows whose two filings cover different fiscal years or different-scale entities.

This script derives the subset where a cross-form difference is genuinely
apples-to-apples, so it can be published as a ranked list without being debunked on
first expert contact:

  1. ccn_count == 1          single reporting facility — the name is trustworthy and
                             there is no system-level aggregation smoothing/inflating
                             the difference
  2. period-aligned         HCRIS fiscal-year end within 1 month of the 990 tax-period
                             end — the two filings cover the same fiscal year
  3. both numbers material   HCRIS S-10 charity care cost AND Schedule H 7a >= $1M
  4. expense bases agree      max/min of the two total-expense figures <= 1.05 — confirms
                             the two forms describe the same-scale entity for the same
                             period (catches stub periods, partial filings, mismatches)

Output:
  artifacts/charity_care_gap_index_2022.md          committed, GitHub-viewable table
  web/data/charity_care_gap_index_2022.json         ranked rows + filter metadata for the site
"""

import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "artifacts" / "community_benefit_gap_2022.csv"
MD_OUT = ROOT / "artifacts" / "charity_care_gap_index_2022.md"
JSON_OUT = ROOT / "web" / "data" / "charity_care_gap_index_2022.json"

MATERIAL_FLOOR = 1_000_000
EXPENSE_BASE_TOLERANCE = 1.05
ALIGNMENT_MONTHS = 1


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


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
            }
        )
    out.sort(key=lambda x: -abs(x["gap"]))
    return out


def usd(v):
    a = abs(v)
    sign = "−" if v < 0 else ""
    if a >= 1e9:
        return f"{sign}${a / 1e9:.1f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:.1f}M"
    if a >= 1e3:
        return f"{sign}${a / 1e3:.0f}K"
    return f"{sign}${a:.0f}"


def write_markdown(index):
    n = len(index)
    big = sum(1 for r in index if r["gap_pct"] and r["gap_pct"] > 0.5)
    lines = []
    lines.append("# The Charity Care Gap Index — TY2022")
    lines.append("")
    lines.append(
        "Every nonprofit U.S. hospital reports the cost of the free/discounted care it "
        "gave patients who couldn't pay to **two** federal regulators: to CMS on "
        "Worksheet S-10 of the Medicare Cost Report, and to the IRS on Schedule H "
        "(Part I, line 7a) of Form 990. The two numbers describe the same underlying "
        "activity. They are frequently far apart."
    )
    lines.append("")
    lines.append(
        "This is the **credibility-hardened** ranking derived from the full "
        "[gap dataset](community_benefit_gap_2022.csv) — the subset where the "
        "comparison is genuinely apples-to-apples, so the numbers survive scrutiny. "
        "Each hospital below is:"
    )
    lines.append("")
    lines.append(
        "- a **single reporting facility** (one CCN under one EIN — no multi-hospital roll-up hiding behind one name);"
    )
    lines.append(
        f"- **period-aligned** (the two filings' fiscal periods end within {ALIGNMENT_MONTHS} month of each other — they cover the same year);"
    )
    lines.append("- **material** (both the CMS and IRS charity-care figures are at least $1M); and")
    lines.append(
        f"- reporting **the same-scale entity** (the two forms' total expenses agree within {int((EXPENSE_BASE_TOLERANCE - 1) * 100)}%)."
    )
    lines.append("")
    lines.append(
        "**The comparison is net-to-net.** The IRS figure is Schedule H Part I line 7a "
        "column (e) — *net* community benefit expense for financial assistance (financial "
        "assistance at cost, less direct offsetting revenue). The CMS figure is Worksheet "
        "S-10 cost of charity care, net of partial patient payments. Comparing net to net "
        "pre-empts the obvious objection that a gross figure was set against a net one. The "
        "two \"net\" definitions still aren't identical — Schedule H's offsetting revenue can "
        "include items S-10 doesn't subtract — so a residual difference is expected even for "
        "a perfectly-reporting hospital. **% is the difference as a share of the larger of "
        "the two figures.**"
    )
    lines.append("")
    lines.append(
        f"**{n} hospitals** clear that bar. Of them, **{big}** report charity-care "
        "numbers to the two regulators that differ by more than 50%."
    )
    lines.append("")
    lines.append(
        "> A gap is **not** an accusation. The two forms have genuinely different "
        "definitions, cost-to-charge handling, and category boundaries, and a "
        "difference can be entirely legitimate. What this index does is make a "
        "long-known measurement inconsistency *checkable per hospital*, with a link "
        "to both source filings so you can see for yourself."
    )
    lines.append("")
    lines.append(
        "| # | Hospital | Told the IRS (990 Sch. H) | Told CMS (S-10) | Difference | % | 990 on ProPublica |"
    )
    lines.append(
        "|--:|----------|--------------------------:|----------------:|-----------:|--:|-------------------|"
    )
    for i, r in enumerate(index, 1):
        pp = f"https://projects.propublica.org/nonprofits/organizations/{int(r['ein'])}"
        pct = f"{round(r['gap_pct'] * 100)}%" if r["gap_pct"] is not None else "—"
        lines.append(
            f"| {i} | {r['name']} | {usd(r['irs_7a'])} | {usd(r['cms_s10'])} | "
            f"{'+' if r['gap'] > 0 else ''}{usd(r['gap'])} | {pct} | [990 ↗]({pp}) |"
        )
    lines.append("")
    lines.append(
        "**Reading the sign:** a positive difference means the hospital reported *more* charity-care cost to CMS than to the IRS; negative means it reported more to the IRS than to CMS."
    )
    lines.append("")
    lines.append("## Why the numbers legitimately differ")
    lines.append("")
    lines.append(
        '- **Definitions.** The two forms bound "financial assistance" / "charity care" differently — for example, how uninsured discounts are classified.'
    )
    lines.append(
        "- **Cost-to-charge ratios.** S-10 applies a hospital-wide CCR; Schedule H permits different cost-step-down methods."
    )
    lines.append(
        "- **Category boundaries.** The same patient case can be booked as charity care, bad debt, or contractual allowance — moving cost between lines."
    )
    lines.append(
        "- **S-10 data quality.** The reliability and completeness of Worksheet S-10 charity-care reporting has been repeatedly flagged (e.g., by MedPAC), so either figure — often the S-10 side — can simply be mis- or under-reported. That's a leading reason to read the source filings rather than treat a gap as settled."
    )
    lines.append(
        "- **System-wide methodology.** Hospitals under the same parent tend to share a financial-assistance policy and a common Schedule H costing method, which can push all of a system's hospitals the same direction — a methodological signature, not a statement about any one hospital."
    )
    lines.append("")
    lines.append(
        "This is a well-documented reporting inconsistency, not a novel discovery: the "
        "Government Accountability Office has noted there is no standard definition of "
        "uncompensated care across federal programs (GAO-16-568) and has separately "
        "scrutinized Schedule H reporting (GAO-20-679); the Congressional Research Service "
        "laid out the differing Medicare and IRS charity-care definitions (2018); CMS itself "
        "benchmarked S-10 against Form 990 data (2016); and health-services researchers have "
        "compared the two sources (e.g., Zare et al., *Health Services Research*, 2022)."
    )
    lines.append("")
    lines.append("## Method & reproduction")
    lines.append("")
    lines.append(
        "Generated by [`scripts/build_gap_index.py`](../scripts/build_gap_index.py) "
        "from [`community_benefit_gap_2022.csv`](community_benefit_gap_2022.csv). "
        "The full dataset (1,295 computable systems) and its caveats are documented in "
        "[`community_benefit_gap_2022_summary.md`](community_benefit_gap_2022_summary.md). "
        "HCRIS FY2023 × IRS 990 Schedule H TY2022. US-government-work source data, public domain."
    )
    lines.append("")
    lines.append("```bash")
    lines.append("uv run python scripts/build_gap_dataset.py   # builds the full gap CSV")
    lines.append("uv run python scripts/build_gap_index.py     # builds this index")
    lines.append("```")
    lines.append("")
    MD_OUT.write_text("\n".join(lines))


def write_json(index):
    payload = {
        "tax_year": 2022,
        "filter": {
            "ccn_count": 1,
            "alignment_months_max": ALIGNMENT_MONTHS,
            "material_floor_usd": MATERIAL_FLOOR,
            "expense_base_tolerance": EXPENSE_BASE_TOLERANCE,
            "description": "Single-facility, period-aligned, material (>=$1M both sides), same-scale (expense bases within 5%).",
        },
        "counts": {
            "clean_aligned": len(index),
            "clean_aligned_over_50pct": sum(
                1 for r in index if r["gap_pct"] and r["gap_pct"] > 0.5
            ),
        },
        "rows": index,
    }
    JSON_OUT.write_text(json.dumps(payload, separators=(",", ":")))


def main():
    rows = load_rows()
    index = clean_index(rows)
    write_markdown(index)
    write_json(index)
    print(
        f"{len(index)} clean+aligned hospitals -> {MD_OUT.relative_to(ROOT)} and {JSON_OUT.relative_to(ROOT)}"
    )
    print("\nTop 15:")
    for i, r in enumerate(index[:15], 1):
        pct = f"{round(r['gap_pct'] * 100)}%" if r["gap_pct"] else "—"
        print(
            f"{i:2d}. {r['name'][:36]:36s} IRS {usd(r['irs_7a']):>8s}  CMS {usd(r['cms_s10']):>8s}  gap {('+' if r['gap'] > 0 else '') + usd(r['gap']):>9s} ({pct})  base~{usd(r['expense_base'])}"
        )


if __name__ == "__main__":
    main()
