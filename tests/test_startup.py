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
