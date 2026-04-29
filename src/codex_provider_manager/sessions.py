from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .backup import backup_sessions_dir, timestamp


@dataclass
class SessionInfo:
    path: Path
    session_id: str | None
    title: str | None
    model: str | None
    model_provider: str | None
    cwd: str | None
    ts: str | None
    warning: str | None = None


@dataclass
class MigrationResult:
    changed: int
    skipped: int
    undo_path: Path | None
    backup_path: Path | None
    warnings: list[str]


def _read_first_payload(path: Path) -> tuple[dict | None, str | None, list[str] | None]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return None, "not valid UTF-8", None
    if not lines:
        return None, "empty file", lines
    try:
        payload = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        return None, f"first line is not JSON: {exc}", lines
    if not isinstance(payload, dict):
        return None, "first line JSON is not an object", lines
    return payload, None, lines


def _load_json_line(line: str) -> dict | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _extract(payload: dict, *keys: str) -> str | None:
    candidates = [payload]
    nested_payload = payload.get("payload")
    if isinstance(nested_payload, dict):
        candidates.insert(0, nested_payload)
    for candidate in candidates:
        for key in keys:
            value = candidate.get(key)
            if isinstance(value, str):
                return value
    return None


def _get_provider(payload: dict) -> str | None:
    return _extract(payload, "model_provider", "provider")


def _stringify_content(content) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(parts) if parts else None
    return None


def _clean_title(value: str | None, *, limit: int = 60) -> str | None:
    if not value:
        return None
    title = " ".join(value.split())
    if not title:
        return None
    return title if len(title) <= limit else f"{title[: limit - 1]}..."


def _looks_like_context(value: str) -> bool:
    stripped = value.lstrip()
    prefixes = (
        "<environment_context",
        "<permissions",
        "<app-context",
        "<collaboration_mode",
        "<skills_instructions",
        "<plugins_instructions",
        "<developer",
        "# Codex desktop context",
    )
    return any(stripped.startswith(prefix) for prefix in prefixes)


def _extract_thread_name(payload: dict) -> str | None:
    nested_payload = payload.get("payload")
    candidates = [nested_payload, payload] if isinstance(nested_payload, dict) else [payload]
    for candidate in candidates:
        for key in ("thread_name", "title", "name"):
            value = candidate.get(key)
            if isinstance(value, str):
                return _clean_title(value)
    return None


def _extract_user_title(payload: dict) -> str | None:
    nested_payload = payload.get("payload")
    candidates = [nested_payload, payload] if isinstance(nested_payload, dict) else [payload]
    for candidate in candidates:
        message = candidate.get("message")
        if isinstance(message, str):
            return None if _looks_like_context(message) else _clean_title(message)
        if isinstance(message, dict):
            title = _stringify_content(message.get("content"))
            if title and not _looks_like_context(title):
                return _clean_title(title)
        content = _stringify_content(candidate.get("content"))
        if content and not _looks_like_context(content):
            return _clean_title(content)
    return None


def _extract_session_title(path: Path, first_payload: dict | None, *, max_lines: int = 80) -> str | None:
    payloads: list[dict] = []
    if first_payload:
        payloads.append(first_payload)
    try:
        with path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index >= max_lines:
                    break
                payload = _load_json_line(line)
                if payload:
                    payloads.append(payload)
    except UnicodeDecodeError:
        return None
    for payload in payloads:
        title = _extract_thread_name(payload)
        if title:
            return title
    for payload in payloads:
        title = _extract_user_title(payload)
        if title:
            return title
    return None


def _set_provider(payload: dict, provider: str) -> str:
    nested_payload = payload.get("payload")
    if isinstance(nested_payload, dict):
        if "model_provider" in nested_payload:
            old = str(nested_payload.get("model_provider", ""))
            nested_payload["model_provider"] = provider
            return old
        if "provider" in nested_payload:
            old = str(nested_payload.get("provider", ""))
            nested_payload["provider"] = provider
            return old
    if "model_provider" in payload:
        old = str(payload.get("model_provider", ""))
        payload["model_provider"] = provider
        return old
    if "provider" in payload:
        old = str(payload.get("provider", ""))
        payload["provider"] = provider
        return old
    if isinstance(nested_payload, dict):
        nested_payload["model_provider"] = provider
    else:
        payload["model_provider"] = provider
    return ""


def scan_sessions(sessions_dir: Path) -> list[SessionInfo]:
    if not sessions_dir.exists():
        return []
    infos: list[SessionInfo] = []
    for path in sorted(sessions_dir.rglob("*.jsonl")):
        payload, warning, _ = _read_first_payload(path)
        if payload is None:
            infos.append(SessionInfo(path, None, None, None, None, None, None, warning))
            continue
        infos.append(
            SessionInfo(
                path=path,
                session_id=_extract(payload, "id", "session_id"),
                title=_extract_session_title(path, payload),
                model=_extract(payload, "model"),
                model_provider=_get_provider(payload),
                cwd=_extract(payload, "cwd"),
                ts=_extract(payload, "timestamp", "ts", "created_at"),
            )
        )
    return infos


def summarize_by_provider(infos: list[SessionInfo]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for info in infos:
        key = info.model_provider or "<unknown>"
        summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def preview_migration(infos: list[SessionInfo], sources: set[str]) -> list[SessionInfo]:
    return [info for info in infos if info.model_provider in sources]


def migrate_sessions(
    sessions_dir: Path,
    sources: set[str],
    target: str,
    *,
    dry_run: bool = False,
    backup: bool = False,
    selected_paths: set[Path] | None = None,
) -> MigrationResult:
    infos = scan_sessions(sessions_dir)
    candidates = preview_migration(infos, sources)
    if selected_paths is not None:
        resolved = {path.resolve() for path in selected_paths}
        candidates = [info for info in candidates if info.path.resolve() in resolved]
    candidate_paths = {info.path.resolve() for info in candidates}
    warnings: list[str] = [f"{info.path}: {info.warning}" for info in infos if info.warning]
    if dry_run:
        return MigrationResult(changed=len(candidates), skipped=len(infos) - len(candidates), undo_path=None, backup_path=None, warnings=warnings)

    backup_path = backup_sessions_dir(sessions_dir) if backup and sessions_dir.exists() else None
    changes: list[dict[str, str]] = []
    skipped = 0
    for info in infos:
        if info.model_provider not in sources or info.path.resolve() not in candidate_paths:
            skipped += 1
            continue
        payload, warning, lines = _read_first_payload(info.path)
        if payload is None or lines is None:
            skipped += 1
            warnings.append(f"{info.path}: {warning}")
            continue
        old_provider = _set_provider(payload, target)
        lines[0] = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ("\n" if lines[0].endswith("\n") else "")
        info.path.write_text("".join(lines), encoding="utf-8")
        changes.append({"path": str(info.path), "old_provider": old_provider, "new_provider": target})

    undo_path = None
    if changes:
        undo_path = sessions_dir.parent / f"session-migration-undo-{timestamp()}.json"
        undo_payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "target_provider": target,
            "changes": changes,
        }
        undo_path.write_text(json.dumps(undo_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return MigrationResult(changed=len(changes), skipped=skipped, undo_path=undo_path, backup_path=backup_path, warnings=warnings)


def migrate_selected_session_files(
    sessions_dir: Path,
    paths: list[Path] | set[Path],
    target: str,
    *,
    dry_run: bool = False,
    backup: bool = False,
) -> MigrationResult:
    selected = [Path(path) for path in paths]
    warnings: list[str] = []
    if dry_run:
        skipped = 0
        for path in selected:
            payload, warning, _ = _read_first_payload(path)
            if payload is None:
                skipped += 1
                warnings.append(f"{path}: {warning}")
        return MigrationResult(changed=len(selected) - skipped, skipped=skipped, undo_path=None, backup_path=None, warnings=warnings)

    backup_path = backup_sessions_dir(sessions_dir) if backup and sessions_dir.exists() else None
    changes: list[dict[str, str]] = []
    skipped = 0
    for path in selected:
        payload, warning, lines = _read_first_payload(path)
        if payload is None or lines is None:
            skipped += 1
            warnings.append(f"{path}: {warning}")
            continue
        old_provider = _set_provider(payload, target)
        lines[0] = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ("\n" if lines[0].endswith("\n") else "")
        path.write_text("".join(lines), encoding="utf-8")
        changes.append({"path": str(path), "old_provider": old_provider, "new_provider": target})

    undo_path = None
    if changes:
        undo_path = sessions_dir.parent / f"session-migration-undo-{timestamp()}.json"
        undo_payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "target_provider": target,
            "changes": changes,
        }
        undo_path.write_text(json.dumps(undo_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return MigrationResult(changed=len(changes), skipped=skipped, undo_path=undo_path, backup_path=backup_path, warnings=warnings)


def rollback_sessions(undo_path: Path, *, dry_run: bool = False) -> MigrationResult:
    payload = json.loads(undo_path.read_text(encoding="utf-8"))
    changes = payload.get("changes", [])
    changed = 0
    skipped = 0
    warnings: list[str] = []
    for change in changes:
        path = Path(change["path"])
        old_provider = change["old_provider"]
        new_provider = change["new_provider"]
        first_payload, warning, lines = _read_first_payload(path)
        if first_payload is None or lines is None:
            skipped += 1
            warnings.append(f"{path}: {warning}")
            continue
        if _get_provider(first_payload) != new_provider:
            skipped += 1
            warnings.append(f"{path}: current provider is not {new_provider}, skipped")
            continue
        if not dry_run:
            _set_provider(first_payload, old_provider)
            lines[0] = json.dumps(first_payload, ensure_ascii=False, separators=(",", ":")) + ("\n" if lines[0].endswith("\n") else "")
            path.write_text("".join(lines), encoding="utf-8")
        changed += 1
    return MigrationResult(changed=changed, skipped=skipped, undo_path=undo_path, backup_path=None, warnings=warnings)


def copy_sessions_for_tests(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
