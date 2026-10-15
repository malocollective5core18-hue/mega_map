#!/usr/bin/env python3
"""Regenerate the public, non-personal Open Graph share image.

Install the pinned generator-only dependency with
`python -m pip install -r requirements-image.txt`, then run
`python scripts/make_og_image.py` from the repository root.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "core/static/og/share-1200x630-v1.png"
ICON = ROOT / "core/static/core/icons/icon-512.png"
WIDTH, HEIGHT = 1200, 630
GREEN = "#0f3d2e"
GREEN_LINE = "#164a39"
WHITE = "#ffffff"
AMBER = "#f2a900"


def load_font(size: int, *, bold: bool = False):
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), GREEN)
    draw = ImageDraw.Draw(image)

    # Low-contrast solid street lines give a restrained map cue without texture.
    draw.line([(760, 40), (850, 160), (790, 260), (920, 380), (870, 610)], fill=GREEN_LINE, width=3)
    draw.line([(1010, 0), (945, 130), (1035, 245), (970, 365), (1125, 530)], fill=GREEN_LINE, width=3)
    draw.line([(680, 555), (790, 480), (900, 510), (1005, 430), (1200, 445)], fill=GREEN_LINE, width=3)

    icon = Image.open(ICON).convert("RGBA").resize((258, 258), Image.Resampling.LANCZOS)
    image.paste(icon, (112, 185), icon)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((108, 181, 374, 447), radius=47, outline="#235c49", width=2)

    title_font = load_font(48, bold=True)
    sub_font = load_font(47, bold=True)
    tagline_font = load_font(32)
    draw.text((430, 213), "Mauzosheet, Hotbano", font=title_font, fill=WHITE)
    draw.text((430, 276), "& Services", font=sub_font, fill=AMBER)
    draw.rounded_rectangle((432, 361, 532, 368), radius=3, fill=AMBER)
    draw.text((430, 397), "Shiriki location ya biashara yako", font=tagline_font, fill=WHITE)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, format="PNG", optimize=True, compress_level=9)
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({image.width}x{image.height}, {OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
