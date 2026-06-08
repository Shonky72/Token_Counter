"""The long-lived tray must drop accounts removed in the login window."""

from token_counter.config import load_config
from token_counter.engine import Engine
from token_counter.ledger import Ledger
from token_counter.tray import TrayApp


def _write(path, names):
    body = "\n".join(f"  - name: {n}\n    type: local_ledger" for n in names)
    path.write_text("providers:\n" + body + "\n", encoding="utf-8")


def test_reload_config_drops_removed_provider(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    _write(cfg_path, ["claude", "gemini", "groq"])
    cfg = load_config(cfg_path)
    engine = Engine(cfg, Ledger(tmp_path / "l.db"))
    tray = TrayApp(engine, config_path=str(cfg_path), app_config=cfg)
    assert len(tray.engine.config.providers) == 3
    assert "groq" in tray._usage_urls

    _write(cfg_path, ["claude", "gemini"])  # user removed groq in the login window
    tray._reload_config()

    names = [p.name for p in tray.engine.config.providers]
    assert names == ["claude", "gemini"]
    assert len(tray.engine.snapshot()) == 2
    assert "groq" not in tray._usage_urls


def test_reload_config_picks_up_added_provider(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    _write(cfg_path, ["claude"])
    cfg = load_config(cfg_path)
    tray = TrayApp(Engine(cfg, Ledger(tmp_path / "l.db")),
                   config_path=str(cfg_path), app_config=cfg)

    _write(cfg_path, ["claude", "gemini"])
    tray._reload_config()
    assert [p.name for p in tray.engine.config.providers] == ["claude", "gemini"]
