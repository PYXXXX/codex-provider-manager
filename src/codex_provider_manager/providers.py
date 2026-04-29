from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import nested_table, table_items
from .utils import BUILTIN_PROVIDER_IDS, validate_provider_id


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    base_url: str | None = None
    env_key: str | None = None
    wire_api: str | None = None
    supports_websockets: bool | None = None
    builtin: bool = False


OFFICIAL_PROVIDER = Provider(
    id="openai",
    name="Official OpenAI / ChatGPT auth",
    builtin=True,
)

def list_providers(doc) -> list[Provider]:
    providers = [OFFICIAL_PROVIDER]
    for provider_id, data in table_items(doc, "model_providers").items():
        if provider_id == "openai":
            continue
        providers.append(
            Provider(
                id=provider_id,
                name=str(data.get("name", provider_id)),
                base_url=str(data["base_url"]) if "base_url" in data else None,
                env_key=str(data["env_key"]) if "env_key" in data else None,
                wire_api=str(data["wire_api"]) if "wire_api" in data else None,
                supports_websockets=bool(data["supports_websockets"]) if "supports_websockets" in data else None,
            )
        )
    return providers


def get_provider(doc, provider_id: str) -> Provider | None:
    for provider in list_providers(doc):
        if provider.id == provider_id:
            return provider
    return None


def upsert_provider(
    doc,
    provider_id: str,
    *,
    name: str,
    base_url: str,
    env_key: str,
    supports_websockets: bool = False,
    wire_api: str = "responses",
    allow_builtin: bool = False,
) -> None:
    if not validate_provider_id(provider_id):
        raise ValueError("provider id may only contain letters, numbers, underscores, and hyphens")
    if provider_id in BUILTIN_PROVIDER_IDS and not allow_builtin:
        raise ValueError(f"{provider_id!r} is a built-in provider id and cannot be overwritten")
    if env_key and ("sk-" in env_key or env_key.count(".") >= 2):
        raise ValueError("env_key must be an environment variable name, not an API key")
    table = nested_table(doc, "model_providers", provider_id)
    table["name"] = name
    table["base_url"] = base_url.rstrip("/")
    table["env_key"] = env_key
    table["wire_api"] = wire_api
    table["supports_websockets"] = supports_websockets


def remove_provider(doc, provider_id: str) -> None:
    if provider_id in BUILTIN_PROVIDER_IDS:
        raise ValueError(f"{provider_id!r} is built in and cannot be removed")
    providers = doc.get("model_providers")
    if providers and provider_id in providers:
        del providers[provider_id]


def referencing_profiles(doc, provider_id: str) -> list[str]:
    refs: list[str] = []
    for name, data in table_items(doc, "profiles").items():
        if data.get("model_provider") == provider_id:
            refs.append(name)
    return refs


def provider_to_dict(provider: Provider) -> dict[str, Any]:
    return {
        "id": provider.id,
        "name": provider.name,
        "base_url": provider.base_url or "official auth",
        "env_key": provider.env_key or "",
        "wire_api": provider.wire_api or "",
        "supports_websockets": "" if provider.supports_websockets is None else str(provider.supports_websockets).lower(),
    }
