from token_counter import analytics


def test_burn_rate_rising_series():
    # used grows 0→3600 over 1 hour → 3600 tokens/hour.
    base = 1_000_000.0
    samples = [(base + i * 600, i * 600) for i in range(7)]  # every 10 min, +600
    rate = analytics.burn_rate_per_hour(samples)
    assert abs(rate - 3600) < 1e-6


def test_burn_rate_ignores_window_reset_drop():
    # used climbs, resets to 0, climbs again — only the rises count.
    base = 0.0
    samples = [(base + 0, 0), (base + 3600, 1000), (base + 7200, 0), (base + 10800, 500)]
    rate = analytics.burn_rate_per_hour(samples)
    # gained = 1000 + 500 = 1500 over 3 hours = 500/h
    assert abs(rate - 500) < 1e-6


def test_burn_rate_insufficient_data():
    assert analytics.burn_rate_per_hour([]) == 0.0
    assert analytics.burn_rate_per_hour([(1.0, 5)]) == 0.0


def test_runout_text_buckets():
    assert analytics.runout_text(None, 10) == ""
    assert analytics.runout_text(1000, 0) == ""
    assert analytics.runout_text(600, 3600).endswith("m")     # 10 min
    assert analytics.runout_text(7200, 3600) == "runs out in ~2h"
    assert "d" in analytics.runout_text(360000, 3600)         # ~4.2d


def test_spark_points_bounds_and_count():
    pts = analytics.spark_points([1, 2, 3, 4], w=40, h=10)
    assert len(pts) == 4
    for x, y in pts:
        assert 0 <= x <= 40 and 0 <= y <= 10
    # rising series → last point is higher (smaller y) than first
    assert pts[-1][1] < pts[0][1]


def test_spark_points_flat_is_midline():
    pts = analytics.spark_points([5, 5, 5], w=30, h=10)
    ys = {round(y, 3) for _, y in pts}
    assert len(ys) == 1  # all same height


def test_spark_points_too_few():
    assert analytics.spark_points([1], 10, 10) == []
