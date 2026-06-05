"""Catalog of AI services the user can add from the login window.

Each entry is everything needed to (a) populate the "add a service" dropdown,
(b) show an info ("i") popup explaining how to get the key, and (c) write a
provider block into the user's config. One key per service; all of that
service's models are tracked under it automatically.

Most services speak the OpenAI-compatible API (``scheme="openai"``) but on
different base URLs, so each carries a ``base_url`` and a cheap ``test_model``
used to fetch live rate-limit headers right after a key is saved.

Note: these track the *developer API* (your API key), not the consumer web/app
subscription — the apps expose no usage to outside tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Service:
    key: str                      # internal id + provider name in config
    display_name: str             # shown on the card
    type: str                     # provider plugin type
    scheme: str | None            # rate-limit header scheme
    key_url: str                  # where to create an API key
    help: str                     # short, friendly steps
    base_url: str | None = None   # API base (for openai-compatible providers)
    test_model: str | None = None # cheap model id for the live-limits probe
    options: dict = field(default_factory=dict)  # extra provider options

    def provider_config(self) -> dict:
        cfg = {"name": self.key, "type": self.type, "display_name": self.display_name}
        if self.scheme:
            cfg["scheme"] = self.scheme
        if self.base_url:
            cfg["base_url"] = self.base_url
        if self.test_model:
            cfg["test_model"] = self.test_model
        cfg.update(self.options)
        return cfg


def _openai_compatible(key, name, key_url, base_url, model, help):
    return Service(
        key=key, display_name=name, type="rate_limit", scheme="openai",
        key_url=key_url, base_url=base_url, test_model=model, help=help,
        options={"display": "ring", "primary": "tokens"},
    )


SERVICES: dict[str, Service] = {
    "claude": Service(
        key="claude", display_name="Claude", type="rate_limit", scheme="anthropic",
        key_url="https://console.anthropic.com/settings/keys",
        base_url="https://api.anthropic.com", test_model="claude-3-5-haiku-latest",
        help=("1. Open console.anthropic.com and sign in.\n"
              "2. Settings → API keys → Create Key.\n"
              "3. Copy the key (starts with sk-ant-) and paste it here.\n\n"
              "Note: developer API key — separate from Claude.ai Pro."),
        options={"display": "ring", "primary": "requests"},
    ),
    "openai": Service(
        key="openai", display_name="ChatGPT", type="rate_limit", scheme="openai",
        key_url="https://platform.openai.com/api-keys",
        base_url="https://api.openai.com/v1", test_model="gpt-4o-mini",
        help=("1. Open platform.openai.com and sign in.\n"
              "2. API keys → Create new secret key.\n"
              "3. Copy the key (starts with sk-) and paste it here.\n\n"
              "Note: the developer API is billed separately from ChatGPT Plus."),
        options={"display": "ring", "primary": "tokens"},
    ),
    "gemini": Service(
        key="gemini", display_name="Gemini", type="gemini", scheme=None,
        key_url="https://aistudio.google.com/app/apikey",
        help=("1. Open aistudio.google.com and sign in.\n"
              "2. Get API key → Create API key.\n"
              "3. Copy it and paste it here.\n\n"
              "Note: Google exposes no live limits, so Gemini shows usage you report."),
        options={"display": "bar", "budget": {"period": "monthly", "limit": 2000000}},
    ),
    "grok": _openai_compatible(
        "grok", "Grok", "https://console.x.ai", "https://api.x.ai/v1", "grok-2-latest",
        help=("1. Open console.x.ai and sign in with your X account.\n"
              "2. Click “API Keys” → “Create API Key”.\n"
              "3. Copy the key (starts with xai-) and paste it here.\n\n"
              "Requires an xAI API account with credit — separate from X Premium.")),
    "deepseek": _openai_compatible(
        "deepseek", "DeepSeek", "https://platform.deepseek.com/api_keys",
        "https://api.deepseek.com", "deepseek-chat",
        help=("1. Open platform.deepseek.com and sign in.\n"
              "2. Go to “API keys” → “Create new API key”.\n"
              "3. Copy the key (starts with sk-) and paste it here.")),
    "mistral": _openai_compatible(
        "mistral", "Mistral", "https://console.mistral.ai/api-keys",
        "https://api.mistral.ai/v1", "mistral-small-latest",
        help=("1. Open console.mistral.ai and sign in.\n"
              "2. Go to “API Keys” → “Create new key”.\n"
              "3. Copy the key and paste it here.")),
    "groq": _openai_compatible(
        "groq", "Groq", "https://console.groq.com/keys",
        "https://api.groq.com/openai/v1", "llama-3.1-8b-instant",
        help=("1. Open console.groq.com and sign in.\n"
              "2. Go to “API Keys” → “Create API Key”.\n"
              "3. Copy the key (starts with gsk_) and paste it here.")),
    "perplexity": _openai_compatible(
        "perplexity", "Perplexity", "https://www.perplexity.ai/settings/api",
        "https://api.perplexity.ai", "sonar",
        help=("1. Open perplexity.ai → Settings → “API”.\n"
              "2. Add a payment method, then “Generate” an API key.\n"
              "3. Copy the key (starts with pplx-) and paste it here.")),
    "openrouter": _openai_compatible(
        "openrouter", "OpenRouter", "https://openrouter.ai/keys",
        "https://openrouter.ai/api/v1", "openai/gpt-4o-mini",
        help=("1. Open openrouter.ai/keys and sign in.\n"
              "2. Click “Create Key”.\n"
              "3. Copy the key (starts with sk-or-) and paste it here.\n\n"
              "One key gives access to many models across providers.")),
    "together": _openai_compatible(
        "together", "Together AI", "https://api.together.xyz/settings/api-keys",
        "https://api.together.xyz/v1", "meta-llama/Llama-3.1-8B-Instruct-Turbo",
        help=("1. Open api.together.xyz and sign in.\n"
              "2. Go to Settings → “API Keys”.\n"
              "3. Copy your key and paste it here.")),
    "fireworks": _openai_compatible(
        "fireworks", "Fireworks AI", "https://fireworks.ai/account/api-keys",
        "https://api.fireworks.ai/inference/v1", "accounts/fireworks/models/llama-v3p1-8b-instruct",
        help=("1. Open fireworks.ai and sign in.\n"
              "2. Go to Account → “API Keys” → “Create API Key”.\n"
              "3. Copy the key and paste it here.")),
    "cohere": _openai_compatible(
        "cohere", "Cohere", "https://dashboard.cohere.com/api-keys",
        "https://api.cohere.ai/compatibility/v1", "command-r",
        help=("1. Open dashboard.cohere.com and sign in.\n"
              "2. Go to “API Keys” → create a Trial or Production key.\n"
              "3. Copy the key and paste it here.\n\n"
              "Note: Cohere's rate-limit headers are partial; some gauges may show no data.")),
}


def service_keys() -> list[str]:
    return list(SERVICES)


def get(key: str) -> Service | None:
    return SERVICES.get(key)


def provider_config_for(key: str) -> dict:
    svc = SERVICES.get(key)
    if svc is None:
        raise KeyError(f"unknown service {key!r}")
    return svc.provider_config()
