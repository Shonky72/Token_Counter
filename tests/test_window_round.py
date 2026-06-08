from token_counter.window_ui import _round_rect_points


def test_round_rect_points_closed_and_bounded():
    pts = _round_rect_points(0, 0, 100, 40, 12)
    # flat list of x,y pairs
    assert len(pts) % 2 == 0 and len(pts) >= 8
    xs = pts[0::2]
    ys = pts[1::2]
    assert min(xs) >= 0 and max(xs) <= 100
    assert min(ys) >= 0 and max(ys) <= 40


def test_round_rect_radius_clamped_to_half():
    # r larger than half the smaller side must not invert/escape bounds.
    pts = _round_rect_points(0, 0, 20, 10, 999)
    xs = pts[0::2]
    ys = pts[1::2]
    assert min(xs) >= 0 and max(xs) <= 20
    assert min(ys) >= 0 and max(ys) <= 10
