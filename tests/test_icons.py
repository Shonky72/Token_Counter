import sys

import pytest

PIL = pytest.importorskip("PIL")

from token_counter import icons, logos


def test_tray_meter_image_size_and_mode():
    img = icons.tray_meter_image(64, 50)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_meter_lights_more_bars_as_usage_rises():
    # crude: a red (high) meter should have more non-transparent pixels than an
    # almost-empty one, since more bars are lit.
    def lit_pixels(p):
        alpha = icons.tray_meter_image(64, p).getchannel("A").tobytes()
        return sum(1 for b in alpha if b > 0)

    assert lit_pixels(95) >= lit_pixels(10)


def test_app_icon_image():
    assert icons.app_icon_image(128).size == (128, 128)


def test_write_ico(tmp_path):
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
