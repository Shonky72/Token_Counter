from token_counter.models import BudgetStatus, ModelBudgetStatus
from token_counter.render import detail_text, human, overall_percent, tooltip_text


def test_human():
    assert human(500) == "500"
    assert human(1500) == "1.5K"
    assert human(1_000_000) == "1M"
    assert human(1_500_000) == "1.50M"


def test_tooltip_includes_used_and_remaining():
    s = BudgetStatus(
        provider="claude", period="monthly", limit=1_000_000, used=620_000,
        models=[ModelBudgetStatus("opus", 620_000, 600_000)],
    )
    text = tooltip_text([s])
    assert "claude" in text
    assert "1M" in text  # limit
    assert "62%" in text


def test_tooltip_handles_error():
    s = BudgetStatus(provider="x", period="monthly", limit=None, used=0, error="bad key")
    assert "bad key" in tooltip_text([s])


def test_overall_percent_is_worst_case():
    a = BudgetStatus("a", "monthly", 100, 10)   # 10%
    b = BudgetStatus("b", "monthly", 100, 90)   # 90%
    assert overall_percent([a, b]) == 90


def test_overall_percent_none_when_no_limits():
    s = BudgetStatus("a", "monthly", None, 50)
    assert overall_percent([s]) is None


def test_detail_text_lists_models():
    s = BudgetStatus(
        provider="claude", period="monthly", limit=1000, used=300,
        models=[ModelBudgetStatus("opus", 200, 500), ModelBudgetStatus("sonnet", 100, None)],
    )
    text = detail_text([s])
    assert "opus" in text and "sonnet" in text
