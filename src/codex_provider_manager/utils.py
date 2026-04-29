from __future__ import annotations

import re
from pathlib import Path


BUILTIN_PROVIDER_IDS = {"openai", "ollama", "lmstudio"}
OFFICIAL_MODELS = [
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.3-codex",
    "gpt-5.3-codex-spark",
    "gpt-5.2-codex",
]


def codex_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".codex"


def config_path(home: Path | None = None) -> Path:
    return codex_dir(home) / "config.toml"


def sessions_path(home: Path | None = None) -> Path:
    return codex_dir(home) / "sessions"


def validate_provider_id(provider_id: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_-]+", provider_id))


def env_key_for_provider_id(provider_id: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_", provider_id).strip("_").upper()
    if not stem:
        stem = "PROVIDER"
    return f"{stem}_API_KEY"


def profile_name_for(provider_id: str, model: str) -> str:
    raw = f"{provider_id}_{model}"
    return re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_").lower()


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def mask_len(value: str | None) -> str:
    if value is None:
        return "missing"
    return f"exists, length {len(value)}"
