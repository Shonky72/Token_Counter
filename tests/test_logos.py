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
