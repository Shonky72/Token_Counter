import sys

from token_counter import shortcut


def test_is_supported_matches_platform():
    assert shortcut.is_supported() == sys.platform.startswith("win")


def test_noop_off_windows():
    if shortcut.is_supported():
        return  # only exercised off Windows
    ok, msg = shortcut.create_desktop_shortcut(target="C:/x.exe")
    assert ok is False
    assert "Windows" in msg


def test_ps_quote_escapes_single_quotes():
    assert shortcut._ps_quote("a'b") == "'a''b'"
