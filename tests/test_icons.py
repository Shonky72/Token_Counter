import sys

import pytest

PIL = pytest.importorskip("PIL")

from token_counter import icons, logos


def test_app_icon_image_fallback():
    icons.app_icon_image.cache_clear()
    img = icons.app_icon_image(128)
    assert img.size == (128, 128)
    assert img.mode == "RGBA"


def test_app_icon_uses_user_png(tmp_path, monkeypatch):
    png = tmp_path / "app_icon.png"
    PIL.Image.new("RGBA", (20, 20), (255, 0, 0, 255)).save(png)
    monkeypatch.setattr(icons, "_icon_png_path", lambda: png)
    icons.app_icon_image.cache_clear()
    img = icons.app_icon_image(32)
    assert img.size == (32, 32)
    assert img.getpixel((16, 16))[0] > 200  # red from our PNG
    icons.app_icon_image.cache_clear()


def test_write_ico(tmp_path):
    icons.app_icon_image.cache_clear()
    path = tmp_path / "icon.ico"
    icons.write_ico(str(path))
    assert path.exists() and path.stat().st_size > 0
    img = PIL.Image.open(path)
    assert img.format == "ICO"


def test_provider_key_detection():
    assert logos.provider_key("ChatGPT", "openai") == "openai"
    assert logos.provider_key("claude", "anthropic") == "claude"
    assert logos.provider_key("gemini") == "gemini"
    assert logos.provider_key("mystery") == "generic"


def test_provider_logo_image_renders():
    for name in ("claude", "openai", "gemini", "whatever"):
        img = logos.provider_logo_image(name, 28)
        assert img.size == (28, 28)
        assert img.mode == "RGBA"


def test_user_png_overrides_glyph(tmp_path, monkeypatch):
    monkeypatch.setattr(logos, "LOGO_DIR", tmp_path)
    # A red square dropped in as the "claude" logo should be picked up.
    PIL.Image.new("RGBA", (10, 10), (255, 0, 0, 255)).save(tmp_path / "claude.png")
    img = logos.provider_logo_image("claude", 28)
    assert img.size == (28, 28)
    # center pixel should be red-ish (from our PNG), not the terracotta glyph
    assert img.getpixel((14, 14))[0] > 200
