import subprocess
import sys

from token_counter import relaunch, shortcut


def test_is_supported_matches_platform():
    assert shortcut.is_supported() == sys.platform.startswith("win")


def test_popen_kwargs_hides_console_only_on_windows():
    kw = relaunch.popen_kwargs()
    if sys.platform.startswith("win"):
        assert "creationflags" in kw
    else:
        assert kw == {}


def test_startup_shortcut_exists_spawns_no_process(monkeypatch):
    # The tray polls this on a timer — it must never shell out (shelling out
    # flashed a console window every refresh).
    def boom(*a, **k):  # pragma: no cover - only fires on regression
        raise AssertionError("startup_shortcut_exists must not spawn a process")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    assert shortcut.startup_shortcut_exists() in (True, False)
    shortcut.remove_startup_shortcut()  # also pure-filesystem; must not spawn


def test_startup_shortcut_filesystem_roundtrip(tmp_path, monkeypatch):
    # Force a fake Startup dir and exercise the pure-filesystem path on any OS.
    monkeypatch.setattr(shortcut, "is_supported", lambda: True)
    monkeypatch.setattr(shortcut, "_startup_dir", lambda: tmp_path)
    assert shortcut.startup_shortcut_exists("tokn") is False
    (tmp_path / "tokn.lnk").write_text("x")
    assert shortcut.startup_shortcut_exists("tokn") is True
    ok, msg = shortcut.remove_startup_shortcut("tokn")
    assert ok and msg == "removed"
    assert shortcut.startup_shortcut_exists("tokn") is False


def test_noop_off_windows():
    if shortcut.is_supported():
        return  # only exercised off Windows
    ok, msg = shortcut.create_desktop_shortcut(target="C:/x.exe")
    assert ok is False
    assert "Windows" in msg


def test_ps_quote_escapes_single_quotes():
    assert shortcut._ps_quote("a'b") == "'a''b'"
