"""Every catalog service should get its own drawn glyph (not the letter badge)."""

import pytest

from token_counter import catalog
from token_counter import logos

PIL = pytest.importorskip("PIL")


def test_every_service_has_a_drawn_glyph():
    for key in catalog.service_keys():
        # provider_key maps the service id to a glyph family, never "generic".
        assert logos.provider_key(key) == key
        assert key in logos._DRAWERS, f"{key} falls back to the letter badge"


def test_logo_image_size_and_mode():
    img = logos.provider_logo_image("grok", size=28)
    assert img.size == (28, 28)
    assert img.mode == "RGBA"


def test_unknown_provider_uses_letter_badge():
    assert logos.provider_key("totally-unknown") == "generic"
    img = logos.provider_logo_image("totally-unknown", size=20)
    assert img.size == (20, 20)


def test_bundled_png_used_when_present():
    # At least the fetched marks should resolve to a bundled PNG, not a glyph.
    bundled = [k for k in catalog.service_keys() if logos._bundled_png(k)]
    assert bundled, "expected some bundled logo PNGs to ship"
    for key in bundled:
        img = logos.provider_logo_image(key, 28)
        assert img.size == (28, 28) and img.mode == "RGBA"


def test_grok_glyph_colour_is_visible_on_dark():
    # Grok's drawn-glyph colour must not be near-black (invisible on the dark bg).
    r, g, b = logos._BRAND["grok"]
    assert max(r, g, b) > 120
