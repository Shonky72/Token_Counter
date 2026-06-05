"""Catalog of AI services the user can add from the login window.

Each entry is everything needed to (a) populate the "add a service" dropdown,
(b) show an info ("i") popup explaining how to get the key, and (c) write a
provider block into the user's config. One key per service; all of that
service's models are tracked under it automatically.

Note: these track the *developer API* (your API key), not the consumer web/app
subscription — the apps expose no usage to outside tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Service:
    key: str                 # internal id + provider name in config
    display_name: str        # shown on the card
    type: str                # provider plugin type
    scheme: str | None       # rate-limit header scheme (rate_limit providers)
    key_url: str             # where to create an API key
    help: str                # short, friendly steps
    options: dict = field(default_factory=dict)  # extra provider options

    def provider_config(self) -> dict:
        cfg = {"name": self.key, "type": self.type, "display_name": self.display_name}
        if self.scheme:
            cfg["scheme"] = self.scheme
        cfg.update(self.options)
        return cfg


SERVICES: dict[str, Service] = {
    "claude": Service(
        key="claude",
        display_name="Claude",
        type="rate_limit",
        scheme="anthropic",
        key_url="https://console.anthropic.com/settings/keys",
        help=(
            "1. Open console.anthropic.com and sign in.\n"
            "2. Settings → API keys → Create Key.\n"
            "3. Copy the key (starts with sk-ant-) and paste it here.\n\n"
            "Note: this is your developer API key — separate from Claude.ai Pro."
        ),
        options={"display": "ring", "primary": "requests"},
    ),
    "openai": Service(
        key="openai",
        display_name="ChatGPT",
        type="rate_limit",
        scheme="openai",
        key_url="https://platform.openai.com/api-keys",
        help=(
            "1. Open platform.openai.com and sign in.\n"
            "2. API keys → Create new secret key.\n"
            "3. Copy the key (starts with sk-) and paste it here.\n\n"
            "Note: the developer API is billed separately from ChatGPT Plus."
        ),
        options={"display": "ring", "primary": "tokens"},
    ),
    "gemini": Service(
        key="gemini",
        display_name="Gemini",
        type="gemini",
        scheme=None,
        key_url="https://aistudio.google.com/app/apikey",
        help=(
            "1. Open aistudio.google.com and sign in.\n"
            "2. Get API key → Create API key.\n"
            "3. Copy it and paste it here.\n\n"
            "Note: Google exposes no live limits, so Gemini shows usage you report."
        ),
        options={"display": "bar", "budget": {"period": "monthly", "limit": 2000000}},
    ),
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
