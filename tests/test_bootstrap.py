import sys

from token_counter import bootstrap


def test_log_file_path_under_data_dir():
    assert bootstrap.log_file_path().name == "token_counter.log"


def test_set_app_user_model_id_no_error():
    # Must be a harmless no-op off Windows.
    bootstrap.set_app_user_model_id()


def test_ensure_streams_replaces_none(monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "LOG_DIR", tmp_path)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    bootstrap.ensure_streams()
    # Both streams must now be writable so print() can't crash.
    assert sys.stdout is not None and sys.stderr is not None
    print("hello")  # would raise if stdout were still None
    sys.stdout.flush()
    assert (tmp_path / "token_counter.log").exists()


def test_ensure_streams_leaves_real_streams_alone(monkeypatch):
    sentinel_out, sentinel_err = sys.stdout, sys.stderr
    bootstrap.ensure_streams()
    assert sys.stdout is sentinel_out
    assert sys.stderr is sentinel_err
