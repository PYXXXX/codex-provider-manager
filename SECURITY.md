# Security Policy

`codex-provider-manager` works with local Codex configuration and session files, so safety is part of the project contract.

## Supported Versions

This project is currently in early alpha. Security fixes target the latest `main` branch until the first stable release.

## Reporting a Vulnerability

Please open a private security advisory on GitHub if available, or contact the maintainer privately before posting details publicly.

Do not include real API keys, Codex auth tokens, cookies, or private session contents in reports. Redact secrets and provide minimal reproduction data.

## Sensitive Data Rules

The project should never:

- Write API keys to `~/.codex/config.toml`.
- Print full API keys.
- Read or modify Codex auth token files.
- Upload local session contents anywhere.
- Back up the full sessions directory unless the user explicitly asks.

Session migration should only edit the provider field in the first JSONL line and preserve workspace (`cwd`), title, id, timestamp, model, and message history.
