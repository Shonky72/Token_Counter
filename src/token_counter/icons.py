"""Icon generation + the app's brand icon.

The brand icon is the user-supplied ``assets/app_icon.png`` (used for the tray,
every window, and the packaged .exe). If that file isn't present we draw a
4-row coloured-grid fallback so the app never ships without an icon.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

N_BARS = 5
# Four row colours matching the brand mark: blue, orange, green, grey.
_GRID_COLORS = [(83, 152, 219), (237, 142, 66), (84, 176, 111), (138, 138, 144)]


def _icon_png_path() -> Path | None:
    try:
        from importlib.resources import files

        p = Path(str(files("token_counter") / "assets" / "app_icon.png"))
        return p if p.exists() else None
    except Exception:
        guess = Path(__file__).resolve().parent / "assets" / "app_icon.png"
        return guess if guess.exists() else None


def _draw_grid(size: int):
    """Fallback brand mark: 4 rows x 7 ascending rounded bars in brand colours."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cols, rows = 7, 4
    pad = size * 0.08
    gap = size * 0.02
    cell_w = (size - 2 * pad - gap * (cols - 1)) / cols
    row_h = (size - 2 * pad - gap * (rows - 1)) / rows
    radius = max(1, cell_w * 0.3)
    for r in range(rows):
        base = _GRID_COLORS[r % len(_GRID_COLORS)]
        ry = pad + r * (row_h + gap)
        for c in range(cols):
            frac = 0.45 + 0.55 * (c / (cols - 1))  # ascending heights
            # Slightly darken toward the right for a touch of depth.
            shade = 1.0 - 0.10 * (c / (cols - 1))
            color = tuple(max(0, int(v * shade)) for v in base)
            bh = row_h * frac
            x0 = pad + c * (cell_w + gap)
            y0 = ry + (row_h - bh)
            draw.rounded_rectangle((x0, y0, x0 + cell_w, ry + row_h),
                                   radius=radius, fill=color)
    return img


@lru_cache(maxsize=8)
def app_icon_image(size: int = 64):
    """The brand icon at ``size`` px (user PNG if present, else the grid)."""
    from PIL import Image

    png = _icon_png_path()
    if png is not None:
        return Image.open(png).convert("RGBA").resize((size, size), Image.LANCZOS)
    return _draw_grid(size)


def tray_meter_image(size: int = 64, percent: float | None = None):
    """Kept for back-compat; the tray now uses the brand icon regardless of usage."""
    return app_icon_image(size)


def status_color(percent: float | None, threshold: int = 90) -> tuple[int, int, int] | None:
    """Status-dot colour for a usage percent: green <75, amber <threshold, red ≥."""
    if percent is None:
        return None
    if percent >= threshold:
        return (224, 76, 76)      # red
    if percent >= 75:
        return (235, 169, 60)     # amber
    return (84, 176, 111)         # green


def status_icon_image(size: int = 64, percent: float | None = None, threshold: int = 90):
    """The brand icon with a small status dot in the corner reflecting ``percent``."""
    from PIL import Image, ImageDraw

    base = app_icon_image(size).copy()
    color = status_color(percent, threshold)
    if color is None:
        return base
    draw = ImageDraw.Draw(base)
    r = max(4, int(size * 0.22))
    cx = cy = size - r - max(1, int(size * 0.04))
    # White ring so the dot reads on any icon colour.
    draw.ellipse((cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2), fill=(255, 255, 255, 255))
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (255,))
    return base


def write_ico(path: str, base_size: int = 256) -> str:
    """Write a multi-resolution .ico (from the brand icon) for the executable."""
    img = app_icon_image(base_size)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(path, format="ICO", sizes=sizes)
    return path
