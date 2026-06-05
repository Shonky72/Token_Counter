"""Build a Windows .msi installer with cx_Freeze.

    python -m pip install -e . cx_Freeze
    python -m token_counter icon icon.ico
    python setup_msi.py bdist_msi
    ->  dist\\TokenCounter-<version>-win64.msi

The MSI does a per-user install (no admin prompt) to
``%LOCALAPPDATA%\\Programs\\TokenCounter``, adds Start Menu + Desktop shortcuts,
and registers an Add/Remove Programs entry. To install system-wide instead,
set ``all_users`` to True and ``initial_target_dir`` to ``[ProgramFilesFolder]``
below (that build then requires admin rights to install).

Easiest: just double-click ``build_msi.bat``.
"""

import sys
from pathlib import Path

from cx_Freeze import Executable, setup

try:
    from token_counter import __version__ as VERSION
except Exception:
    VERSION = "0.1.0"

# What to bundle. The dynamic ones (tkinter, keyring backends, the pystray
# Windows backend) are listed explicitly so the freezer doesn't miss them.
build_exe_options = {
    "packages": [
        "token_counter",
        "tkinter",
        "keyring",
        "keyring.backends",
        "pystray",
        "PIL",
        "yaml",
    ],
    "excludes": ["pytest", "tkinter.test", "test", "unittest"],
    "include_msvcr": True,
}

# No console window for the GUI/tray app.
base = "Win32GUI" if sys.platform == "win32" else None

icon = "icon.ico" if Path("icon.ico").exists() else None

# Start Menu + Desktop shortcuts, via the MSI Shortcut table.
# Columns: Shortcut, Directory_, Name, Component_, Target, Arguments,
#          Description, Hotkey, Icon_, IconIndex, ShowCmd, WkDir
shortcut_table = [
    (
        "StartMenuShortcut", "ProgramMenuFolder", "Token Counter",
        "TARGETDIR", "[TARGETDIR]TokenCounter.exe", None,
        "Live AI token usage tracker", None, None, None, None, "TARGETDIR",
    ),
    (
        "DesktopShortcut", "DesktopFolder", "Token Counter",
        "TARGETDIR", "[TARGETDIR]TokenCounter.exe", None,
        "Live AI token usage tracker", None, None, None, None, "TARGETDIR",
    ),
]

bdist_msi_options = {
    # A stable GUID so future versions upgrade in place instead of stacking.
    "upgrade_code": "{6D9F2C1A-7E4B-4C3D-9F8A-1B2C3D4E5F60}",
    "add_to_path": False,
    "all_users": False,  # per-user install -> no admin prompt
    "initial_target_dir": r"[LocalAppDataFolder]\Programs\TokenCounter",
    "data": {"Shortcut": shortcut_table},
}

executables = [
    Executable(
        "run_token_counter.py",
        base=base,
        target_name="TokenCounter.exe",
        icon=icon,
        copyright="Token Counter",
    )
]

setup(
    name="TokenCounter",
    version=VERSION,
    description="Live AI token usage tracker for the system tray",
    options={"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables=executables,
)
