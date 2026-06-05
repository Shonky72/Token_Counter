"""Regression tests for the tray menu (no display required)."""

from token_counter.tray import TrayApp


def _app():
    # TrayApp only needs an engine for run(); these tests touch pure helpers.
    return TrayApp(engine=None, refresh_seconds=30)


def test_refresh_label_accepts_pystray_item():
    # pystray calls a callable menu label as text(item) — it must not raise.
    app = _app()
    label = app._refresh_label(object())  # the MenuItem pystray passes
    assert label.startswith("Refresh now (last:")
    assert "never" in label  # no refresh yet


def test_refresh_label_no_arg_also_works():
    assert _app()._refresh_label().startswith("Refresh now (last:")


def test_refresh_label_shows_time_after_refresh():
    from datetime import datetime

    app = _app()
    app._last_refresh = datetime(2026, 6, 5, 14, 32, 5)
    assert "14:32:05" in app._refresh_label(object())
