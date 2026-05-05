"""Generate the og:image and twitter:image for troveproject.com.

Produces a 1200x630 JPEG card representing the multi-area trove project
in a monospace dark-mode style matching the site. Numbers are pulled
from the live data bundles so the card stays in sync with what each
area surfaces.

Usage: ``uv run python scripts/build_og_image.py``
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FDA_JSON = Path("web/data/fda_approvals_nme_recent.json")
HOSPITALS_JSON = Path("web/data/community_benefit_gap_2022.json")
JPG_OUT = Path("web/og.jpg")

WIDTH, HEIGHT = 1200, 630  # 1.91:1 — the OG / X-card standard
BG = (14, 14, 14)
FG = (240, 240, 240)
MUTED = (170, 170, 170)
ACCENT = (240, 162, 107)  # warm orange — matches --pos in dark mode
DIVIDER = (60, 60, 60)

MENLO_REGULAR = "/System/Library/Fonts/Menlo.ttc"
SFMONO = "/System/Library/Fonts/SFNSMono.ttf"


def main() -> None:
    fda = json.loads(FDA_JSON.read_text())
    hospitals = json.loads(HOSPITALS_JSON.read_text())
    fda_count = fda["totals"]["drugs"]
    fda_year_min = fda["totals"]["year_min"]
    fda_year_max = fda["totals"]["year_max"]
    hospitals_count = hospitals["totals"]["computable"]

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    title_font = _font(MENLO_REGULAR, 92, idx=1)
    tagline_font = _font(SFMONO, 30)
    area_label_font = _font(SFMONO, 22)
    area_title_font = _font(MENLO_REGULAR, 36, idx=1)
    area_sub_font = _font(SFMONO, 22)
    footer_font = _font(SFMONO, 24)

    pad = 70

    # Title + tagline
    draw.text((pad, pad - 10), "trove", font=title_font, fill=FG)
    draw.text(
        (pad, pad + 110),
        "Reference tools for underused public healthcare data.",
        font=tagline_font,
        fill=MUTED,
    )

    # Two area blocks, stacked
    area_y = pad + 200
    block_h = 120

    # Area 1 — FDA drug approvals
    _draw_area(
        draw,
        x=pad,
        y=area_y,
        tag="AREA 1 · NEW",
        title="FDA novel drug approvals",
        sub=f"{fda_count} drugs, {fda_year_min}–{fda_year_max} · find the approval package",
        tag_font=area_label_font,
        title_font=area_title_font,
        sub_font=area_sub_font,
    )
    # Divider line
    draw.line(
        [(pad, area_y + block_h - 6), (WIDTH - pad, area_y + block_h - 6)],
        fill=DIVIDER,
        width=1,
    )

    # Area 2 — Hospital reporting
    _draw_area(
        draw,
        x=pad,
        y=area_y + block_h,
        tag="AREA 2",
        title="Hospital reporting",
        sub=f"{hospitals_count:,} systems, TY2022 · CMS Cost Reports + IRS 990 Schedule H",
        tag_font=area_label_font,
        title_font=area_title_font,
        sub_font=area_sub_font,
    )

    # Footer
    draw.text((pad, HEIGHT - pad - 30), "troveproject.com", font=footer_font, fill=FG)
    repo_text = "github.com/cbetz/trove"
    repo_w = draw.textlength(repo_text, font=footer_font)
    draw.text(
        (WIDTH - pad - repo_w, HEIGHT - pad - 30),
        repo_text,
        font=footer_font,
        fill=MUTED,
    )

    JPG_OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(JPG_OUT, "JPEG", quality=92, optimize=True)
    print(f"  → {JPG_OUT} ({JPG_OUT.stat().st_size / 1024:.1f} KB)")
    print(f"  stats: {fda_count} drugs ({fda_year_min}–{fda_year_max}), {hospitals_count:,} hospitals (TY2022)")


def _draw_area(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    tag: str,
    title: str,
    sub: str,
    tag_font: ImageFont.FreeTypeFont,
    title_font: ImageFont.FreeTypeFont,
    sub_font: ImageFont.FreeTypeFont,
) -> None:
    draw.text((x, y), tag, font=tag_font, fill=ACCENT)
    draw.text((x, y + 30), title, font=title_font, fill=FG)
    draw.text((x, y + 80), sub, font=sub_font, fill=MUTED)


def _font(path: str, size: int, idx: int = 0) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size, index=idx)
    except (OSError, IndexError):
        return ImageFont.load_default()


if __name__ == "__main__":
    main()
