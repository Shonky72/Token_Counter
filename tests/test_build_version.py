import importlib.util
from pathlib import Path

from token_counter import __version__, build_string
from token_counter import app, bootstrap

_STAMP = Path(__file__).resolve().parents[1] / "tools" / "stamp_build.py"


def _load_stamp():
    spec = importlib.util.spec_from_file_location("stamp_build", _STAMP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_build_string_contains_version():
    assert __version__ in build_string()
    assert "(" in build_string() and ")" in build_string()


def test_version_flag(capsys):
    rc = app.main(["--version"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tokn" in out
    assert __version__ in out


def test_startup_logs_version(capsys):
    bootstrap.log_startup()
    out = capsys.readouterr().out
    assert "tokn" in out
    assert __version__ in out


def test_stamp_generates_compilable_outputs():
    stamp = _load_stamp()
    # The version it reads from _buildinfo.py must match the package version.
    assert stamp.current_version() == __version__

    info = stamp.buildinfo_text("1.2.3", "abc1234", "2026-06-05")
    ns: dict = {}
    exec(compile(info, "_buildinfo.py", "exec"), ns)
    assert ns["VERSION"] == "1.2.3"
    assert ns["build_string"]() == "1.2.3 (abc1234, 2026-06-05)"

    # version_info.txt must be valid Python (PyInstaller execs it).
    vinfo = stamp.version_info_text("1.2.3")
    compile(vinfo, "version_info.txt", "exec")
    assert "1, 2, 3, 0" in vinfo
    assert "tokn" in vinfo
