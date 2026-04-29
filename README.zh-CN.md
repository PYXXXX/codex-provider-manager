# codex-provider-manager

[![CI](https://github.com/PYXXXX/codex-provider-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/PYXXXX/codex-provider-manager/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English README](README.md)

`codex-provider-manager` 是一个跨平台 CLI/TUI 辅助工具，用来管理 OpenAI Codex CLI、Codex App 和 IDE Extension 共用的 Codex 用户配置。

它主要解决这些实际问题：

- 管理 `~/.codex/config.toml` 里的 provider
- 管理 profile 和当前使用的 profile
- 从第三方 OpenAI-compatible provider 的 `/v1/models` 导入模型并生成 profile
- 检查 API key 对应的系统环境变量
- 扫描本地 session 的 provider 归属，并安全迁移 session 可见性

这是独立社区工具，不隶属于 OpenAI。

## 安全原则

- 不把 API key 写入 `config.toml`。
- 不打印 API key。
- 不读取或修改 Codex auth 文件。
- 保留未知 TOML section。
- `config.toml` 备份由用户明确选择，不默认创建。
- `sessions` 目录完整备份由用户明确选择，不默认创建。
- session 迁移只修改 JSONL 第一行里的 provider 字段。
- session 的 `cwd`/工作区、标题、id、timestamp、model 和后续消息都保持不变。

## 会修改哪些文件

Codex 配置：

```text
~/.codex/config.toml
```

Codex sessions：

```text
~/.codex/sessions/**/*.jsonl
```

当前 Codex session 文件通常在第一行这样记录 provider 归属：

```json
{"payload":{"model_provider":"codexlb"}}
```

旧结构或简化测试文件里的顶层 `model_provider` 也兼容。

## 快速运行

Windows PowerShell：

```powershell
.\scripts\run.ps1
.\scripts\run.ps1 doctor
```

macOS/Linux：

```bash
chmod +x scripts/run.sh
./scripts/run.sh
./scripts/run.sh doctor
```

脚本不带参数时会打开 TUI；带参数时会透传给 CLI。

## 安装

```bash
python -m pip install -e ".[dev]"
```

然后运行：

```bash
cpm tui
cpm doctor
```

## TUI

```bash
cpm tui
```

TUI 会根据系统语言自动切换：系统 locale 以 `zh` 开头时显示中文，否则显示英文。

主要入口：

- Provider 管理
- Profile 管理
- 模型管理
- Session 管理
- 环境变量检查

TUI 中迁移 session 的流程是：先加载 session 列表，勾选具体要迁移的 session，再选择目标 provider，确认后执行。

## Provider 命令

```bash
cpm list-providers
cpm add-provider --id codexlb --name codex-lb --base-url https://aiapi.bilirec.com/v1 --env-key CODEX_LB_API_KEY
cpm edit-provider codexlb
cpm remove-provider codexlb
```

内置官方 provider 会始终显示为 `openai`，但工具不会写入 `[model_providers.openai]`，因为这个 provider 由 Codex 自己负责。

## 模型导入是怎么工作的

第三方 provider 的模型导入会读取配置里的 `base_url` 和 `env_key`，然后从系统环境变量读取 API key，请求：

```text
GET {base_url}/models
Authorization: Bearer <API key from env_key>
```

返回 OpenAI-compatible 模型列表后，工具会为选中的模型创建 Codex profile，例如：

```toml
[profiles.codexlb_gpt_5_4]
model = "gpt-5.4"
model_provider = "codexlb"
model_reasoning_effort = "medium"
```

示例：

```bash
set CODEX_LB_API_KEY=...
cpm fetch-models codexlb
cpm import-models codexlb
```

官方 OpenAI/ChatGPT auth 模式使用 `model_provider = "openai"`。创建 profile 只代表写入配置，模型是否真的可用由 Codex auth、订阅和权限决定。

## Profile 命令

```bash
cpm list-profiles
cpm add-profile --provider openai --model gpt-5.5 --name official_gpt_5_5
cpm switch-profile official_gpt_5_5
```

`switch-profile` 会更新根部的 `profile = "..."`，并保证它位于所有 TOML table 前面。

## Session 命令

```bash
cpm scan-sessions --verbose
cpm migrate-sessions huaibao codexlb --dry-run
cpm migrate-sessions huaibao,onetoken codexlb
cpm rollback-sessions --undo ~/.codex/session-migration-undo-YYYYMMDD-HHMMSS.json
```

迁移只修改第一行 provider 字段。不会修改 model、session id、timestamp、工作区/cwd、标题或后续消息。

正式迁移会生成轻量 undo JSON。只有传入 `--backup` 或在 TUI 中明确选择时，才会创建完整 sessions 备份。

## 环境变量命令

```bash
cpm check-env
cpm set-env --provider codexlb
cpm check-official-auth
```

Windows 持久化设置在用户明确选择时使用 `setx`。macOS/Linux 默认只输出 `export` 命令，不自动修改 shell 启动文件。

## 开发

```bash
python -m pip install -e ".[dev]"
pytest
```

测试覆盖 TOML 保留、provider/profile 写入、`/v1/models` 导入、session 扫描、迁移、回滚和可选备份。

## 已知限制

- 本工具管理 Codex 配置和本地 session 元数据，不修改 Codex 登录状态。
- `/v1/models` 导入要求 provider 支持 OpenAI-compatible models 接口。
- TUI 暂时保持终端原生和轻量，以可靠性优先。
- official profile 的模型权限不由本工具决定，最终由 Codex auth 决定。

## 安全报告

请查看 [SECURITY.md](SECURITY.md)。不要在公开 issue 中粘贴 API key、auth token、cookie 或私密 session 内容。

## 后续方向

- 更强的 TUI 搜索和筛选。
- 大批量 session 迁移的更细预览。
- Windows/macOS 打包发布。
- 更多 provider 诊断能力，同时继续避免泄露密钥。
