"""Build identity for Token Counter.

These constants are the single source of truth for the app's version, and are
overwritten at package time by ``tools/stamp_build.py`` (which fills in the real
git commit and build date). In a plain source checkout they stay at their
defaults. ``build_string()`` is shown in ``--version``, the tray menu, the
dashboard header, and the startup log — so you can always tell exactly which
build is running.
"""

from __future__ import annotations

VERSION = "0.1.0"
GIT_SHA = "dev"
BUILT_AT = "source"


def build_string() -> str:
    return f"{VERSION} ({GIT_SHA}, {BUILT_AT})"
