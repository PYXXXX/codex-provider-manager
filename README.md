# codex-provider-manager

[![CI](https://github.com/PYXXXX/codex-provider-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/PYXXXX/codex-provider-manager/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[中文说明](README.zh-CN.md)

`codex-provider-manager` is a cross-platform CLI/TUI assistant for managing the Codex user configuration used by OpenAI Codex CLI, Codex App, and IDE extensions.

It focuses on the practical parts that Codex users need when switching between the built-in OpenAI provider and OpenAI-compatible third-party providers:

- provider definitions in `~/.codex/config.toml`
- profiles and the active profile
- model profile import from `/v1/models`
- API-key environment variable checks
- local session provider visibility and safe session migration

This is an independent community tool and is not affiliated with OpenAI.

## Safety Model

- API keys are never written to `config.toml`.
- API keys are never printed.
- Codex auth files are not read or modified.
- Unknown TOML sections are preserved.
- `config.toml` backups are opt-in.
- Full `sessions` directory backups are opt-in.
- Session migration edits only the provider field in the first JSONL line.
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

Current Codex session files usually store provider ownership in the first line under:

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
The scripts automatically refresh the local editable install when source files change, so pulling a newer version and running the script is enough.

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

Main areas:

- Provider management
- Profile management
- Model management
- Session management
- Environment checks

The session migration flow loads sessions first, lets you select the exact sessions to migrate, then asks for the target provider and confirmation. There is also a "migrate to current provider" action that preselects sessions whose first-line provider differs from the active profile's provider, while still letting you uncheck any session before writing.

## Provider Commands

```bash
cpm list-providers
cpm add-provider --id codex-lb --name codex-lb --base-url https://aiapi.bilirec.com/v1
cpm add-provider --id codex-lb --name codex-lb --base-url https://aiapi.bilirec.com/v1 --prompt-api-key --persist-api-key
cpm edit-provider codex-lb
cpm remove-provider codex-lb
```

The built-in official provider is always shown as `openai`, but the tool does not write `[model_providers.openai]` because Codex owns that provider.
When adding a third-party provider in the TUI, the flow automatically creates an env var name from the provider id, asks only for the real API key, fetches `/v1/models`, creates a profile for the selected model, and can set it as the current profile. The key is written only to the environment, never to `config.toml`.

## Model Import

For third-party OpenAI-compatible providers, model import reads:

```text
GET {base_url}/models
Authorization: Bearer <API key from env_key>
```

Then it creates Codex profiles such as:

```toml
[profiles.codexlb_gpt_5_4]
model = "gpt-5.4"
model_provider = "codexlb"
model_reasoning_effort = "medium"
```

Example:

```bash
set CODEX_LB_API_KEY=...
cpm fetch-models codexlb
cpm import-models codexlb
```

For official OpenAI/ChatGPT auth, create profiles with `model_provider = "openai"`. Whether a model is actually usable depends on your Codex auth subscription and permissions.

## Profile Commands

```bash
cpm list-profiles
cpm add-profile --provider openai --model gpt-5.5 --name official_gpt_5_5
cpm switch-profile official_gpt_5_5
```

`switch-profile` updates the root `profile = "..."` key and keeps it before TOML tables.

## Session Commands

```bash
cpm scan-sessions --verbose
cpm migrate-sessions huaibao codexlb --dry-run
cpm migrate-sessions huaibao,onetoken codexlb
cpm rollback-sessions --undo ~/.codex/session-migration-undo-YYYYMMDD-HHMMSS.json
```

Migration changes only the first-line provider field. It does not change the model, session id, timestamp, workspace/cwd, title, or later messages.

Formal migration writes a lightweight undo JSON. A full sessions backup is created only when you pass `--backup` or choose it in the TUI.

## Environment Commands

```bash
cpm check-env
cpm set-env --provider codexlb
cpm check-official-auth
```

On Windows, persistent env setup uses `setx` when requested. On macOS/Linux, the tool sets the key for the current process and tells you which variable to persist manually without printing the secret.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

The test suite covers TOML preservation, provider/profile writes, `/v1/models` import, session scanning, migration, rollback, and opt-in backups.

## Known Limits

- This tool manages Codex config and local session metadata; it does not modify Codex authentication state.
- `/v1/models` import requires the provider to expose an OpenAI-compatible models endpoint.
- The TUI is intentionally simple and terminal-native for reliability.
- Official model availability is not guaranteed by profile creation; Codex auth decides access.

## Security

Please see [SECURITY.md](SECURITY.md). Do not post API keys, auth tokens, cookies, or private session contents in public issues.

## Roadmap

- Richer TUI layout with search and filters.
- Safer bulk editing previews for large session sets.
- Optional packaged releases for Windows/macOS.
- More provider-specific diagnostics without exposing secrets.
