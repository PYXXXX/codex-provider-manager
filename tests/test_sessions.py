import json
from pathlib import Path

from codex_provider_manager.sessions import migrate_selected_session_files, migrate_sessions, rollback_sessions, scan_sessions, summarize_by_provider


def _session(path: Path, provider: str, model: str = "gpt-5.4") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "id": path.stem,
                "model": model,
                "model_provider": provider,
                "cwd": "D:\\Agent\\demo",
                "timestamp": "2026-04-29T12:00:00Z",
            },
            separators=(",", ":"),
        )
        + "\n"
        + json.dumps({"type": "message", "content": "keep me"}) + "\n",
        encoding="utf-8",
    )


def _nested_session(path: Path, provider: str, model: str = "gpt-5.4") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "timestamp": "2026-04-29T12:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": path.stem,
                    "model": model,
                    "model_provider": provider,
                    "cwd": "D:\\Agent\\demo",
                    "timestamp": "2026-04-29T12:00:00Z",
                },
            },
            separators=(",", ":"),
        )
        + "\n"
        + json.dumps({"type": "message", "content": "keep me"}) + "\n",
        encoding="utf-8",
    )


def _titled_session(path: Path, provider: str, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "timestamp": "2026-04-29T12:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": path.stem,
                    "model_provider": provider,
                    "cwd": "D:\\Agent\\demo",
                    "timestamp": "2026-04-29T12:00:00Z",
                },
            },
            separators=(",", ":"),
        )
        + "\n"
        + json.dumps({"type": "event_msg", "payload": {"type": "thread_name_updated", "thread_name": title}}) + "\n",
        encoding="utf-8",
    )


def _context_then_titled_session(path: Path, provider: str, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": path.stem, "model_provider": provider}}, separators=(",", ":"))
        + "\n"
        + json.dumps({"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<environment_context>noise</environment_context>"}]}})
        + "\n"
        + json.dumps({"type": "event_msg", "payload": {"type": "thread_name_updated", "thread_name": title}})
        + "\n",
        encoding="utf-8",
    )


def test_scan_sessions_summarizes_provider_counts(tmp_path: Path) -> None:
    sessions = tmp_path / ".codex" / "sessions"
    _session(sessions / "2026" / "04" / "29" / "a.jsonl", "huaibao")
    _session(sessions / "2026" / "04" / "29" / "b.jsonl", "huaibao")
    _session(sessions / "2026" / "04" / "29" / "c.jsonl", "codexlb")

    summary = summarize_by_provider(scan_sessions(sessions))
    assert summary == {"codexlb": 1, "huaibao": 2}


def test_scan_sessions_reads_nested_payload_provider(tmp_path: Path) -> None:
    sessions = tmp_path / ".codex" / "sessions"
    _nested_session(sessions / "2026" / "04" / "29" / "a.jsonl", "huaibao")

    infos = scan_sessions(sessions)
    assert infos[0].model_provider == "huaibao"
    assert infos[0].model == "gpt-5.4"
    assert infos[0].cwd == "D:\\Agent\\demo"


def test_scan_sessions_extracts_title_from_thread_name_event(tmp_path: Path) -> None:
    sessions = tmp_path / ".codex" / "sessions"
    _titled_session(sessions / "2026" / "04" / "29" / "a.jsonl", "huaibao", "Provider migration work")

    infos = scan_sessions(sessions)
    assert infos[0].title == "Provider migration work"


def test_scan_sessions_prefers_thread_name_over_context_messages(tmp_path: Path) -> None:
    sessions = tmp_path / ".codex" / "sessions"
    _context_then_titled_session(sessions / "2026" / "04" / "29" / "a.jsonl", "huaibao", "Actual title")

    infos = scan_sessions(sessions)
    assert infos[0].title == "Actual title"


def test_migrate_sessions_dry_run_does_not_modify(tmp_path: Path) -> None:
    sessions = tmp_path / ".codex" / "sessions"
    file_path = sessions / "2026" / "04" / "29" / "a.jsonl"
    _session(file_path, "huaibao")
    before = file_path.read_text(encoding="utf-8")

    result = migrate_sessions(sessions, {"huaibao"}, "codexlb", dry_run=True)

    assert result.changed == 1
    assert result.undo_path is None
    assert file_path.read_text(encoding="utf-8") == before


def test_migrate_only_changes_first_line_provider_and_rollback_restores(tmp_path: Path) -> None:
    sessions = tmp_path / ".codex" / "sessions"
    file_path = sessions / "2026" / "04" / "29" / "a.jsonl"
    _session(file_path, "huaibao")

    result = migrate_sessions(sessions, {"huaibao"}, "codexlb")
    assert result.changed == 1
    assert result.undo_path is not None
    assert result.backup_path is None
    assert not list((tmp_path / ".codex").glob("sessions.backup-*"))

    lines = file_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    assert first["model_provider"] == "codexlb"
    assert first["model"] == "gpt-5.4"
    assert json.loads(lines[1]) == {"type": "message", "content": "keep me"}

    rollback = rollback_sessions(result.undo_path)
    assert rollback.changed == 1
    restored = json.loads(file_path.read_text(encoding="utf-8").splitlines()[0])
    assert restored["model_provider"] == "huaibao"


def test_migrate_sessions_backup_is_opt_in(tmp_path: Path) -> None:
    sessions = tmp_path / ".codex" / "sessions"
    file_path = sessions / "2026" / "04" / "29" / "a.jsonl"
    _session(file_path, "huaibao")

    result = migrate_sessions(sessions, {"huaibao"}, "codexlb", backup=True)
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert (result.backup_path / "2026" / "04" / "29" / "a.jsonl").exists()


def test_migrate_sessions_updates_nested_payload_provider(tmp_path: Path) -> None:
    sessions = tmp_path / ".codex" / "sessions"
    file_path = sessions / "2026" / "04" / "29" / "a.jsonl"
    _nested_session(file_path, "huaibao")

    result = migrate_sessions(sessions, {"huaibao"}, "codexlb")
    assert result.changed == 1

    lines = file_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    assert first["payload"]["model_provider"] == "codexlb"
    assert "model_provider" not in {key for key in first if key != "payload"}
    assert first["payload"]["model"] == "gpt-5.4"

    rollback_sessions(result.undo_path)
    restored = json.loads(file_path.read_text(encoding="utf-8").splitlines()[0])
    assert restored["payload"]["model_provider"] == "huaibao"


def test_migrate_sessions_can_limit_to_selected_paths(tmp_path: Path) -> None:
    sessions = tmp_path / ".codex" / "sessions"
    selected = sessions / "2026" / "04" / "29" / "a.jsonl"
    unselected = sessions / "2026" / "04" / "29" / "b.jsonl"
    _nested_session(selected, "huaibao")
    _nested_session(unselected, "huaibao")

    result = migrate_sessions(sessions, {"huaibao"}, "codexlb", selected_paths={selected})
    assert result.changed == 1

    selected_first = json.loads(selected.read_text(encoding="utf-8").splitlines()[0])
    unselected_first = json.loads(unselected.read_text(encoding="utf-8").splitlines()[0])
    assert selected_first["payload"]["model_provider"] == "codexlb"
    assert unselected_first["payload"]["model_provider"] == "huaibao"


def test_migrate_selected_session_files_updates_only_chosen_files(tmp_path: Path) -> None:
    sessions = tmp_path / ".codex" / "sessions"
    chosen = sessions / "2026" / "04" / "29" / "chosen.jsonl"
    other = sessions / "2026" / "04" / "29" / "other.jsonl"
    _nested_session(chosen, "huaibao")
    _nested_session(other, "onetoken")

    result = migrate_selected_session_files(sessions, {chosen}, "codexlb")

    assert result.changed == 1
    assert result.undo_path is not None
    chosen_first = json.loads(chosen.read_text(encoding="utf-8").splitlines()[0])
    other_first = json.loads(other.read_text(encoding="utf-8").splitlines()[0])
    assert chosen_first["payload"]["model_provider"] == "codexlb"
    assert chosen_first["payload"]["cwd"] == "D:\\Agent\\demo"
    assert other_first["payload"]["model_provider"] == "onetoken"
