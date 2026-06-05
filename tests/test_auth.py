import os

import token_counter.auth as auth
from token_counter.auth import CredentialStore, load_credentials_into_env
from token_counter.config import parse_config


def _file_store(tmp_path, monkeypatch):
    # Force the local-file fallback so the test never touches a real keyring.
    monkeypatch.setattr(auth, "_HAVE_KEYRING", False)
    return CredentialStore(fallback_path=tmp_path / "creds.json")


def test_set_get_delete_roundtrip(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch)
    assert store.get("claude") is None
    store.set("claude", "sk-test-123")
    assert store.get("claude") == "sk-test-123"
    assert store.has_any("claude") is True
    store.delete("claude")
    assert store.get("claude") is None
    assert store.has_any("claude") is False


def test_kinds_are_separate(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch)
    store.set("gemini", "api-123", "api_key")
    store.set("gemini", '{"access_token": "x"}', "oauth")
    assert store.get("gemini", "api_key") == "api-123"
    assert store.get("gemini", "oauth") == '{"access_token": "x"}'


def test_load_credentials_into_env(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch)
    store.set("claude", "sk-env-abc")
    cfg = parse_config(
        {"providers": [{"name": "claude", "type": "rate_limit", "api_key_env": "TC_TEST_KEY"}]}
    )
    monkeypatch.delenv("TC_TEST_KEY", raising=False)
    load_credentials_into_env(store, cfg.providers)
    assert os.environ["TC_TEST_KEY"] == "sk-env-abc"


def test_backend_reported(tmp_path, monkeypatch):
    store = _file_store(tmp_path, monkeypatch)
    assert store.backend == "local-file"
