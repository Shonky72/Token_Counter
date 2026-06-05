"""Load the bundled JetBrains Mono font for the app name in the GUI.

JetBrains Mono (SIL Open Font License) is shipped in ``assets/fonts``. On Windows
we register the .ttf at runtime with ``AddFontResourceExW`` so Tkinter can use it
without a system install. If the font file or registration is unavailable, we
fall back to ``Consolas`` (a monospace font present on every Windows install) so
the UI never breaks.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

JETBRAINS_MONO = "JetBrains Mono"
FALLBACK = "Consolas"

_FONT_FILES = ("JetBrainsMono-Regular.ttf", "JetBrainsMono-Bold.ttf")


def _font_dir() -> Path | None:
    try:
        from importlib.resources import files

        return Path(str(files("token_counter") / "assets" / "fonts"))
    except Exception:
        # Fallback for odd layouts: relative to this file.
        guess = Path(__file__).resolve().parent / "assets" / "fonts"
        return guess if guess.exists() else None


def _register_windows(path: Path) -> bool:
    try:  # pragma: no cover - Windows only
        import ctypes

        FR_PRIVATE = 0x10
        added = ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0)
        return bool(added)
    except Exception:
        return False


@lru_cache(maxsize=1)
def app_font_family() -> str:
    """Return the font family to use for the app name (registers it if needed)."""
    fdir = _font_dir()
    if fdir is None:
        return FALLBACK

    available = [fdir / name for name in _FONT_FILES if (fdir / name).exists()]
    if not available:
        return FALLBACK

    if sys.platform.startswith("win"):
        if any(_register_windows(p) for p in available):
            return JETBRAINS_MONO
        return FALLBACK

    # Off Windows we don't register, but report the family if the files are there
    # (Tk will use it only if the OS knows it; harmless for our headless tests).
    return JETBRAINS_MONO
