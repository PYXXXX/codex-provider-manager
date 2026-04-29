# codex-provider-manager

[![CI](https://github.com/PYXXXX/codex-provider-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/PYXXXX/codex-provider-manager/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[中文说明](README.zh-CN.md)

`codex-provider-manager` is a cross-platform CLI/TUI for managing the Codex user configuration used by OpenAI Codex CLI, Codex App, and IDE extensions.

It helps manage:

- Codex model providers
- Profiles and the active profile
- OpenAI-compatible model lists from `/v1/models`
- Environment variable health checks
- Local session provider visibility and safe session migration

The tool is designed for Windows and macOS/Linux and uses `pathlib` for path handling.

This is an independent community tool and is not affiliated with OpenAI.

## Safety Model

- API keys are never written to `config.toml`.
- API keys are never printed.
- Codex auth files are not read or modified.
- Unknown TOML sections are preserved.
- Config backups are opt-in.
- Full session directory backups are opt-in.
- Session migration edits only the first JSONL line's provider field.
- Session `cwd`/workspace, title, id, timestamp, model, and later messages are preserved.

## What It Edits

Codex config:

```text
~/.codex/config.toml
```

Codex sessions:

```text
~/.codex/sessions/**/*.jsonl
```

Current Codex session files usually store provider ownership at:

```json
{"payload":{"model_provider":"codexlb"}}
```

Older or simplified files with a top-level `model_provider` are also supported.

## Quick Start

Windows PowerShell:

```powershell
.\scripts\run.ps1
.\scripts\run.ps1 doctor
```

macOS/Linux:

```bash
chmod +x scripts/run.sh
./scripts/run.sh
./scripts/run.sh doctor
```

Running the script with no arguments opens the TUI. Arguments are passed through to the CLI.

## Install

```bash
python -m pip install -e ".[dev]"
```

Then run:

```bash
cpm tui
cpm doctor
```

## TUI

```bash
cpm tui
```

The TUI automatically uses Chinese when the system locale starts with `zh`; otherwise it uses English.

The TUI includes:

- Provider management
- Profile management
- Model management
- Session management
- Environment checks

Session migration in the TUI works by loading the session list first. You select the exact sessions to migrate, choose the target provider, review the preview, then choose dry-run or formal migration.

## Provider Commands

List providers:

```bash
cpm providers
```

Add a provider:

```bash
cpm add-provider \
  --id codexlb \
  --name codex-lb \
  --base-url https://aiapi.bilirec.com/v1 \
  --env-key CODEX_LB_API_KEY
```

Create a config backup explicitly:

```bash
cpm add-provider \
  --id codexlb \
  --name codex-lb \
  --base-url https://aiapi.bilirec.com/v1 \
  --env-key CODEX_LB_API_KEY \
  --backup
```

Edit or remove:

```bash
cpm edit-provider codexlb --base-url https://aiapi.bilirec.com/v1
cpm remove-provider codexlb
```

Built-in provider IDs such as `openai`, `ollama`, and `lmstudio` cannot be overwritten or removed.

## Model Import

Fetch models:

```bash
cpm models codexlb
```

Import selected models as profiles:

```bash
cpm import-models codexlb --models gpt-5.4,gpt-5.5
```

How model import works:

1. Read the provider's `base_url` and `env_key` from `config.toml`.
2. Read the real API key from the environment variable named by `env_key`.
3. Request `GET {base_url}/models` with `Authorization: Bearer <API_KEY>`.
4. Parse OpenAI-compatible responses such as `{"object":"list","data":[{"id":"gpt-5.4"}]}`.
5. Write selected model IDs as Codex profiles, such as `codexlb_gpt_5_4`.

The API key is not written to `config.toml` and is not printed.

## Profile Commands

```bash
cpm profiles
cpm add-profile --provider codexlb --model gpt-5.4
cpm switch codexlb_gpt_5_4
```

Official OpenAI profiles use Codex's built-in `openai` provider and depend on `codex login`:

```toml
[profiles.official_gpt_5_5]
model = "gpt-5.5"
model_provider = "openai"
```

## Session Commands

Scan sessions:

```bash
cpm sessions
cpm scan-sessions --verbose
```

Dry-run migration:

```bash
cpm migrate huaibao codexlb --dry-run
```

Formal migration:

```bash
cpm migrate huaibao codexlb -y
```

Full session directory backup is opt-in:

```bash
cpm migrate huaibao codexlb --backup -y
```

Rollback:

```bash
cpm rollback --undo ~/.codex/session-migration-undo-YYYYMMDD-HHMMSS.json
```

Formal migration always creates a lightweight undo JSON. It records only changed files and old/new providers.

## Environment Commands

```bash
cpm check-env
cpm set-env --provider codexlb
```

`check-env` prints only existence and length. `set-env --persist` uses `setx` on Windows. On macOS/Linux it prints an `export` command instead of modifying shell startup files.

## Official Auth Check

```bash
cpm check-official-auth
```

This may run `codex /status` or `codex --version`. It does not read or modify Codex auth tokens.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

Windows script smoke test:

```powershell
.\scripts\run.ps1 doctor
```

macOS/Linux script smoke test:

```bash
./scripts/run.sh doctor
```

## Status

This project is an early alpha. The CLI and menu-based TUI are intentionally conservative and safety-focused.

## Security

Please see [SECURITY.md](SECURITY.md). Do not post API keys, auth tokens, cookies, or private session contents in public issues.
