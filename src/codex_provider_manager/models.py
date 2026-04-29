from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import requests

from .config import nested_table, table_items
from .providers import get_provider
from .utils import OFFICIAL_MODELS, profile_name_for


@dataclass
class FetchResult:
    ok: bool
    models: list[str]
    error: str | None = None


def fetch_models(doc, provider_id: str, *, api_key: str | None = None, timeout: int = 20) -> FetchResult:
    if provider_id == "openai":
        return FetchResult(ok=True, models=OFFICIAL_MODELS)
    provider = get_provider(doc, provider_id)
    if provider is None:
        return FetchResult(ok=False, models=[], error=f"provider {provider_id!r} not found")
    if not provider.base_url:
        return FetchResult(ok=False, models=[], error=f"provider {provider_id!r} has no base_url")
    if not provider.env_key:
        return FetchResult(ok=False, models=[], error=f"provider {provider_id!r} has no env_key")
    if not api_key:
        return FetchResult(ok=False, models=[], error=f"environment variable {provider.env_key} is missing")

    url = f"{provider.base_url.rstrip('/')}/models"
    try:
        response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout)
    except requests.RequestException as exc:
        return FetchResult(ok=False, models=[], error=f"request failed: {exc}")
    if response.status_code >= 400:
        summary = response.text[:300].replace("\n", " ")
        return FetchResult(ok=False, models=[], error=f"HTTP {response.status_code}: {summary}")
    try:
        payload = response.json()
    except ValueError:
        return FetchResult(ok=False, models=[], error="response was not valid JSON")
    data = payload.get("data")
    if not isinstance(data, list):
        return FetchResult(ok=False, models=[], error="response JSON did not contain a data list")
    models = sorted({str(item["id"]) for item in data if isinstance(item, dict) and item.get("id")})
    return FetchResult(ok=True, models=models)


def list_profiles(doc) -> dict[str, dict]:
    return table_items(doc, "profiles")


def add_profile(
    doc,
    *,
    profile_name: str | None,
    provider_id: str,
    model: str,
    reasoning_effort: str = "medium",
) -> str:
    name = profile_name or profile_name_for(provider_id if provider_id != "openai" else "official", model)
    profile = nested_table(doc, "profiles", name)
    profile["model"] = model
    profile["model_provider"] = provider_id
    if reasoning_effort:
        profile["model_reasoning_effort"] = reasoning_effort
    return name


def import_models(doc, provider_id: str, models: Iterable[str], *, reasoning_effort: str = "medium") -> list[str]:
    created: list[str] = []
    profile_provider_id = "official" if provider_id == "openai" else provider_id
    for model in models:
        name = profile_name_for(profile_provider_id, model)
        add_profile(doc, profile_name=name, provider_id=provider_id, model=model, reasoning_effort=reasoning_effort)
        created.append(name)
    return created
