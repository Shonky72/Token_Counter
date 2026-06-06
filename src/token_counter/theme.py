"""Shared dark theme for the GUI windows (dashboard, login, popup).

One palette so the windows look consistent, plus a helper to apply a dark ttk
style to the login window's themed widgets.
"""

from __future__ import annotations

BG = "#16161a"
CARD = "#222228"
CARD_HOVER = "#2b2b33"
CARD_BORDER = "#34343d"
TEXT = "#ececed"
SUBTEXT = "#9a9aa6"
TRACK = "#3a3a44"
ACCENT = "#5a78c8"


def lighten(hex_color: str, amount: float) -> str:
    """Lighten a #rrggbb colour toward white by ``amount`` (0..1)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def mix(c1: str, c2: str, t: float) -> str:
    """Linear blend between two #rrggbb colours, t in 0..1."""
    a = [int(c1.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    m = [int(a[i] + (b[i] - a[i]) * t) for i in range(3)]
    return f"#{m[0]:02x}{m[1]:02x}{m[2]:02x}"


def apply_ttk_dark(root) -> None:
    """Style ttk widgets dark to match the dashboard. Best-effort/headless-safe."""
    try:
        from tkinter import ttk

        style = ttk.Style(root)
        try:
            style.theme_use("clam")  # the most themable built-in
        except Exception:
            pass
        style.configure(".", background=BG, foreground=TEXT, fieldbackground=CARD,
                        bordercolor=CARD_BORDER)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Sub.TLabel", background=BG, foreground=SUBTEXT)
        style.configure("CardSub.TLabel", background=CARD, foreground=SUBTEXT)
        style.configure("TLabelframe", background=CARD, foreground=TEXT,
                        bordercolor=CARD_BORDER)
        style.configure("TLabelframe.Label", background=CARD, foreground=TEXT)
        style.configure("TButton", background=CARD, foreground=TEXT,
                        bordercolor=CARD_BORDER, focuscolor=BG)
        style.map("TButton", background=[("active", CARD_HOVER)])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", lighten(ACCENT, 0.15))])
        style.configure("TEntry", fieldbackground="#1c1c22", foreground=TEXT,
                        insertcolor=TEXT)
        style.configure("TCombobox", fieldbackground="#1c1c22", foreground=TEXT,
                        background=CARD, arrowcolor=TEXT, bordercolor=CARD_BORDER)
        # The readonly combobox uses the "readonly" state, not the default one.
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#1c1c22"), ("disabled", CARD)],
            foreground=[("readonly", TEXT), ("disabled", SUBTEXT)],
            selectbackground=[("readonly", "#1c1c22")],
            selectforeground=[("readonly", TEXT)],
            background=[("active", CARD)],
        )
        # The combobox *popdown list* is a classic Tk Listbox that ttk.Style does
        # NOT reach — style it through the option database so it's dark + readable.
        root.option_add("*TCombobox*Listbox.background", CARD)
        root.option_add("*TCombobox*Listbox.foreground", TEXT)
        root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        root.option_add("*TCombobox*Listbox.borderWidth", 0)
        root.configure(bg=BG)
    except Exception:
        pass
