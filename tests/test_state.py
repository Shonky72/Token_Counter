from token_counter import state


def test_set_get_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "STATE_PATH", tmp_path / "state.json")
    assert state.get("dashboard_geometry") is None
    state.set("dashboard_geometry", "500x600+10+20")
    assert state.get("dashboard_geometry") == "500x600+10+20"


def test_default_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "STATE_PATH", tmp_path / "nope.json")
    assert state.get("x", "fallback") == "fallback"


def test_multiple_keys_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(state, "STATE_PATH", tmp_path / "state.json")
    state.set("a", "1")
    state.set("b", "2")
    assert state.get("a") == "1" and state.get("b") == "2"
