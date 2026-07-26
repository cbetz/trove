"""Generate the og:image and twitter:image for troveproject.com.

Produces a 1200x630 JPEG card in the monospace dark style matching the site.
Numbers are read from the published bundles so the card stays in sync.

The card states the finding in the **aggregate** and names no hospital. That is
deliberate: a JPEG can't carry the definitional caveats that make a per-hospital
comparison fair, and once a scraper has cached it, it can't be corrected. The
named example lives in ``og:description`` and on the page, where the caveats and
links to both source filings travel with it.

``FILENAME`` is cache-busted — X and Slack cache aggressively by URL, so a
changed card needs a changed path. Bump it, then run this script: it rewrites the
references across ``web/`` for you.

Usage: ``uv run python scripts/build_og_image.py``
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INDEX_JSON = Path("web/data/charity_care_gap_index_2022.json")
HOSPITALS_JSON = Path("web/data/community_benefit_gap_2022.json")
FDA_JSON = Path("web/data/fda_approvals_nme_recent.json")
WEB_DIR = Path("web")
FILENAME = "og-20260725.jpg"
JPG_OUT = WEB_DIR / FILENAME

WIDTH, HEIGHT = 1200, 630  # 1.91:1 — the OG / X-card standard
BG = (14, 14, 14)
FG = (240, 240, 240)
MUTED = (170, 170, 170)
ACCENT = (240, 162, 107)  # warm orange — matches --pos in dark mode
DIVIDER = (60, 60, 60)

MENLO_REGULAR = "/System/Library/Fonts/Menlo.ttc"
SFMONO = "/System/Library/Fonts/SFNSMono.ttf"

PAD = 70
HEADLINE = ["Hospitals report charity", "care to CMS and the IRS."]
KICKER = "The numbers don't match."


def main() -> None:
    index = json.loads(INDEX_JSON.read_text())
    hospitals = json.loads(HOSPITALS_JSON.read_text())
    fda = json.loads(FDA_JSON.read_text())

    clean = index["counts"]["clean_aligned"]
    big = index["counts"]["clean_aligned_over_50pct"]
    computable = hospitals["totals"]["computable"]
    fda_count = fda["totals"]["drugs"]
    fda_year_min, fda_year_max = fda["totals"]["year_min"], fda["totals"]["year_max"]

    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    brand_font = _font(MENLO_REGULAR, 30, idx=1)
    headline_font = _fit(draw, MENLO_REGULAR, HEADLINE + [KICKER], WIDTH - 2 * PAD, start=68, idx=1)
    sub_font = _font(SFMONO, 26)
    footer_font = _font(SFMONO, 22)

    draw.text((PAD, PAD - 14), "trove", font=brand_font, fill=MUTED)

    y = PAD + 46
    line_h = headline_font.size + 14
    for line in HEADLINE:
        draw.text((PAD, y), line, font=headline_font, fill=FG)
        y += line_h
    draw.text((PAD, y), KICKER, font=headline_font, fill=ACCENT)
    y += line_h + 22

    draw.text(
        (PAD, y),
        f"{clean} hospitals where the two filings are cleanly comparable.",
        font=sub_font,
        fill=MUTED,
    )
    draw.text(
        (PAD, y + 36),
        f"{big} of them differ by more than 50%.",
        font=sub_font,
        fill=MUTED,
    )

    footer_y = HEIGHT - PAD - 46
    draw.line([(PAD, footer_y - 20), (WIDTH - PAD, footer_y - 20)], fill=DIVIDER, width=1)
    site = "troveproject.com"
    footer_lines = [
        "CMS Worksheet S-10 x IRS 990 Schedule H, TY2022",
        f"{computable:,} systems - also {fda_count} FDA approvals, {fda_year_min}-{fda_year_max}",
    ]
    # The right-aligned domain and the left footer lines share one band, so fit
    # the font to the *combined* width or they collide as the counts grow.
    gutter = 40
    footer_font = _fit(
        draw,
        SFMONO,
        [f"{line}{' ' * 3}{site}" for line in footer_lines],
        WIDTH - 2 * PAD - gutter,
        start=22,
    )
    for i, line in enumerate(footer_lines):
        draw.text((PAD, footer_y + i * 28), line, font=footer_font, fill=MUTED)
    draw.text(
        (WIDTH - PAD - draw.textlength(site, font=footer_font), footer_y + 14),
        site,
        font=footer_font,
        fill=FG,
    )

    JPG_OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(JPG_OUT, "JPEG", quality=92, optimize=True)
    print(f"  → {JPG_OUT} ({JPG_OUT.stat().st_size / 1024:.1f} KB)")
    print(f"  stats: {clean} clean / {big} over 50% / {computable:,} systems / {fda_count} drugs")
    _retarget_pages()


def _retarget_pages() -> None:
    """Point every page's og:image / twitter:image at FILENAME.

    The card is cache-busted by path, so the filename changes and every
    reference has to follow. Missing one means a stale card on that page.
    """
    pattern = re.compile(r"og-\d{8}[a-z]?\.jpg")
    changed = []
    for page in sorted(WEB_DIR.rglob("*.html")):
        text = page.read_text()
        updated = pattern.sub(FILENAME, text)
        if updated != text:
            page.write_text(updated)
            changed.append(str(page.relative_to(WEB_DIR)))
    print(f"  → repointed og:image on {len(changed)} page(s)")


def _fit(
    draw: ImageDraw.ImageDraw,
    path: str,
    lines: list[str],
    max_width: int,
    *,
    start: int,
    idx: int = 0,
) -> ImageFont.FreeTypeFont:
    """Largest font size at which every line fits inside max_width."""
    size = start
    while size > 12:
        font = _font(path, size, idx=idx)
        if all(draw.textlength(line, font=font) <= max_width for line in lines):
            return font
        size -= 2
    return _font(path, 12, idx=idx)


def _font(path: str, size: int, idx: int = 0) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size, index=idx)
    except (OSError, IndexError):
        return ImageFont.load_default()


if __name__ == "__main__":
    main()
