"""Generate the og:image and twitter:image for troveproject.com.

Produces a 1200x630 PNG showing the project's headline numbers in a
monospace dark-mode card matching the site aesthetic.

Uses statistics computed from the published gap dataset, so the numbers
in the image stay in sync with what the site displays.

Usage: ``uv run --with pillow python scripts/build_og_image.py``
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

JSON_IN = Path("web/data/community_benefit_gap_2022.json")
PNG_OUT = Path("web/og.png")

WIDTH, HEIGHT = 1200, 630
BG = (14, 14, 14)
FG = (240, 240, 240)
MUTED = (170, 170, 170)
ACCENT = (240, 162, 107)  # warm orange — matches --pos in dark mode

MENLO_REGULAR = "/System/Library/Fonts/Menlo.ttc"
SFMONO = "/System/Library/Fonts/SFNSMono.ttf"


def main() -> None:
    bundle = json.loads(JSON_IN.read_text())
    rows = bundle["rows"]

    # Compute the same headline stats the page does.
    aligned_comparable = [
        r for r in rows
        if r.get("hcris_charity") and r.get("fa_990")
        and abs(r["hcris_charity"]) >= 500_000
        and abs(r["fa_990"]) >= 500_000
        and _months_between(r.get("hcris_fy_end"), r.get("period_end")) <= 1
    ]
    n = len(aligned_comparable)
    pcts = sorted(abs(r["gap_pct"]) for r in aligned_comparable)
    median_pct = pcts[len(pcts) // 2] if pcts else 0
    big = sum(1 for p in pcts if p >= 0.5)

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    title_font = _font(MENLO_REGULAR, 92, idx=1)  # bold variant in TTC
    body_font = _font(SFMONO, 28)
    stat_num_font = _font(MENLO_REGULAR, 80, idx=1)
    stat_label_font = _font(SFMONO, 22)
    footer_font = _font(SFMONO, 24)

    pad = 70

    draw.text((pad, pad - 10), "trove", font=title_font, fill=FG)

    body = (
        "A side-by-side comparison of what nonprofit U.S. hospitals\n"
        "report as charity care to two regulators (CMS vs. IRS) —\n"
        "for tax year 2022."
    )
    draw.text((pad, pad + 110), body, font=body_font, fill=MUTED, spacing=10)

    stats_y = pad + 290
    stats_x_starts = [pad, pad + 360, pad + 720]
    for x, num, label in zip(
        stats_x_starts,
        [str(n), f"{round(median_pct * 100)}%", str(big)],
        [
            "ALIGNED, COMPARABLE\nSYSTEMS",
            "MEDIAN GAP\nON THIS SUBSET",
            "DISAGREE BY\nMORE THAN HALF",
        ],
    ):
        draw.text((x, stats_y), num, font=stat_num_font, fill=ACCENT)
        draw.text((x, stats_y + 100), label, font=stat_label_font, fill=MUTED, spacing=8)

    draw.text((pad, HEIGHT - pad - 30), "troveproject.com", font=footer_font, fill=FG)
    repo_text = "github.com/cbetz/trove"
    repo_w = draw.textlength(repo_text, font=footer_font)
    draw.text(
        (WIDTH - pad - repo_w, HEIGHT - pad - 30),
        repo_text,
        font=footer_font,
        fill=MUTED,
    )

    PNG_OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(PNG_OUT, "PNG", optimize=True)
    print(f"  → {PNG_OUT} ({PNG_OUT.stat().st_size / 1024:.1f} KB)")
    print(f"  stats: {n} systems, {round(median_pct * 100)}% median, {big} big gaps")


def _font(path: str, size: int, idx: int = 0) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size, index=idx)
    except (OSError, IndexError):
        return ImageFont.load_default()


def _months_between(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 999
    from datetime import date
    da = date(*[int(x) for x in a.split("-")])
    db = date(*[int(x) for x in b.split("-")])
    return abs((da - db).days) / 30.44


if __name__ == "__main__":
    main()
