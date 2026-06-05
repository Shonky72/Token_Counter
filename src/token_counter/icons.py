"""Icon generation + the app's brand icon.

The brand icon is the user-supplied ``assets/app_icon.png`` (used for the tray,
every window, and the packaged .exe). If that file isn't present we draw a
4-row coloured-grid fallback so the app never ships without an icon.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

N_BARS = 5
_GRID_COLORS = [(74, 144, 217), (230, 140, 60), (70, 175, 110), (130, 130, 140)]


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
        color = _GRID_COLORS[r % len(_GRID_COLORS)]
        ry = pad + r * (row_h + gap)
        for c in range(cols):
            frac = 0.45 + 0.55 * (c / (cols - 1))  # ascending heights
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


def write_ico(path: str, base_size: int = 256) -> str:
    """Write a multi-resolution .ico (from the brand icon) for the executable."""
    img = app_icon_image(base_size)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(path, format="ICO", sizes=sizes)
    return path
