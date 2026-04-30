# Changelog

## 0.1.0

- Add provider and profile management for Codex user config.
- Add OpenAI-compatible `/v1/models` import into Codex profiles.
- Add TUI with automatic Chinese/English language selection.
- Add session provider scan, selected-session migration, undo JSON, and rollback.
- Keep session `cwd`/workspace, title, id, timestamp, model, and message history unchanged during migration.
- Make config and session directory backups opt-in.
- Allow setting provider API keys from provider add/edit flows without writing secrets to `config.toml`.
- Guide new provider setup through model selection, profile creation, and optional current-profile switching.
- Generate provider API-key environment variable names automatically during provider creation.
- Add TUI session deletion with workspace output review and workspace skill installation support.
