"""Shared theme for the GUI windows (dashboard, login, popup).

Material 3 (Material You) edition — one palette, switchable between **dark** and
**light** (and "system", which reads the OS preference). Window processes are
short-lived, so the palette is chosen once at process start via
:func:`set_palette` (called from ``app.main`` before the GUI modules import these
constants), then the constants below hold the active theme for the whole process.

Drop-in replacement: every existing constant name (BG, CARD, …) is preserved, so
no call sites change. The values are mapped onto the canonical Material 3 baseline
colour roles, and one new role — ``ON_ACCENT`` — is added so filled buttons keep
correct contrast on the M3 primary (light text on a light-purple primary is wrong;
M3 uses a dark on-primary in dark mode).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Material 3 baseline colour roles, flattened onto this app's constant names.
#   BG          -> surface
#   CARD        -> surfaceContainer        (cards read as gently raised)
#   CARD_HOVER  -> surfaceContainerHigh
#   CARD_BORDER -> outlineVariant
#   TEXT        -> onSurface
#   SUBTEXT     -> onSurfaceVariant
#   TRACK       -> surfaceContainerHighest  (gauge/progress track)
#   ACCENT      -> primary
#   ON_ACCENT   -> onPrimary                (text/icon on a filled primary)
#   FIELD       -> surfaceContainerHighest  (M3 filled text field)
#   TILE_BG     -> split-flap tile body
#   FLAP_FG     -> split-flap glyph
# ---------------------------------------------------------------------------

DARK = {
    "BG": "#141218",
    "CARD": "#211f26",
    "CARD_HOVER": "#2b2930",
    "CARD_BORDER": "#49454f",
    "TEXT": "#e6e0e9",
    "SUBTEXT": "#cac4d0",
    "TRACK": "#36343b",
    "ACCENT": "#d0bcff",
    "ON_ACCENT": "#381e72",
    "FIELD": "#2b2930",
    "TILE_BG": "#0c0a10",   # split-flap tile body
    "FLAP_FG": "#f3eef9",   # split-flap glyph
}

LIGHT = {
    "BG": "#fdf7ff",
    "CARD": "#ffffff",
    "CARD_HOVER": "#f2ecf4",
    "CARD_BORDER": "#cac4cf",
    "TEXT": "#1d1b20",
    "SUBTEXT": "#49454e",
    "TRACK": "#e6e0e9",
    "ACCENT": "#65558f",
    "ON_ACCENT": "#ffffff",
    "FIELD": "#f2ecf4",
    "TILE_BG": "#2a2730",
    "FLAP_FG": "#f6f1fb",
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
ON_ACCENT = DARK["ON_ACCENT"]
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
    global ON_ACCENT, FIELD, TILE_BG, FLAP_FG, _ACTIVE
    resolved = resolve_theme(name)
    p = LIGHT if resolved == "light" else DARK
    BG, CARD, CARD_HOVER, CARD_BORDER = p["BG"], p["CARD"], p["CARD_HOVER"], p["CARD_BORDER"]
    TEXT, SUBTEXT, TRACK, ACCENT = p["TEXT"], p["SUBTEXT"], p["TRACK"], p["ACCENT"]
    ON_ACCENT, FIELD, TILE_BG, FLAP_FG = p["ON_ACCENT"], p["FIELD"], p["TILE_BG"], p["FLAP_FG"]
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
    """Style ttk widgets to the active Material 3 palette. Best-effort/headless-safe."""
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
        # M3 tabs: flat, with the active tab carrying the surface + primary text.
        style.configure("TNotebook", background=BG, bordercolor=CARD_BORDER)
        style.configure("TNotebook.Tab", background=BG, foreground=SUBTEXT,
                        padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", BG)],
                  foreground=[("selected", ACCENT)])
        style.configure("TLabelframe", background=CARD, foreground=TEXT,
                        bordercolor=CARD_BORDER)
        style.configure("TLabelframe.Label", background=CARD, foreground=TEXT)
        # Buttons: M3 "tonal"-ish default; pill-ish padding (Tk can't round them).
        style.configure("TButton", background=CARD_HOVER, foreground=TEXT,
                        bordercolor=CARD_BORDER, focuscolor=BG, padding=(16, 7),
                        relief="flat")
        style.map("TButton", background=[("active", lighten(CARD_HOVER, 0.06)
                                          if active_theme() == "dark" else darken(CARD_HOVER, 0.04))])
        # Filled primary button — correct on-primary contrast for the active theme.
        style.configure("Accent.TButton", background=ACCENT, foreground=ON_ACCENT,
                        padding=(18, 7), relief="flat")
        style.map("Accent.TButton",
                  background=[("active", lighten(ACCENT, 0.12)
                              if active_theme() == "dark" else darken(ACCENT, 0.08))])
        style.configure("TRadiobutton", background=BG, foreground=TEXT)
        style.map("TRadiobutton", background=[("active", BG)],
                  indicatorcolor=[("selected", ACCENT)])
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)],
                  indicatorcolor=[("selected", ACCENT)])
        # M3 filled text field.
        style.configure("TEntry", fieldbackground=FIELD, foreground=TEXT,
                        insertcolor=TEXT, bordercolor=CARD_BORDER, relief="flat")
        style.configure("TCombobox", fieldbackground=FIELD, foreground=TEXT,
                        background=CARD_HOVER, arrowcolor=TEXT, bordercolor=CARD_BORDER)
        # The readonly combobox uses the "readonly" state, not the default one.
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", FIELD), ("disabled", CARD)],
            foreground=[("readonly", TEXT), ("disabled", SUBTEXT)],
            selectbackground=[("readonly", FIELD)],
            selectforeground=[("readonly", TEXT)],
            background=[("active", CARD_HOVER)],
        )
        # M3 progress / scrollbar troughs read off the gauge track.
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=TRACK,
                        bordercolor=TRACK, lightcolor=ACCENT, darkcolor=ACCENT)
        style.configure("TScrollbar", background=CARD_HOVER, troughcolor=BG,
                        bordercolor=BG, arrowcolor=SUBTEXT)
        # The combobox *popdown list* is a classic Tk Listbox that ttk.Style does
        # NOT reach — style it through the option database so it's readable.
        root.option_add("*TCombobox*Listbox.background", CARD)
        root.option_add("*TCombobox*Listbox.foreground", TEXT)
        root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        root.option_add("*TCombobox*Listbox.selectForeground", ON_ACCENT)
        root.option_add("*TCombobox*Listbox.borderWidth", 0)
        root.configure(bg=BG)
    except Exception:
        pass


# Back-compat alias (older call sites used apply_ttk_dark).
apply_ttk_dark = apply_theme
