"""Pure-logic tests for the split-flap display helpers."""

from token_counter.flap import (
    FLAP_ALPHABET,
    flap_glyph,
    flap_string,
    layout_offset,
    settle_fraction,
)


def test_layout_offset_centres_and_never_negative():
    assert layout_offset(2, 15) == 6        # (15-2)//2
    assert layout_offset(15, 15) == 0       # exact fit
    assert layout_offset(20, 15) == 0       # longer than reserve → no negative
    assert layout_offset(0, 4) == 2


def test_alphabet_covers_amount_glyphs():
    for ch in "0123456789.,/% KMB":
        assert ch in FLAP_ALPHABET
    # letters for unit words like "tokens" / "messages" / "no data"
    for ch in "tokensmesagdNo":
        assert ch in FLAP_ALPHABET


def test_flap_glyph_lands_on_target_when_done():
    for ch in "0/9M ":
        assert flap_glyph(ch, 0, 1.0) == ch
        assert flap_glyph(ch, 3, 1.5) == ch


def test_flap_glyph_locks_at_settle_point():
    count = 5
    for pos in range(count):
        s = settle_fraction(pos, count)
        # exactly at (and past) the settle point the tile shows the target
        assert flap_glyph("7", pos, s, count) == "7"
        assert flap_glyph("7", pos, min(1.0, s + 0.05), count) == "7"


def test_flap_glyph_rolls_before_settle():
    # Well before settle it should usually NOT already equal the target.
    rolling = [flap_glyph("5", 4, p, 6) for p in (0.05, 0.1, 0.15, 0.2)]
    assert any(g != "5" for g in rolling)


def test_settle_fraction_monotonic_left_to_right():
    count = 8
    fracs = [settle_fraction(i, count) for i in range(count)]
    assert fracs == sorted(fracs)          # later positions settle later
    assert fracs[0] < fracs[-1]


def test_unknown_glyph_shown_statically():
    assert flap_glyph("€", 0, 0.1) == "€"   # not in alphabet → passthrough


def test_flap_string_preserves_length_and_finishes():
    target = "1.2M / 2.0M"
    assert len(flap_string(target, 0.3)) == len(target)
    assert flap_string(target, 1.0) == target


def test_digit_rolls_only_within_0_9():
    # A digit tile must roll like an odometer — always a digit, never a symbol.
    for p in (0.05, 0.15, 0.25, 0.35):
        g = flap_glyph("8", 6, p, 10)
        assert g in "0123456789"


def test_letter_rolls_within_its_case():
    for p in (0.05, 0.2, 0.35):
        assert flap_glyph("M", 2, p, 8) in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        assert flap_glyph("k", 2, p, 8) in "abcdefghijklmnopqrstuvwxyz"


def test_symbols_do_not_roll():
    for ch in " ./%":
        assert flap_glyph(ch, 1, 0.1, 8) == ch
