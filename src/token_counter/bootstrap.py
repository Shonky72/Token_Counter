"""Startup hardening for the packaged app.

Two problems unique to a windowed (``--noconsole``) PyInstaller build:

  * ``sys.stdout`` / ``sys.stderr`` are ``None``, so the app's ``print()`` calls
    raise and the program dies *before the tray icon appears* — looking like
    "it's running but nothing shows". We point the streams at a log file.
  * A bare exception during startup vanishes with no console. We log the
    traceback and pop a dialog so failures are visible, not silent.

Also sets the Windows AppUserModelID so the taskbar shows the app correctly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

LOG_DIR = Path("~/.token_counter").expanduser()
APP_USER_MODEL_ID = "Shonky.tokn"


def log_file_path() -> Path:
    return LOG_DIR / "token_counter.log"


def _open_log():
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        return open(log_file_path(), "a", encoding="utf-8", buffering=1)
    except Exception:  # pragma: no cover - last resort
        return open(os.devnull, "w")


def ensure_streams() -> None:
    """Guarantee stdout/stderr are writable (prevents print() crashes when frozen)."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    log = _open_log()
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log


def set_app_user_model_id(appid: str = APP_USER_MODEL_ID) -> None:
    if not sys.platform.startswith("win"):
        return
    try:  # pragma: no cover - Windows only
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
    except Exception:
        pass


def log_startup() -> None:
    """Write the running build's identity to stdout (i.e. the log when frozen)."""
    try:
        from ._buildinfo import build_string

        print(f"[tokn] tokn {build_string()} starting (log: {log_file_path()})")
    except Exception:  # pragma: no cover - never block startup
        pass


def init(log_version: bool = True) -> None:
    ensure_streams()
    set_app_user_model_id()
    if log_version:
        log_startup()


def report_fatal(exc: BaseException) -> None:
    """Log a startup failure and try to show it in a dialog (never raise)."""
    import traceback

    tb = traceback.format_exc()
    try:
        print(f"[token-counter] FATAL: {exc}\n{tb}")
    except Exception:
        pass
    try:  # pragma: no cover - GUI only
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "tokn — startup error",
            f"{type(exc).__name__}: {exc}\n\nDetails were written to:\n{log_file_path()}",
        )
        root.destroy()
    except Exception:
        pass
