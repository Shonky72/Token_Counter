"""Icon generation — the ascending-bars motif used everywhere.

One shape, two jobs:
  * ``app_icon_image`` / ``write_ico`` — the brand logo for the window and the
    packaged ``.exe``.
  * ``tray_meter_image`` — the same bars as a live usage meter: bars light up
    (and shift green→amber→red) as you approach your limit.

Drawn with Pillow so there are no binary assets to ship; scales cleanly from
16px (tray) to 256px (.exe icon).
"""

from __future__ import annotations

N_BARS = 5
APP_COLOR = (74, 144, 217)        # brand blue
DIM = (130, 130, 140, 70)         # unlit bar


def _severity(percent: float | None) -> tuple[int, int, int]:
    if percent is None:
        return APP_COLOR
    if percent >= 90:
        return (210, 60, 60)
    if percent >= 75:
        return (220, 160, 40)
    return (60, 170, 90)


def _draw_bars(size: int, lit: int, lit_color, dim_color=DIM):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = size * 0.12
    usable_w = size - 2 * pad
    usable_h = size - 2 * pad
    gap = usable_w / N_BARS * 0.32
    bar_w = (usable_w - gap * (N_BARS - 1)) / N_BARS
    radius = max(1, bar_w * 0.35)
    baseline = size - pad
    min_h = usable_h * 0.34

    for i in range(N_BARS):
        frac = i / (N_BARS - 1)
        h = min_h + (usable_h - min_h) * frac
        x0 = pad + i * (bar_w + gap)
        y0 = baseline - h
        color = lit_color if i < lit else dim_color
        draw.rounded_rectangle((x0, y0, x0 + bar_w, baseline), radius=radius, fill=color)
    return img


def app_icon_image(size: int = 64):
    """The brand logo: all bars lit, brand blue."""
    return _draw_bars(size, N_BARS, APP_COLOR)


def tray_meter_image(size: int = 64, percent: float | None = None):
    """Usage meter: number of lit bars + color track the worst usage."""
    if percent is None:
        lit = 1
    else:
        lit = max(1, min(N_BARS, round(percent / 100 * N_BARS)))
    return _draw_bars(size, lit, _severity(percent))


def write_ico(path: str, base_size: int = 256) -> str:
    """Write a multi-resolution .ico for the packaged executable."""
    img = app_icon_image(base_size)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(path, format="ICO", sizes=sizes)
    return path
