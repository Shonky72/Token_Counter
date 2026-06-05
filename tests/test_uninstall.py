import token_counter.auth as auth
from token_counter.auth import CredentialStore
from token_counter.uninstall import uninstall


def _file_store(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "_HAVE_KEYRING", False)
    return CredentialStore(fallback_path=tmp_path / "creds.json")


def test_uninstall_removes_saved_keys(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch)
    store.set("claude", "sk-1", "api_key")
    store.set("gemini", '{"t":1}', "oauth")
    assert store.has_any("claude")

    results = uninstall(remove_keys=True, store=store)

    assert not store.has_any("claude")
    assert not store.has_any("gemini")
    assert any("credential" in r for r in results)


def test_uninstall_keep_keys(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch)
    store.set("claude", "sk-1", "api_key")
    uninstall(remove_keys=False, store=store)
    assert store.get("claude", "api_key") == "sk-1"


def test_uninstall_reports_startup_and_shortcut(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch)
    results = uninstall(remove_keys=True, store=store)
    text = " ".join(results).lower()
    assert "startup" in text
    assert "shortcut" in text
