# codex-provider-manager

[![CI](https://github.com/PYXXXX/codex-provider-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/PYXXXX/codex-provider-manager/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English README](README.md)

`codex-provider-manager` 是一个跨平台 CLI/TUI 工具，用来管理 OpenAI Codex CLI、Codex App 和 IDE Extension 共用的 Codex 用户配置。

它主要用于管理：

- Codex model providers
- profiles 和当前 profile
- 第三方 OpenAI-compatible provider 的 `/v1/models` 模型列表
- 环境变量健康检查
- 本地 session 的 provider 可见性和安全迁移

工具面向 Windows 和 macOS/Linux，路径处理使用 `pathlib`。

这是一个独立社区工具，不隶属于 OpenAI。

## 安全原则

- 不把 API key 写入 `config.toml`。
- 不打印 API key。
- 不读取或修改 Codex auth 文件。
- 保留未知 TOML section。
- config 备份由用户明确选择，不默认创建。
- sessions 目录完整备份由用户明确选择，不默认创建。
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

TUI 包含：

- Provider 管理
- Profile 管理
- 模型管理
- Session 管理
- 环境变量检查

TUI 中迁移 session 的流程是：先加载 session 列表，用户勾选具体要迁移的 session，再选择目标 provider，检查预览，然后选择仅预览或正式迁移。

## Provider 命令

查看 provider：

```bash
cpm providers
```

新增 provider：

```bash
cpm add-provider \
  --id codexlb \
  --name codex-lb \
  --base-url https://aiapi.bilirec.com/v1 \
  --env-key CODEX_LB_API_KEY
```

显式创建 config 备份：

```bash
cpm add-provider \
  --id codexlb \
  --name codex-lb \
  --base-url https://aiapi.bilirec.com/v1 \
  --env-key CODEX_LB_API_KEY \
  --backup
```

编辑或删除：

```bash
cpm edit-provider codexlb --base-url https://aiapi.bilirec.com/v1
cpm remove-provider codexlb
```

`openai`、`ollama`、`lmstudio` 等内置 provider id 不能覆盖或删除。

## 模型导入

拉取模型：

```bash
cpm models codexlb
```

把模型导入为 profiles：

```bash
cpm import-models codexlb --models gpt-5.4,gpt-5.5
```

模型导入的工作方式：

1. 从 `config.toml` 读取 provider 的 `base_url` 和 `env_key`。
2. 从 `env_key` 指向的系统环境变量读取真实 API key。
3. 请求 `GET {base_url}/models`，请求头带 `Authorization: Bearer <API_KEY>`。
4. 解析 OpenAI-compatible 返回格式，例如 `{"object":"list","data":[{"id":"gpt-5.4"}]}`。
5. 把选中的模型 ID 写成 Codex profiles，例如 `codexlb_gpt_5_4`。

API key 不会写入 `config.toml`，也不会打印出来。

## Profile 命令

```bash
cpm profiles
cpm add-profile --provider codexlb --model gpt-5.4
cpm switch codexlb_gpt_5_4
```

官方 OpenAI profiles 使用 Codex 内置的 `openai` provider，是否可用取决于 `codex login` 和账号权限：

```toml
[profiles.official_gpt_5_5]
model = "gpt-5.5"
model_provider = "openai"
```

## Session 命令

扫描 sessions：

```bash
cpm sessions
cpm scan-sessions --verbose
```

预览迁移：

```bash
cpm migrate huaibao codexlb --dry-run
```

正式迁移：

```bash
cpm migrate huaibao codexlb -y
```

完整 sessions 目录备份需要显式选择：

```bash
cpm migrate huaibao codexlb --backup -y
```

回滚：

```bash
cpm rollback --undo ~/.codex/session-migration-undo-YYYYMMDD-HHMMSS.json
```

正式迁移会默认创建轻量 undo JSON，只记录被修改文件和新旧 provider。

## 环境变量命令

```bash
cpm check-env
cpm set-env --provider codexlb
```

`check-env` 只显示是否存在和长度，不显示密钥。`set-env --persist` 在 Windows 上使用 `setx`；macOS/Linux 默认只输出 `export` 命令，不主动修改 shell 启动文件。

## 官方登录检查

```bash
cpm check-official-auth
```

该命令可能运行 `codex /status` 或 `codex --version`，不会读取或修改 Codex auth token。

## 开发

```bash
python -m pip install -e ".[dev]"
pytest
```

Windows 脚本测试：

```powershell
.\scripts\run.ps1 doctor
```

macOS/Linux 脚本测试：

```bash
./scripts/run.sh doctor
```

## 状态

项目目前是早期 alpha。CLI 和菜单式 TUI 都以保守、安全、可回滚为优先。

## 安全报告

请查看 [SECURITY.md](SECURITY.md)。不要在公开 issue 中粘贴 API key、auth token、cookie 或私密 session 内容。
