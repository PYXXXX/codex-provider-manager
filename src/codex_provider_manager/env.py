from __future__ import annotations

import os
import platform
import subprocess

from .providers import list_providers
from .utils import mask_len


def check_env(doc) -> list[tuple[str, str]]:
    seen: set[str] = set()
    results: list[tuple[str, str]] = []
    for provider in list_providers(doc):
        if not provider.env_key or provider.env_key in seen:
            continue
        seen.add(provider.env_key)
        results.append((provider.env_key, mask_len(os.environ.get(provider.env_key))))
    return results


def set_env_var(name: str, value: str, *, persist: bool = False) -> str:
    os.environ[name] = value
    if not persist:
        return f"Set {name} for the current process only."
    if platform.system() == "Windows":
        subprocess.run(["setx", name, value], check=True, capture_output=True, text=True)
        return f"Persisted {name} for the Windows user environment. Reopen terminals to use it."
    escaped = value.replace("'", "'\"'\"'")
    return f"Add this to your shell profile:\nexport {name}='{escaped}'"
