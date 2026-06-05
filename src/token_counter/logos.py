"""Provider logos for the cards and compact view.

Honest note on trademarks: the official ChatGPT / Claude / Gemini logos are
trademarked, so this ships *brand-style glyph approximations* drawn in code
(OpenAI knot-ish ring, Claude sunburst, Gemini sparkle) rather than the real
asset files. If you have the rights to the real logos, drop a PNG at
``~/.token_counter/logos/<provider>.png`` (or ``<key>.png`` where key is
openai/claude/gemini) and it will be used automatically.
"""

from __future__ import annotations

import math
from pathlib import Path

LOGO_DIR = Path("~/.token_counter/logos").expanduser()

_BRAND = {
    "openai": (16, 163, 127),
    "claude": (217, 119, 87),
    "gemini": (66, 133, 244),
}


def provider_key(name: str, scheme: str | None = None) -> str:
    text = f"{name} {scheme or ''}".lower()
    if any(k in text for k in ("openai", "chatgpt", "gpt")):
        return "openai"
    if any(k in text for k in ("claude", "anthropic")):
        return "claude"
    if any(k in text for k in ("gemini", "google")):
        return "gemini"
    return "generic"


def _user_png(name: str, key: str) -> Path | None:
    for candidate in (LOGO_DIR / f"{name}.png", LOGO_DIR / f"{key}.png"):
        if candidate.exists():
            return candidate
    return None


def _sparkle(draw, cx, cy, r, color):
    """Gemini-style 4-point star."""
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i
        rad = r if i % 2 == 0 else r * 0.32
        pts.append((cx + rad * math.cos(ang - math.pi / 2),
                    cy + rad * math.sin(ang - math.pi / 2)))
    draw.polygon(pts, fill=color)


def _sunburst(draw, cx, cy, r, color):
    """Claude-style radial burst."""
    for i in range(12):
        ang = math.pi / 6 * i
        x1, y1 = cx + r * 0.30 * math.cos(ang), cy + r * 0.30 * math.sin(ang)
        x2, y2 = cx + r * math.cos(ang), cy + r * math.sin(ang)
        draw.line((x1, y1, x2, y2), fill=color, width=max(1, int(r * 0.16)))
    draw.ellipse((cx - r * 0.22, cy - r * 0.22, cx + r * 0.22, cy + r * 0.22), fill=color)


def _ring(draw, cx, cy, r, color):
    """OpenAI-style ring/knot."""
    w = max(1, int(r * 0.28))
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
    draw.ellipse((cx - r * 0.12, cy - r * 0.12, cx + r * 0.12, cy + r * 0.12), fill=color)


def _letter_badge(draw, size, color, letter):
    from PIL import ImageFont

    draw.ellipse((1, 1, size - 1, size - 1), fill=color)
    try:
        font = ImageFont.load_default()
    except Exception:  # pragma: no cover
        font = None
    draw.text((size / 2, size / 2), letter, fill=(255, 255, 255), anchor="mm", font=font)


def provider_logo_image(name: str, size: int = 28, scheme: str | None = None):
    """Return a PIL RGBA image for the provider (real PNG if present, else glyph)."""
    from PIL import Image, ImageDraw

    key = provider_key(name, scheme)
    png = _user_png(name, key)
    if png is not None:
        return Image.open(png).convert("RGBA").resize((size, size), Image.LANCZOS)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = _BRAND.get(key, (120, 130, 150))
    cx = cy = size / 2
    r = size * 0.42
    if key == "gemini":
        _sparkle(draw, cx, cy, r, color)
    elif key == "claude":
        _sunburst(draw, cx, cy, r, color)
    elif key == "openai":
        _ring(draw, cx, cy, r, color)
    else:
        _letter_badge(draw, size, color, (name[:1] or "?").upper())
    return img
