import sys

from token_counter import startup


def test_is_supported_matches_platform():
    assert startup.is_supported() == sys.platform.startswith("win")


def test_startup_command_runs_the_tray():
    cmd = startup.startup_command()
    assert "-m token_counter run" in cmd


def test_noop_on_non_windows():
    if startup.is_supported():
        return  # exercised only off-Windows
    assert startup.is_enabled() is False
    assert startup.enable() is False
    assert startup.disable() is False
    assert startup.set_enabled(True) is False


def test_detailed_helpers_report_off_windows():
    if startup.is_supported():
        return
    ok, msg = startup.set_enabled_detailed(True)
    assert ok is False and "Windows" in msg
    ok, msg = startup.enable_detailed()
    assert ok is False and isinstance(msg, str)


def test_startup_shortcut_helpers_noop_off_windows():
    from token_counter import shortcut

    if shortcut.is_supported():
        return
    ok, _ = shortcut.create_startup_shortcut()
    assert ok is False
    ok, _ = shortcut.remove_startup_shortcut()
    assert ok is False
    assert shortcut.startup_shortcut_exists() is False
