import pytest

from token_counter import icons

pytest.importorskip("PIL")


def test_status_color_thresholds():
    assert icons.status_color(None) is None
    assert icons.status_color(10) == (84, 176, 111)    # green
    assert icons.status_color(80) == (235, 169, 60)    # amber
    assert icons.status_color(95) == (224, 76, 76)     # red
    # custom threshold
    assert icons.status_color(85, threshold=80) == (224, 76, 76)


def test_status_icon_image_returns_image():
    img = icons.status_icon_image(64, percent=95)
    assert img.size == (64, 64)
    assert img.mode == "RGBA"
    # no percent → unchanged brand icon (still an image)
    assert icons.status_icon_image(64, percent=None).size == (64, 64)
