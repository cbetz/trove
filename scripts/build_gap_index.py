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
import html
import json
import math
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "artifacts" / "community_benefit_gap_2022.csv"
MD_OUT = ROOT / "artifacts" / "charity_care_gap_index_2022.md"
JSON_OUT = ROOT / "web" / "data" / "charity_care_gap_index_2022.json"
CHART_TARGETS = (
    ROOT / "web" / "notes" / "charity-care-gap" / "index.html",
    ROOT / "web" / "hospitals" / "index.html",
)
CHART_START = "<!-- GAP_CHART:START -->"
CHART_END = "<!-- GAP_CHART:END -->"

MATERIAL_FLOOR = 1_000_000
EXPENSE_BASE_TOLERANCE = 1.05
ALIGNMENT_MONTHS = 1

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


def _usd_axis(v):
    """Axis tick label: $1M, $10M, $100M — no decimals, they're log decades."""
    if v >= 1e9:
        return f"${v / 1e9:.0f}B"
    if v >= 1e6:
        return f"${v / 1e6:.0f}M"
    return f"${v / 1e3:.0f}K"


def svg_chart(index):
    """A log-log scatter of the two reported figures, one dot per hospital.

    The form follows the data's job. Both axes carry the same unit (dollars of
    charity-care cost), so they share one scale and one range — that is what makes
    the 45-degree parity line meaningful: a hospital reporting the same number to
    both regulators lands exactly on it, and distance from the line IS the finding.
    Two axes of the same measure is the opposite of a dual-axis chart; forcing
    independent scales here would manufacture the very divergence being measured.

    Color encodes polarity (which regulator got the larger number), diverging from
    the parity line as a neutral midpoint. No hospital is direct-labeled: identity
    comes from hover and from the ranked table beside it, so an exported PNG can't
    become a named-and-shamed image detached from its caveats. Region labels
    explain the encoding without naming anyone.

    Log scale because the values span $1M to $113M; a linear axis would pack 80 of
    the 99 hospitals into the bottom-left corner.
    """
    pts = [r for r in index if r["irs_7a"] > 0 and r["cms_s10"] > 0]
    if not pts:
        return ""

    W, H = 720, 560
    M = {"t": 28, "r": 22, "b": 68, "l": 82}
    pw, ph = W - M["l"] - M["r"], H - M["t"] - M["b"]

    lo = min(min(p["irs_7a"], p["cms_s10"]) for p in pts) * 0.8
    hi = max(max(p["irs_7a"], p["cms_s10"]) for p in pts) * 1.25
    l10, h10 = math.log10(lo), math.log10(hi)

    def sx(v):
        return M["l"] + (math.log10(v) - l10) / (h10 - l10) * pw

    def sy(v):
        return M["t"] + ph - (math.log10(v) - l10) / (h10 - l10) * ph

    ticks = [t for t in (1e6, 2e6, 5e6, 1e7, 2e7, 5e7, 1e8) if lo <= t <= hi]

    o = []
    o.append(
        f'<svg class="gapchart" viewBox="0 0 {W} {H}" role="img" '
        f'aria-labelledby="gapchart-t gapchart-d" preserveAspectRatio="xMidYMid meet">'
    )
    o.append(
        '<title id="gapchart-t">Charity care reported to CMS versus to the IRS, '
        f"{len(pts)} hospitals, tax year 2022</title>"
    )
    o.append(
        '<desc id="gapchart-d">Log-log scatter. Each dot is one hospital. The '
        "diagonal marks where the two filings would be equal. Dots above it reported "
        "more to CMS; dots below reported more to the IRS. Distance from the diagonal "
        "is the size of the difference. The full figures are in the table below.</desc>"
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
            f'<text class="tick tick-x" x="{sx(t):.1f}" y="{M["t"] + ph + 20}">'
            f"{_usd_axis(t)}</text>"
        )
        o.append(
            f'<text class="tick tick-y" x="{M["l"] - 10}" y="{sy(t) + 4:.1f}">{_usd_axis(t)}</text>'
        )

    # Parity line — the neutral reference the whole chart is read against.
    o.append(
        f'<line class="parity" x1="{sx(lo):.1f}" y1="{sy(lo):.1f}" '
        f'x2="{sx(hi):.1f}" y2="{sy(hi):.1f}"/>'
    )
    # Legend, top-left, in the one corner the cloud leaves empty. Every key is a
    # swatch or a line-key beside muted text — identity never comes from coloring
    # the text, and never from color alone. The parity line is keyed here rather
    # than labeled inline: an inline label lands in the densest part of the cloud
    # and collides with the dots it's meant to explain.
    lx, ly = M["l"] + 14, M["t"] + 14
    o.append(
        f'<line class="parity" x1="{lx}" y1="{ly}" x2="{lx + 16}" y2="{ly}"/>'
        f'<text class="region" x="{lx + 24}" y="{ly + 4}">the diagonal: both filings equal</text>'
    )
    o.append(
        f'<circle class="swatch pos" cx="{lx + 8}" cy="{ly + 20}" r="4.5"/>'
        f'<text class="region" x="{lx + 24}" y="{ly + 24}">above it: reported more to CMS</text>'
    )
    o.append(
        f'<circle class="swatch neg" cx="{lx + 8}" cy="{ly + 40}" r="4.5"/>'
        f'<text class="region" x="{lx + 24}" y="{ly + 44}">below it: reported more to the IRS</text>'
    )

    # Dots last so they sit above the grid. Surface ring keeps overlaps legible.
    for p in pts:
        cls = "pos" if p["gap"] > 0 else "neg"
        pct = f"{round(p['gap_pct'] * 100)}%" if p["gap_pct"] is not None else "—"
        o.append(
            f'<circle class="dot {cls}" cx="{sx(p["irs_7a"]):.1f}" cy="{sy(p["cms_s10"]):.1f}" '
            f'r="4.5" data-n="{html.escape(p["name"], quote=True)}" '
            # usd(), not the axis formatter — the tooltip must match the $113.1M
            # precision used in the table and prose, not round to whole millions.
            f'data-irs="{usd(p["irs_7a"])}" data-cms="{usd(p["cms_s10"])}" '
            f'data-pct="{pct}" data-end="{p["period_end"]}"><title>{html.escape(p["name"])}: '
            f"IRS {usd(p['irs_7a'])}, CMS {usd(p['cms_s10'])}</title></circle>"
        )

    o.append(
        f'<text class="axis-title" x="{M["l"] + pw / 2:.0f}" y="{H - 18}">'
        "Reported to the IRS — Form 990 Schedule H, Part I line 7a (net)</text>"
    )
    o.append(
        f'<text class="axis-title" transform="translate(18,{M["t"] + ph / 2:.0f}) rotate(-90)" '
        'x="0" y="0">Reported to CMS — Worksheet S-10 (net)</text>'
    )
    o.append("</svg>")
    return "\n".join(o)


CHART_CSS = f"""
<style>
  .gapfig {{ margin: 2rem 0; }}
  .gapfig figcaption {{ color: var(--muted); font-size: 0.85rem; line-height: 1.5; margin-top: 0.6rem; }}
  .gapchart {{ width: 100%; height: auto; display: block; overflow: visible;
    --mark-pos: {MARK_POS_LIGHT}; --mark-neg: {MARK_NEG_LIGHT};
    --grid: rgba(127,127,127,0.22); --parity: rgba(127,127,127,0.55); }}
  @media (prefers-color-scheme: dark) {{
    .gapchart {{ --mark-pos: {MARK_POS_DARK}; --mark-neg: {MARK_NEG_DARK};
      --grid: rgba(255,255,255,0.13); --parity: rgba(255,255,255,0.4); }}
  }}
  .gapchart .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .gapchart .parity {{ stroke: var(--parity); stroke-width: 1.5; }}
  .gapchart .tick, .gapchart .axis-title, .gapchart .region {{
    fill: var(--muted); font-family: ui-monospace, Menlo, monospace; }}
  .gapchart .tick {{ font-size: 12px; }}
  .gapchart .tick-x {{ text-anchor: middle; }}
  .gapchart .tick-y {{ text-anchor: end; }}
  .gapchart .axis-title {{ font-size: 12.5px; text-anchor: middle; }}
  .gapchart .region {{ font-size: 12px; text-anchor: start; }}
  .gapchart .swatch {{ stroke: var(--bg); stroke-width: 1.5; }}
  .gapchart .swatch.pos {{ fill: var(--mark-pos); }}
  .gapchart .swatch.neg {{ fill: var(--mark-neg); }}
  .gapchart .dot {{ stroke: var(--bg); stroke-width: 2; cursor: pointer; }}
  .gapchart .dot.pos {{ fill: var(--mark-pos); }}
  .gapchart .dot.neg {{ fill: var(--mark-neg); }}
  .gapchart .dot:hover {{ r: 7; }}
  .gaptip {{ position: fixed; z-index: 20; pointer-events: none; opacity: 0;
    transition: opacity 0.1s; background: var(--bg); color: var(--fg);
    border: 1px solid var(--border); border-radius: 6px; padding: 0.5rem 0.7rem;
    font: 12px/1.5 ui-monospace, Menlo, monospace; max-width: 17rem;
    box-shadow: 0 2px 10px rgba(0,0,0,0.18); }}
  .gaptip b {{ display: block; margin-bottom: 0.2rem; }}
  .gaptip span {{ color: var(--muted); }}
</style>
"""

CHART_JS = """
<script>
(function () {
  var svg = document.querySelector('.gapchart');
  if (!svg) return;
  var tip = document.createElement('div');
  tip.className = 'gaptip';
  document.body.appendChild(tip);
  function show(e) {
    var d = e.target.dataset;
    tip.innerHTML = '<b>' + d.n + '</b>'
      + 'IRS 990 Sch. H 7a: ' + d.irs + '<br>'
      + 'CMS Worksheet S-10: ' + d.cms + '<br>'
      + '<span>differs by ' + d.pct + ' \\u00b7 period ended ' + d.end + '</span>';
    tip.style.opacity = '1';
    move(e);
  }
  function move(e) {
    var r = tip.getBoundingClientRect();
    var x = Math.min(e.clientX + 14, window.innerWidth - r.width - 8);
    var y = Math.max(e.clientY - r.height - 12, 8);
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }
  svg.querySelectorAll('.dot').forEach(function (dot) {
    dot.addEventListener('mouseenter', show);
    dot.addEventListener('mousemove', move);
    dot.addEventListener('mouseleave', function () { tip.style.opacity = '0'; });
  });
})();
</script>
"""


def write_chart(index):
    """Inject the generated figure between markers on each target page.

    Marker-delimited so the chart is regenerated, never hand-maintained — the same
    reason sitemap.xml lives in a build script.
    """
    n = len([r for r in index if r["irs_7a"] > 0 and r["cms_s10"] > 0])
    big = sum(1 for r in index if r["gap_pct"] and r["gap_pct"] > 0.5)
    fragment = (
        f'{CHART_START}\n{CHART_CSS}\n<figure class="gapfig">\n{svg_chart(index)}\n'
        f"<figcaption>Each dot is one of the {n} hospitals where the two filings are "
        f"cleanly comparable — single facility, periods ending within a month of each "
        f"other, both figures at least $1M, and total expenses within 5%. A hospital "
        f"reporting the same cost to both regulators sits on the diagonal; {big} sit "
        f"far enough off it that the two figures differ by more than half. Both axes "
        f"are log-scaled. Hover any dot for the hospital and its two figures. "
        f"Sources: CMS HCRIS Worksheet S-10 (FY2023) and IRS Form 990 Schedule H "
        f"(TY2022).</figcaption>\n</figure>\n{CHART_JS}\n{CHART_END}"
    )
    written = []
    for path in CHART_TARGETS:
        if not path.exists():
            continue
        text = path.read_text()
        if CHART_START not in text or CHART_END not in text:
            continue
        head, _, rest = text.partition(CHART_START)
        _, _, tail = rest.partition(CHART_END)
        path.write_text(head + fragment + tail)
        written.append(path.relative_to(ROOT))
    return written


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
    charted = write_chart(index)
    print(
        f"{len(index)} clean+aligned hospitals -> {MD_OUT.relative_to(ROOT)} and {JSON_OUT.relative_to(ROOT)}"
    )
    print(
        f"  chart -> {', '.join(str(p) for p in charted) if charted else 'NO TARGET HAD MARKERS'}"
    )
    print("\nTop 15:")
    for i, r in enumerate(index[:15], 1):
        pct = f"{round(r['gap_pct'] * 100)}%" if r["gap_pct"] else "—"
        print(
            f"{i:2d}. {r['name'][:36]:36s} IRS {usd(r['irs_7a']):>8s}  CMS {usd(r['cms_s10']):>8s}  gap {('+' if r['gap'] > 0 else '') + usd(r['gap']):>9s} ({pct})  base~{usd(r['expense_base'])}"
        )


if __name__ == "__main__":
    main()
