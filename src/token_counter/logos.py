"""Provider logos for the cards and compact view.

Honest note on trademarks: official provider logos are trademarked, so this ships
*brand-style glyph approximations* drawn in code (not the real asset files). Drop
a PNG at ``~/.token_counter/logos/<service>.png`` (e.g. ``grok.png``) to override
any of them with the real artwork you have rights to.
"""

from __future__ import annotations

import math
from pathlib import Path

LOGO_DIR = Path("~/.token_counter/logos").expanduser()


def _bundled_dir() -> Path | None:
    """Folder of bundled real-logo PNGs shipped with the package (if present)."""
    try:
        from importlib.resources import files

        return Path(str(files("token_counter") / "assets" / "logos"))
    except Exception:
        guess = Path(__file__).resolve().parent / "assets" / "logos"
        return guess if guess.exists() else None


def _bundled_png(key: str) -> Path | None:
    d = _bundled_dir()
    if d is None:
        return None
    candidate = d / f"{key}.png"
    return candidate if candidate.exists() else None

# Brand accent colour per service id.
_BRAND = {
    "openai": (16, 163, 127),
    "claude": (217, 119, 87),
    "gemini": (66, 133, 244),
    "grok": (236, 236, 237),       # near-white: xAI mark reads on the dark bg
    "deepseek": (77, 107, 254),
    "mistral": (255, 143, 0),
    "groq": (242, 78, 30),
    "perplexity": (32, 178, 170),
    "openrouter": (124, 92, 220),
    "together": (240, 90, 90),
    "fireworks": (255, 110, 60),
    "cohere": (216, 100, 120),
}


def provider_key(name: str, scheme: str | None = None) -> str:
    """Map a provider name/scheme to a catalog service id."""
    text = f"{name} {scheme or ''}".lower()
    pairs = [
        ("openai", ("openai", "chatgpt", "gpt")),
        ("claude", ("claude", "anthropic")),
        ("gemini", ("gemini", "google")),
        ("grok", ("grok", "xai")),
        ("deepseek", ("deepseek",)),
        ("mistral", ("mistral",)),
        ("groq", ("groq",)),
        ("perplexity", ("perplexity", "pplx")),
        ("openrouter", ("openrouter",)),
        ("together", ("together",)),
        ("fireworks", ("fireworks",)),
        ("cohere", ("cohere",)),
    ]
    for key, needles in pairs:
        if any(n in text for n in needles):
            return key
    return "generic"


def _user_png(name: str, key: str) -> Path | None:
    for candidate in (LOGO_DIR / f"{name}.png", LOGO_DIR / f"{key}.png"):
        if candidate.exists():
            return candidate
    return None


# --- glyph primitives ------------------------------------------------------
def _sparkle(draw, cx, cy, r, color):
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i
        rad = r if i % 2 == 0 else r * 0.32
        pts.append((cx + rad * math.cos(ang - math.pi / 2),
                    cy + rad * math.sin(ang - math.pi / 2)))
    draw.polygon(pts, fill=color)


def _sunburst(draw, cx, cy, r, color):
    for i in range(12):
        ang = math.pi / 6 * i
        x1, y1 = cx + r * 0.30 * math.cos(ang), cy + r * 0.30 * math.sin(ang)
        x2, y2 = cx + r * math.cos(ang), cy + r * math.sin(ang)
        draw.line((x1, y1, x2, y2), fill=color, width=max(1, int(r * 0.16)))
    draw.ellipse((cx - r * 0.22, cy - r * 0.22, cx + r * 0.22, cy + r * 0.22), fill=color)


def _ring(draw, cx, cy, r, color):
    w = max(1, int(r * 0.28))
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
    draw.ellipse((cx - r * 0.12, cy - r * 0.12, cx + r * 0.12, cy + r * 0.12), fill=color)


def _slash_x(draw, cx, cy, r, color):
    """Grok / xAI — angular crossed slashes."""
    w = max(2, int(r * 0.34))
    draw.line((cx - r, cy - r, cx + r, cy + r), fill=color, width=w)
    draw.line((cx + r, cy - r, cx - r, cy + r), fill=color, width=w)


def _whale(draw, cx, cy, r, color):
    """DeepSeek — a simple curved arc + dot motif."""
    w = max(2, int(r * 0.30))
    draw.arc((cx - r, cy - r, cx + r, cy + r), start=20, end=200, fill=color, width=w)
    draw.ellipse((cx + r * 0.25, cy - r * 0.1, cx + r * 0.55, cy + r * 0.2), fill=color)


def _bands(draw, cx, cy, r, base):
    """Mistral — horizontal colour bands (orange→yellow→red)."""
    cols = [(255, 209, 0), (255, 143, 0), (240, 90, 30), (200, 40, 40)]
    n = len(cols)
    top, h = cy - r, (2 * r) / n
    for i, col in enumerate(cols):
        y0 = top + i * h
        draw.rectangle((cx - r, y0, cx + r, y0 + h), fill=col)


def _q(draw, cx, cy, r, color):
    """Groq — a ring with a tail (Q)."""
    w = max(2, int(r * 0.26))
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=w)
    draw.line((cx + r * 0.2, cy + r * 0.2, cx + r * 0.9, cy + r * 0.9), fill=color, width=w)


def _seek(draw, cx, cy, r, color):
    """Perplexity — concentric/seek motif."""
    w = max(2, int(r * 0.20))
    draw.arc((cx - r, cy - r, cx + r, cy + r), 0, 360, fill=color, width=w)
    draw.line((cx, cy - r, cx, cy + r), fill=color, width=w)
    draw.line((cx - r, cy, cx + r, cy), fill=color, width=w)


def _knot(draw, cx, cy, r, color):
    """OpenRouter — two interlocking rings."""
    w = max(2, int(r * 0.24))
    draw.ellipse((cx - r, cy - r * 0.5, cx, cy + r * 0.5), outline=color, width=w)
    draw.ellipse((cx, cy - r * 0.5, cx + r, cy + r * 0.5), outline=color, width=w)


def _burst(draw, cx, cy, r, color):
    """Fireworks — radiating lines."""
    for i in range(8):
        ang = math.pi / 4 * i
        draw.line((cx, cy, cx + r * math.cos(ang), cy + r * math.sin(ang)),
                  fill=color, width=max(1, int(r * 0.14)))
    draw.ellipse((cx - r * 0.16, cy - r * 0.16, cx + r * 0.16, cy + r * 0.16), fill=color)


def _disc(draw, cx, cy, r, color):
    """Together / Cohere — filled disc with a lighter inner ring."""
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    light = tuple(min(255, c + 70) for c in color)
    w = max(2, int(r * 0.18))
    draw.ellipse((cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55),
                 outline=light, width=w)


def _letter_badge(draw, size, color, letter):
    from PIL import ImageFont

    draw.ellipse((1, 1, size - 1, size - 1), fill=color)
    try:
        font = ImageFont.load_default()
    except Exception:  # pragma: no cover
        font = None
    draw.text((size / 2, size / 2), letter, fill=(255, 255, 255), anchor="mm", font=font)


_DRAWERS = {
    "gemini": _sparkle,
    "claude": _sunburst,
    "openai": _ring,
    "grok": _slash_x,
    "deepseek": _whale,
    "mistral": _bands,
    "groq": _q,
    "perplexity": _seek,
    "openrouter": _knot,
    "fireworks": _burst,
    "together": _disc,
    "cohere": _disc,
}


def provider_logo_image(name: str, size: int = 28, scheme: str | None = None):
    """Return a PIL RGBA image for the provider (real PNG if present, else glyph)."""
    from PIL import Image, ImageDraw

    key = provider_key(name, scheme)
    # Precedence: user override → bundled real logo → drawn glyph.
    png = _user_png(name, key) or _bundled_png(key)
    if png is not None:
        return Image.open(png).convert("RGBA").resize((size, size), Image.LANCZOS)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = _BRAND.get(key, (120, 130, 150))
    cx = cy = size / 2
    r = size * 0.42
    drawer = _DRAWERS.get(key)
    if drawer is not None:
        drawer(draw, cx, cy, r, color)
    else:
        _letter_badge(draw, size, color, (name[:1] or "?").upper())
    return img
