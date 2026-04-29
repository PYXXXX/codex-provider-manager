# Contributing

Thanks for helping improve `codex-provider-manager`.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

The codebase is intentionally small:

- `src/codex_provider_manager/config.py`: `config.toml` read/write helpers.
- `src/codex_provider_manager/providers.py`: provider operations.
- `src/codex_provider_manager/models.py`: `/v1/models` fetching and profile generation.
- `src/codex_provider_manager/sessions.py`: session scan, migration, and rollback.
- `src/codex_provider_manager/tui.py`: menu-based TUI.

## Safety Rules

- Never write API keys to `config.toml`.
- Never print full API keys.
- Never touch Codex auth files.
- Do not back up `~/.codex/sessions` unless the user explicitly asks.
- Session migration should only edit the first JSONL line's provider field.
- Preserve unknown TOML sections and existing user settings.
