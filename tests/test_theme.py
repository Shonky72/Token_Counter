"""Sanity checks for the shared dark palette and helpers."""

import re

from token_counter import theme

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_palette_constants_are_valid_hex():
    for name in ("BG", "CARD", "CARD_HOVER", "CARD_BORDER", "TEXT", "SUBTEXT",
                 "TRACK", "ACCENT"):
        value = getattr(theme, name)
        assert HEX.match(value), f"{name}={value!r} is not #rrggbb"


def test_lighten_and_mix_return_hex():
    assert HEX.match(theme.lighten("#102030", 0.5))
    assert HEX.match(theme.mix("#000000", "#ffffff", 0.5))


def test_mix_endpoints():
    assert theme.mix("#000000", "#ffffff", 0.0) == "#000000"
    assert theme.mix("#000000", "#ffffff", 1.0) == "#ffffff"
    # Halfway is grey-ish (each channel ~127).
    assert theme.mix("#000000", "#ffffff", 0.5) == "#7f7f7f"
