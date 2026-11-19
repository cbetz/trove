"""Generate the og:image and twitter:image for troveproject.com.

Produces a 1200x630 JPEG card in the monospace dark style matching the site, and
optionally a 1280x640 variant for the GitHub repository social preview.
Every number on the card is read from the published bundles, so the card cannot
drift from the data.

The card describes what the site shows and names no hospital. That is
deliberate: a JPEG can't carry the definitional caveats that make a per-hospital
comparison fair, and once a scraper has cached it, it can't be corrected. The
wording is descriptive ("side by side", "the components behind each difference")
and makes no claim about why the figures differ, or about how many do.

``FILENAME`` is cache-busted — X and Slack cache aggressively by URL, so a
changed card needs a changed path. Bump it and run this script. The pages'
``og:image`` / ``twitter:image`` tags are only rewritten with ``--retarget-pages``;
without the flag no HTML is touched.

Usage::

    uv run python scripts/build_og_image.py
    uv run python scripts/build_og_image.py --social-out /path/to/social-1280x640.jpg
    uv run python scripts/build_og_image.py --retarget-pages
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INDEX_JSON = Path("web/data/charity_care_gap_index_2022.json")
FDA_JSON = Path("web/data/fda_approvals_nme_recent.json")
WEB_DIR = Path("web")
FILENAME = "og-20261119.jpg"
JPG_OUT = WEB_DIR / FILENAME

OG_SIZE = (1200, 630)  # 1.91:1 — the OG / X-card standard
SOCIAL_SIZE = (1280, 640)  # GitHub repository social preview
BG = (14, 14, 14)
FG = (240, 240, 240)
MUTED = (170, 170, 170)
ACCENT = (240, 162, 107)  # warm orange — matches --pos in dark mode
DIVIDER = (60, 60, 60)

MENLO_REGULAR = "/System/Library/Fonts/Menlo.ttc"
SFMONO = "/System/Library/Fonts/SFNSMono.ttf"

PAD = 70
# Line 1 is the white row; line 2 is the accent text beneath it, set on two rows
# so the type stays large enough to read in a link preview; line 3 is the
# smaller row under both, also set on two rows.
LINE_1 = "Hospital charity care:"
LINE_2 = ["the IRS figure and the CMS figure,", "side by side"]
LINE_3 = [
    "{clean} hospitals \u00b7 tax year {tax_year} \u00b7",
    "with the components behind each difference",
]


def card_text(index: dict) -> dict[str, object]:
    """The card's three lines, with counts taken from the index JSON."""
    counts = index["counts"]
    return {
        "line_1": LINE_1,
        "line_2": " ".join(LINE_2),
        "line_3": " ".join(LINE_3).format(
            clean=f"{counts['clean_aligned']:,}",
            tax_year=index["tax_year"],
        ),
    }


def render(index: dict, fda: dict, size: tuple[int, int]) -> Image.Image:
    width, height = size
    fda_count = fda["totals"]["drugs"]
    fda_year_min, fda_year_max = fda["totals"]["year_min"], fda["totals"]["year_max"]

    img = Image.new("RGB", size, BG)
    draw = ImageDraw.Draw(img)

    brand_font = _font(MENLO_REGULAR, 30, idx=1)
    fmt = {"clean": f"{index['counts']['clean_aligned']:,}", "tax_year": index["tax_year"]}
    sub_rows = [row.format(**fmt) for row in LINE_3]
    headline_font = _fit(draw, MENLO_REGULAR, [LINE_1, *LINE_2], width - 2 * PAD, start=56, idx=1)
    sub_font = _fit(draw, SFMONO, sub_rows, width - 2 * PAD, start=30)

    draw.text((PAD, PAD - 14), "trove", font=brand_font, fill=MUTED)

    y = PAD + 52
    line_h = headline_font.size + 16
    draw.text((PAD, y), LINE_1, font=headline_font, fill=FG)
    y += line_h
    for row in LINE_2:
        draw.text((PAD, y), row, font=headline_font, fill=ACCENT)
        y += line_h
    y += 22

    for row in sub_rows:
        draw.text((PAD, y), row, font=sub_font, fill=FG)
        y += sub_font.size + 12

    footer_y = height - PAD - 46
    draw.line([(PAD, footer_y - 20), (width - PAD, footer_y - 20)], fill=DIVIDER, width=1)
    site = "troveproject.com"
    footer_lines = [
        "Sources: IRS Form 990 Schedule H and CMS Worksheet S-10",
        f"Also on the site: {fda_count} FDA drug approvals, {fda_year_min}-{fda_year_max}",
    ]
    # The right-aligned domain and the left footer lines share one band, so fit
    # the font to the *combined* width or they collide as the counts grow.
    gutter = 40
    footer_font = _fit(
        draw,
        SFMONO,
        [f"{line}{' ' * 3}{site}" for line in footer_lines],
        width - 2 * PAD - gutter,
        start=22,
    )
    for i, line in enumerate(footer_lines):
        draw.text((PAD, footer_y + i * 28), line, font=footer_font, fill=MUTED)
    draw.text(
        (width - PAD - draw.textlength(site, font=footer_font), footer_y + 14),
        site,
        font=footer_font,
        fill=FG,
    )
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--social-out",
        type=Path,
        help="also write a 1280x640 GitHub social-preview JPEG to this path",
    )
    ap.add_argument(
        "--retarget-pages",
        action="store_true",
        help="rewrite og:image / twitter:image in web/**/*.html to point at FILENAME",
    )
    args = ap.parse_args()

    index = json.loads(INDEX_JSON.read_text())
    fda = json.loads(FDA_JSON.read_text())

    outputs = [(JPG_OUT, OG_SIZE)]
    if args.social_out:
        outputs.append((args.social_out, SOCIAL_SIZE))
    for path, size in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        render(index, fda, size).save(path, "JPEG", quality=92, optimize=True)
        print(f"  → {path} ({size[0]}x{size[1]}, {path.stat().st_size / 1024:.1f} KB)")
    for line in card_text(index).values():
        print(f"  text: {line}")
    if args.retarget_pages:
        _retarget_pages()
    else:
        print(f"  pages not retargeted (pass --retarget-pages); the new file is {FILENAME}")


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
