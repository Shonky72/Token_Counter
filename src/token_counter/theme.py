"""Shared theme for the GUI windows (dashboard, login, popup).

One palette, switchable between **dark** and **light** (and "system", which reads
the OS preference). Window processes are short-lived, so the palette is chosen
once at process start via :func:`set_palette` (called from ``app.main`` before the
GUI modules import these constants), then the constants below hold the active
theme for the whole process.
"""

from __future__ import annotations

DARK = {
    "BG": "#16161a",
    "CARD": "#222228",
    "CARD_HOVER": "#2b2b33",
    "CARD_BORDER": "#34343d",
    "TEXT": "#ececed",
    "SUBTEXT": "#9a9aa6",
    "TRACK": "#3a3a44",
    "ACCENT": "#5a78c8",
    "FIELD": "#1c1c22",
    "TILE_BG": "#0d0d0f",   # split-flap tile body
    "FLAP_FG": "#f2f2f3",   # split-flap glyph
}

LIGHT = {
    "BG": "#f3f4f6",
    "CARD": "#ffffff",
    "CARD_HOVER": "#eef0f4",
    "CARD_BORDER": "#d6d8de",
    "TEXT": "#1b1b20",
    "SUBTEXT": "#6a6a74",
    "TRACK": "#e3e4ea",
    "ACCENT": "#3f5fc0",
    "FIELD": "#ffffff",
    "TILE_BG": "#e7e8ee",
    "FLAP_FG": "#1b1b20",
}

# Active palette — module globals so existing `from .theme import BG` keeps
# working. Defaults to dark; `set_palette` rebinds them at process start.
BG = DARK["BG"]
CARD = DARK["CARD"]
CARD_HOVER = DARK["CARD_HOVER"]
CARD_BORDER = DARK["CARD_BORDER"]
TEXT = DARK["TEXT"]
SUBTEXT = DARK["SUBTEXT"]
TRACK = DARK["TRACK"]
ACCENT = DARK["ACCENT"]
FIELD = DARK["FIELD"]
TILE_BG = DARK["TILE_BG"]
FLAP_FG = DARK["FLAP_FG"]

_ACTIVE = "dark"


def set_palette(name: str) -> str:
    """Make ``name`` ("dark"/"light"/"system") the active palette for this process.

    Returns the resolved concrete name ("dark"/"light"). Call this **before** the
    GUI modules import the colour constants (i.e. early in ``app.main``).
    """
    global BG, CARD, CARD_HOVER, CARD_BORDER, TEXT, SUBTEXT, TRACK, ACCENT
    global FIELD, TILE_BG, FLAP_FG, _ACTIVE
    resolved = resolve_theme(name)
    p = LIGHT if resolved == "light" else DARK
    BG, CARD, CARD_HOVER, CARD_BORDER = p["BG"], p["CARD"], p["CARD_HOVER"], p["CARD_BORDER"]
    TEXT, SUBTEXT, TRACK, ACCENT = p["TEXT"], p["SUBTEXT"], p["TRACK"], p["ACCENT"]
    FIELD, TILE_BG, FLAP_FG = p["FIELD"], p["TILE_BG"], p["FLAP_FG"]
    _ACTIVE = resolved
    return resolved


def active_theme() -> str:
    return _ACTIVE


def resolve_theme(name: str) -> str:
    """Map a theme setting to a concrete "dark"/"light". "system" reads the OS."""
    if name == "light":
        return "light"
    if name == "system":
        return _system_theme()
    return "dark"


def _system_theme() -> str:
    """Windows app theme via the registry; dark elsewhere / on any failure."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        with key:
            apps_light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if apps_light else "dark"
    except Exception:
        return "dark"


def lighten(hex_color: str, amount: float) -> str:
    """Lighten a #rrggbb colour toward white by ``amount`` (0..1)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def darken(hex_color: str, amount: float) -> str:
    """Darken a #rrggbb colour toward black by ``amount`` (0..1)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = int(r * (1 - amount)), int(g * (1 - amount)), int(b * (1 - amount))
    return f"#{r:02x}{g:02x}{b:02x}"


def mix(c1: str, c2: str, t: float) -> str:
    """Linear blend between two #rrggbb colours, t in 0..1."""
    a = [int(c1.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    m = [int(a[i] + (b[i] - a[i]) * t) for i in range(3)]
    return f"#{m[0]:02x}{m[1]:02x}{m[2]:02x}"


def apply_theme(root) -> None:
    """Style ttk widgets to the active palette. Best-effort/headless-safe."""
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
        style.configure("TNotebook", background=BG, bordercolor=CARD_BORDER)
        style.configure("TNotebook.Tab", background=CARD, foreground=SUBTEXT,
                        padding=(12, 6))
        style.map("TNotebook.Tab", background=[("selected", BG)],
                  foreground=[("selected", TEXT)])
        style.configure("TLabelframe", background=CARD, foreground=TEXT,
                        bordercolor=CARD_BORDER)
        style.configure("TLabelframe.Label", background=CARD, foreground=TEXT)
        style.configure("TButton", background=CARD, foreground=TEXT,
                        bordercolor=CARD_BORDER, focuscolor=BG)
        style.map("TButton", background=[("active", CARD_HOVER)])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", lighten(ACCENT, 0.15))])
        style.configure("TRadiobutton", background=BG, foreground=TEXT)
        style.map("TRadiobutton", background=[("active", BG)])
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT,
                        insertcolor=TEXT)
        style.configure("TCombobox", fieldbackground=FIELD, foreground=TEXT,
                        background=CARD, arrowcolor=TEXT, bordercolor=CARD_BORDER)
        # The readonly combobox uses the "readonly" state, not the default one.
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", FIELD), ("disabled", CARD)],
            foreground=[("readonly", TEXT), ("disabled", SUBTEXT)],
            selectbackground=[("readonly", FIELD)],
            selectforeground=[("readonly", TEXT)],
            background=[("active", CARD)],
        )
        # The combobox *popdown list* is a classic Tk Listbox that ttk.Style does
        # NOT reach — style it through the option database so it's readable.
        root.option_add("*TCombobox*Listbox.background", CARD)
        root.option_add("*TCombobox*Listbox.foreground", TEXT)
        root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        root.option_add("*TCombobox*Listbox.borderWidth", 0)
        root.configure(bg=BG)
    except Exception:
        pass


# Back-compat alias (older call sites used apply_ttk_dark).
apply_ttk_dark = apply_theme
