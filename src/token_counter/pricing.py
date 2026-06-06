"""Rough $ cost estimates for recorded token usage.

IMPORTANT: these are **approximate** public list prices (USD per **million**
tokens) for common models, baked in for convenience. They drift over time and
ignore tiers/discounts/batch pricing — treat the cost shown in the app as a
ballpark, not a bill. Override any of them with a JSON file at
``~/.token_counter/pricing.json`` of the form::

    {"gpt-4o": {"input": 2.5, "output": 10}, "my-model": {"input": 1, "output": 3}}

Matching is by case-insensitive substring of the model id, longest key first.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# model-id substring -> (input $/Mtok, output $/Mtok). Approximate list prices.
PRICES: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "o3-mini": (1.10, 4.40),
    "o3": (2.00, 8.00),
    # Anthropic Claude
    "claude-3-5-haiku": (0.80, 4.0),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3-5-sonnet": (3.0, 15.0),
    "claude-3-7-sonnet": (3.0, 15.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-3-opus": (15.0, 75.0),
    "claude-opus-4": (15.0, 75.0),
    # Google Gemini
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.0),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.0),
    # xAI Grok
    "grok-2": (2.0, 10.0),
    "grok-beta": (5.0, 15.0),
    # DeepSeek
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    # Mistral
    "mistral-small": (0.20, 0.60),
    "mistral-large": (2.0, 6.0),
    # Groq (Llama)
    "llama-3.1-8b": (0.05, 0.08),
    "llama-3.3-70b": (0.59, 0.79),
    # Perplexity
    "sonar": (1.0, 1.0),
    # Cohere
    "command-r-plus": (2.5, 10.0),
    "command-r": (0.15, 0.60),
}


@lru_cache(maxsize=1)
def _table() -> dict[str, tuple[float, float]]:
    table = dict(PRICES)
    try:
        path = Path("~/.token_counter/pricing.json").expanduser()
        if path.exists():
            user = json.loads(path.read_text(encoding="utf-8"))
            for model, p in (user or {}).items():
                if isinstance(p, dict) and "input" in p and "output" in p:
                    table[str(model).lower()] = (float(p["input"]), float(p["output"]))
                elif isinstance(p, (list, tuple)) and len(p) == 2:
                    table[str(model).lower()] = (float(p[0]), float(p[1]))
    except Exception:
        pass
    return table


def price_for(model: str) -> tuple[float, float] | None:
    """(input, output) $/Mtok for a model id, by longest substring match."""
    if not model:
        return None
    low = model.lower()
    best = None
    for key, price in _table().items():
        if key in low and (best is None or len(key) > len(best[0])):
            best = (key, price)
    return best[1] if best else None


def estimate_cost(model: str, input_tokens: int = 0, output_tokens: int = 0,
                  cache_read_tokens: int = 0, cache_creation_tokens: int = 0) -> float | None:
    """Estimated USD for one model's token counts, or None if the model is unknown.

    Cache reads are billed ~0.1× input; cache writes ~1.25× input (Anthropic-style
    approximation), folded into the input side.
    """
    price = price_for(model)
    if price is None:
        return None
    in_price, out_price = price
    input_units = input_tokens + 0.1 * cache_read_tokens + 1.25 * cache_creation_tokens
    return (input_units * in_price + output_tokens * out_price) / 1_000_000.0


def cost_for_usage(usages) -> float:
    """Total estimated USD for a list of ``ModelUsage`` (unknown models = $0)."""
    total = 0.0
    for u in usages:
        c = estimate_cost(
            u.model, u.input_tokens, u.output_tokens,
            getattr(u, "cache_read_tokens", 0), getattr(u, "cache_creation_tokens", 0),
        )
        if c:
            total += c
    return total


def format_cost(amount: float | None) -> str:
    """"$4.20" / "<$0.01" / "" for a USD amount."""
    if amount is None or amount <= 0:
        return ""
    if amount < 0.01:
        return "<$0.01"
    if amount < 100:
        return f"${amount:.2f}"
    return f"${amount:,.0f}"
