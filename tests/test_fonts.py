from token_counter import fonts


def test_app_font_family_returns_nonempty():
    fonts.app_font_family.cache_clear()
    fam = fonts.app_font_family()
    assert isinstance(fam, str) and fam


def test_bundled_font_files_present():
    # The OFL JetBrains Mono ttf should be shipped with the package.
    fdir = fonts._font_dir()
    assert fdir is not None
    assert (fdir / "JetBrainsMono-Regular.ttf").exists()


def test_family_is_jetbrains_when_font_present():
    fonts.app_font_family.cache_clear()
    # Off Windows we report the family when the files exist (no OS registration).
    fam = fonts.app_font_family()
    assert fam in (fonts.JETBRAINS_MONO, fonts.FALLBACK)
