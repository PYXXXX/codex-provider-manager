from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.items import Table

from .backup import backup_file
from .utils import config_path, sessions_path


@dataclass
class CodexPaths:
    config: Path
    sessions: Path


def default_paths(home: Path | None = None) -> CodexPaths:
    return CodexPaths(config=config_path(home), sessions=sessions_path(home))


def load_config(path: Path) -> tomlkit.TOMLDocument:
    if not path.exists():
        return tomlkit.document()
    return tomlkit.parse(path.read_text(encoding="utf-8"))


def save_config(path: Path, doc: tomlkit.TOMLDocument, *, dry_run: bool = False, backup: bool = False) -> Path | None:
    if dry_run:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = backup_file(path) if backup and path.exists() else None
    text = tomlkit.dumps(ensure_root_profile_first(doc))
    path.write_text(text, encoding="utf-8")
    return backup_path


def ensure_root_profile_first(doc: tomlkit.TOMLDocument) -> tomlkit.TOMLDocument:
    if "profile" not in doc:
        return doc
    profile = doc["profile"]
    rebuilt = tomlkit.document()
    rebuilt.add("profile", profile)
    for key, value in doc.items():
        if key != "profile":
            rebuilt.add(key, value)
    return rebuilt


def get_table(doc: tomlkit.TOMLDocument, key: str) -> Table:
    if key not in doc:
        doc[key] = tomlkit.table()
    value = doc[key]
    if not isinstance(value, Table):
        raise ValueError(f"config key [{key}] is not a table")
    return value


def nested_table(doc: tomlkit.TOMLDocument, root: str, name: str) -> Table:
    root_table = get_table(doc, root)
    if name not in root_table:
        root_table[name] = tomlkit.table()
    value = root_table[name]
    if not isinstance(value, Table):
        raise ValueError(f"config key [{root}.{name}] is not a table")
    return value


def table_items(doc: tomlkit.TOMLDocument, root: str) -> dict[str, dict[str, Any]]:
    table = doc.get(root)
    if not isinstance(table, Table):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, value in table.items():
        if isinstance(value, Table):
            result[str(key)] = dict(value.items())
    return result


def set_root_profile(doc: tomlkit.TOMLDocument, profile_name: str) -> None:
    doc["profile"] = profile_name
