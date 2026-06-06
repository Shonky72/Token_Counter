"""Split-flap (mechanical flip-board) number display for the dashboard + compact.

The visible amounts animate like an airport/clock split-flap board: each
character sits on a dark tile with a centre divider line and "flaps" through the
alphabet before locking onto its final glyph. Left tiles settle before right
tiles, so a number resolves left-to-right.

The widget does NOT run its own timer — a single shared animation clock in
``window_ui`` calls :meth:`FlapDisplay.render_progress` each frame, which keeps
every card perfectly in sync and smooth. The pure helpers (``flap_glyph``,
``settle_fraction``, ``FLAP_ALPHABET``) carry the testable logic.
"""

from __future__ import annotations

import string

# Every glyph that can appear in a formatted amount, plus letters for unit words
# ("tokens", "messages", "no data"). The space is first so padding flaps too.
FLAP_ALPHABET = " 0123456789.,/%:-KMB" + string.ascii_uppercase + string.ascii_lowercase

_INDEX = {ch: i for i, ch in enumerate(FLAP_ALPHABET)}
_N = len(FLAP_ALPHABET)


def settle_fraction(position: int, count: int) -> float:
    """Progress (0..1) at which tile ``position`` locks onto its target glyph.

    Left tiles settle earlier than right tiles → the number resolves L→R.
    """
    if count <= 1:
        return 0.6
    return 0.45 + 0.5 * (position / (count - 1))


def flap_glyph(target_char: str, position: int, progress: float, count: int = 1) -> str:
    """The glyph tile ``position`` should show at overall ``progress`` (0..1).

    Before the tile's settle point it rolls backward through the alphabet so it
    lands *exactly* on ``target_char`` at the settle point (a flap "counting up").
    At/after settle — and at ``progress >= 1`` — it shows the target. Glyphs not
    in the alphabet are shown statically.
    """
    if progress >= 1.0 or target_char not in _INDEX:
        return target_char
    settle = settle_fraction(position, count)
    if progress >= settle:
        return target_char
    local = progress / settle if settle > 0 else 1.0      # 0..1 within the flap
    target_idx = _INDEX[target_char]
    flips = 9 + (position % 5)                              # vary speed per tile
    idx = (target_idx - round((1.0 - local) * flips)) % _N
    return FLAP_ALPHABET[idx]


def flap_string(target: str, progress: float) -> str:
    """Render the whole string at ``progress`` (each tile via :func:`flap_glyph`)."""
    n = len(target)
    return "".join(flap_glyph(ch, i, progress, n) for i, ch in enumerate(target))


class FlapDisplay:
    """A Canvas that paints a string as split-flap tiles. Timer-free."""

    def __init__(self, parent, tk, *, bg, font, tile_w=12, tile_h=20, gap=1,
                 tile_bg="#0d0d0f", fg="#f2f2f3", max_chars=22):
        self.tk = tk
        self.tile_w = tile_w
        self.tile_h = tile_h
        self.gap = gap
        self.tile_bg = tile_bg
        self.fg = fg
        self.font = font
        self.max_chars = max_chars
        self._target = ""
        self._accent = fg
        self.canvas = tk.Canvas(parent, bg=bg, highlightthickness=0,
                                height=tile_h, width=(tile_w + gap) * 1)

    def widget(self):
        return self.canvas

    def _draw(self, text: str, glow: float = 0.0):
        c = self.canvas
        text = text[: self.max_chars]
        n = max(1, len(text))
        width = (self.tile_w + self.gap) * n
        if int(c["width"]) != width:
            c.configure(width=width)
        c.delete("all")
        tw, th, gap = self.tile_w, self.tile_h, self.gap
        for i, ch in enumerate(text):
            x = i * (tw + gap)
            # Tile body + a subtle top/bottom split so it reads as a flip card.
            c.create_rectangle(x, 0, x + tw, th, fill=self.tile_bg, outline="")
            c.create_rectangle(x, 0, x + tw, th / 2, fill=_lighten(self.tile_bg, 0.06),
                               outline="")
            c.create_line(x, th / 2, x + tw, th / 2, fill="#000000")
            fill = self.fg if glow <= 0 else _mix(self.fg, self._accent, glow)
            c.create_text(x + tw / 2, th / 2, text=ch, fill=fill, font=self.font)

    def set_static(self, text: str):
        self._target = text
        self._draw(text)

    def render_progress(self, target: str, progress: float, accent: str | None = None):
        self._target = target
        if accent:
            self._accent = accent
        # A brief glow as the tiles lock in (last 15% of the reveal).
        glow = max(0.0, (progress - 0.85) / 0.15) if progress < 1.0 else 0.0
        self._draw(flap_string(target, progress), glow=glow)


def _lighten(hex_color: str, amount: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def _mix(c1: str, c2: str, t: float) -> str:
    a = [int(c1.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    m = [int(a[i] + (b[i] - a[i]) * t) for i in range(3)]
    return f"#{m[0]:02x}{m[1]:02x}{m[2]:02x}"
