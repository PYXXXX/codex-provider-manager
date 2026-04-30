from __future__ import annotations

import os
import platform
from pathlib import Path

import questionary
from questionary import Choice
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from .config import load_config, save_config, set_root_profile
from .env import check_env, set_env_var
from .i18n import tr
from .models import add_profile, fetch_models, import_models, list_profiles
from .providers import get_provider, list_providers, provider_to_dict, referencing_profiles, remove_provider, upsert_provider
from .sessions import (
    backup_session_files,
    delete_session_files,
    install_workspace_skill,
    migrate_selected_session_files,
    rollback_sessions,
    scan_sessions,
    scan_workspace_outputs,
    scan_workspace_skills,
    summarize_by_provider,
    summarize_outputs_by_category,
)
from .utils import env_key_for_provider_id


console = Console()


def _pause() -> None:
    questionary.press_any_key_to_continue(tr("按任意键继续", "Press any key to continue")).ask()


def _confirm(message: str, default: bool = False) -> bool:
    return bool(questionary.confirm(message, default=default).ask())


def _save_with_backup_choice(config_path: Path, doc) -> Path | None:
    create_backup = _confirm(tr("写入前是否创建 config.toml 备份？", "Create config.toml backup before writing?"), False)
    return save_config(config_path, doc, backup=create_backup)


def _backup_label(backup: Path | None) -> str:
    return str(backup) if backup else tr("未创建", "not created")


def _text(message: str, default: str = "") -> str | None:
    value = questionary.text(message, default=default).ask()
    return value.strip() if value is not None else None


def _set_provider_api_key(env_key: str) -> None:
    if not env_key:
        console.print(tr("[yellow]该 Provider 没有 env_key。[/yellow]", "[yellow]This provider has no env_key.[/yellow]"))
        return
    value = questionary.password(tr(f"输入 {env_key} 的 API key", f"API key for {env_key}")).ask()
    if not value:
        return
    persist_default = platform.system() == "Windows"
    persist = _confirm(
        tr(
            "是否保存到用户环境变量？Windows 上建议保存，保存后需要重启 Codex App。",
            "Persist to the user environment? Recommended on Windows; restart Codex App afterward.",
        ),
        persist_default,
    )
    console.print(set_env_var(env_key, value, persist=persist))


def _offer_set_provider_api_key(env_key: str) -> None:
    if env_key and _confirm(tr(f"是否现在设置 {env_key} 的 API key？", f"Set API key for {env_key} now?"), True):
        _set_provider_api_key(env_key)


def _choose_model_for_provider(doc, provider_id: str, env_key: str) -> str | None:
    result = fetch_models(doc, provider_id, api_key=os.environ.get(env_key))
    if result.ok and result.models:
        choices = [*result.models, tr("手动输入模型 ID", "Enter model ID manually"), tr("跳过", "Skip")]
        selected = questionary.select(tr("选择默认模型", "Select default model"), choices=choices).ask()
        if selected in (None, tr("跳过", "Skip")):
            return None
        if selected == tr("手动输入模型 ID", "Enter model ID manually"):
            return _text(tr("模型 ID", "Model ID"))
        return str(selected)
    console.print(tr(f"[yellow]读取模型列表失败：[/yellow] {result.error}", f"[yellow]Failed to fetch model list:[/yellow] {result.error}"))
    if _confirm(tr("是否手动输入模型 ID？", "Enter model ID manually?"), True):
        return _text(tr("模型 ID", "Model ID"))
    return None


def _finish_new_provider_setup(doc, provider_id: str, env_key: str) -> str | None:
    _offer_set_provider_api_key(env_key)
    model = _choose_model_for_provider(doc, provider_id, env_key)
    if not model:
        return None
    profile_name = add_profile(doc, profile_name=None, provider_id=provider_id, model=model, reasoning_effort="medium")
    if _confirm(
        tr(
            f"是否将 {profile_name} 设为当前使用的 Profile（默认 Provider：{provider_id}）？",
            f"Use {profile_name} as the current profile (default provider: {provider_id})?",
        ),
        True,
    ):
        set_root_profile(doc, profile_name)
    return profile_name


def _provider_table(doc) -> Table:
    table = Table(title=tr("Provider 列表", "Providers"))
    for column in ["ID", tr("名称", "Name"), "Base URL", tr("环境变量", "Env key"), "Wire API", "WebSocket"]:
        table.add_column(column)
    for provider in list_providers(doc):
        item = provider_to_dict(provider)
        table.add_row(
            item["id"],
            item["name"],
            item["base_url"],
            item["env_key"],
            item["wire_api"],
            item["supports_websockets"],
        )
    return table


def _provider_detail_table(doc, provider_id: str) -> Table:
    provider = get_provider(doc, provider_id)
    table = Table(title=tr(f"Provider：{provider_id}", f"Provider: {provider_id}"))
    table.add_column(tr("字段", "Field"))
    table.add_column(tr("值", "Value"))
    if not provider:
        table.add_row(tr("状态", "Status"), tr("未找到", "not found"))
        return table
    table.add_row("id", provider.id)
    table.add_row("name", provider.name)
    table.add_row("base_url", provider.base_url or "official auth")
    table.add_row("env_key", provider.env_key or "")
    table.add_row("wire_api", provider.wire_api or "")
    table.add_row("supports_websockets", "" if provider.supports_websockets is None else str(provider.supports_websockets).lower())
    table.add_row("builtin", str(provider.builtin).lower())
    refs = referencing_profiles(doc, provider_id)
    table.add_row(tr("引用它的 profiles", "Referencing profiles"), ", ".join(refs) if refs else tr("<无>", "<none>"))
    return table


def _profile_table(doc) -> Table:
    current = str(doc.get("profile", ""))
    table = Table(title=tr("Profile 列表", "Profiles"))
    table.add_column(tr("当前", "Current"))
    table.add_column("Profile")
    table.add_column(tr("模型", "Model"))
    table.add_column("Provider")
    for name, data in list_profiles(doc).items():
        table.add_row("*" if name == current else "", name, str(data.get("model", "")), str(data.get("model_provider", "")))
    return table


def _profile_detail_table(doc, profile_name: str) -> Table:
    profiles = list_profiles(doc)
    data = profiles.get(profile_name, {})
    table = Table(title=tr(f"Profile：{profile_name}", f"Profile: {profile_name}"))
    table.add_column(tr("字段", "Field"))
    table.add_column(tr("值", "Value"))
    if not data:
        table.add_row(tr("状态", "Status"), tr("未找到", "not found"))
        return table
    for key, value in data.items():
        table.add_row(str(key), str(value))
    return table


def _session_summary_table(sessions_dir: Path) -> Table:
    infos = scan_sessions(sessions_dir)
    table = Table(title=tr("Session Provider 汇总", "Sessions by Provider"))
    table.add_column("Provider")
    table.add_column(tr("Session 数", "Sessions"), justify="right")
    for provider, count in summarize_by_provider(infos).items():
        table.add_row(provider, str(count))
    if not infos:
        table.add_row(tr("<无>", "<none>"), "0")
    return table


def _session_detail_table(sessions_dir: Path, *, limit: int = 30) -> Table:
    infos = scan_sessions(sessions_dir)
    table = Table(title=tr(f"Session 文件（前 {limit} 个）", f"Session Files (first {limit})"))
    for column in ["Provider", tr("标题", "Title"), tr("模型", "Model"), tr("时间", "Time"), tr("工作区", "Workspace"), tr("路径", "Path")]:
        table.add_column(column)
    for info in infos[:limit]:
        table.add_row(info.model_provider or "", info.title or "", info.model or "", info.ts or "", info.cwd or "", str(info.path))
    if not infos:
        table.add_row("", "", "", "", "", "<none>")
    return table


def _env_table(doc) -> Table:
    table = Table(title=tr("环境变量", "Environment"))
    table.add_column(tr("环境变量", "Env key"))
    table.add_column(tr("状态", "Status"))
    rows = check_env(doc)
    if not rows:
        table.add_row(tr("<无>", "<none>"), tr("没有配置 provider env_key", "no provider env_key values configured"))
    for name, status in rows:
        table.add_row(name, status)
    return table


def _dashboard(config_path: Path, sessions_dir: Path) -> None:
    doc = load_config(config_path)
    current = str(doc.get("profile", "<none>"))
    profiles = list_profiles(doc)
    current_data = profiles.get(current, {})
    sessions = scan_sessions(sessions_dir)
    providers = list_providers(doc)
    body = "\n".join(
        [
            tr(f"配置文件：{config_path}", f"Config: {config_path}"),
            tr(f"Sessions：{sessions_dir}", f"Sessions: {sessions_dir}"),
            tr(f"当前 Profile：{current}", f"Current profile: {current}"),
            tr(f"模型：{current_data.get('model', '')}", f"Model: {current_data.get('model', '')}"),
            f"Provider：{current_data.get('model_provider', '')}",
            tr(f"Provider 数量：{len(providers)}", f"Providers: {len(providers)}"),
            tr(f"Profile 数量：{len(profiles)}", f"Profiles: {len(profiles)}"),
            tr(f"Session 文件数量：{len(sessions)}", f"Session files: {len(sessions)}"),
        ]
    )
    console.print(Rule("[bold cyan]Codex Provider Manager[/bold cyan]"))
    console.print(Panel(body, title=tr("当前状态", "Current State"), border_style="cyan"))


def _choose_provider(doc, *, include_openai: bool = True, message: str = "Provider") -> str | None:
    providers = [provider.id for provider in list_providers(doc) if include_openai or not provider.builtin]
    if not providers:
        console.print(tr("[yellow]没有可用 Provider。[/yellow]", "[yellow]No providers available.[/yellow]"))
        return None
    return questionary.select(message, choices=[*providers, tr("返回", "Back")]).ask()


def _normalize_choice(value: str | None) -> str | None:
    return None if value in (None, "Back", "Exit", "返回", "退出") else value


def _providers_menu(config_path: Path) -> None:
    while True:
        doc = load_config(config_path)
        console.clear()
        console.print(_provider_table(doc))
        view = tr("查看 Provider 详情", "View provider detail")
        add = tr("新增 Provider 向导", "Add provider wizard")
        edit = tr("编辑 Provider", "Edit provider")
        remove = tr("删除 Provider", "Remove provider")
        back = tr("返回", "Back")
        action = questionary.select(
            tr("Provider 管理", "Provider Management"),
            choices=[view, add, edit, remove, back],
        ).ask()
        if action in (None, back):
            return
        if action == view:
            provider_id = _normalize_choice(_choose_provider(doc))
            if provider_id:
                console.print(_provider_detail_table(doc, provider_id))
                _pause()
        elif action == add:
            provider_id = _text("Provider ID")
            name = _text(tr("显示名称", "Display name"), provider_id or "")
            base_url = _text("Base URL")
            env_key = env_key_for_provider_id(provider_id or "")
            console.print(tr(f"API key 将保存到环境变量：{env_key}", f"API key will be stored in env var: {env_key}"))
            supports = _confirm(tr("是否支持 WebSocket？", "Supports WebSocket?"), False)
            if provider_id and name and base_url and env_key:
                upsert_provider(doc, provider_id, name=name, base_url=base_url, env_key=env_key, supports_websockets=supports)
                profile_name = _finish_new_provider_setup(doc, provider_id, env_key)
                backup = _save_with_backup_choice(config_path, doc)
                console.print(tr(f"已保存 Provider {provider_id}。备份：{_backup_label(backup)}", f"Saved provider {provider_id}. Backup: {_backup_label(backup)}"))
                if profile_name:
                    console.print(tr(f"已创建 Profile：{profile_name}", f"Created profile: {profile_name}"))
                _pause()
        elif action == edit:
            provider_id = _normalize_choice(_choose_provider(doc, include_openai=False))
            provider = get_provider(doc, provider_id) if provider_id else None
            if provider:
                set_key = tr("设置 API Key（只写环境变量）", "Set API key (environment only)")
                fields = questionary.checkbox(
                    tr("选择要修改的字段", "Fields to edit"),
                    choices=[
                        f"name: {provider.name}",
                        f"base_url: {provider.base_url or ''}",
                        f"env_key: {provider.env_key or ''}",
                        f"supports_websockets: {str(bool(provider.supports_websockets)).lower()}",
                        set_key,
                        back,
                    ],
                ).ask() or []
                if not fields or back in fields:
                    continue
                name = provider.name
                base_url = provider.base_url or ""
                env_key = provider.env_key or ""
                supports = bool(provider.supports_websockets)
                if any(field.startswith("name:") for field in fields):
                    name = _text(tr("显示名称", "Display name"), name) or name
                if any(field.startswith("base_url:") for field in fields):
                    base_url = _text("Base URL", base_url) or base_url
                if any(field.startswith("env_key:") for field in fields):
                    env_key = _text(tr("环境变量名", "Environment variable name"), env_key) or env_key
                if any(field.startswith("supports_websockets:") for field in fields):
                    supports = _confirm(tr("是否支持 WebSocket？", "Supports WebSocket?"), supports)
                config_changed = any(
                    any(field.startswith(prefix) for field in fields)
                    for prefix in ("name:", "base_url:", "env_key:", "supports_websockets:")
                )
                if config_changed and name and base_url and env_key:
                    upsert_provider(doc, provider_id, name=name, base_url=base_url, env_key=env_key, supports_websockets=supports)
                    backup = _save_with_backup_choice(config_path, doc)
                    console.print(tr(f"已保存 Provider {provider_id}。备份：{_backup_label(backup)}", f"Saved provider {provider_id}. Backup: {_backup_label(backup)}"))
                if set_key in fields:
                    _set_provider_api_key(env_key)
                _pause()
        elif action == remove:
            provider_id = _normalize_choice(_choose_provider(doc, include_openai=False))
            if not provider_id:
                continue
            refs = referencing_profiles(doc, provider_id)
            if refs:
                console.print(tr(f"引用它的 Profiles：{', '.join(refs)}", f"Referencing profiles: {', '.join(refs)}"))
            if _confirm(tr(f"确认删除 Provider {provider_id}？", f"Remove provider {provider_id}?"), False):
                if refs and _confirm(tr("是否同时删除引用它的 Profiles？", "Delete referencing profiles too?"), False):
                    profiles = doc.get("profiles")
                    for name in refs:
                        del profiles[name]
                remove_provider(doc, provider_id)
                backup = _save_with_backup_choice(config_path, doc)
                console.print(tr(f"已删除 Provider {provider_id}。备份：{_backup_label(backup)}", f"Removed provider {provider_id}. Backup: {_backup_label(backup)}"))
                _pause()


def _profiles_menu(config_path: Path) -> None:
    while True:
        doc = load_config(config_path)
        console.clear()
        console.print(_profile_table(doc))
        view = tr("查看 Profile 详情", "View profile detail")
        switch = tr("切换 Profile", "Switch profile")
        add = tr("新增 Profile", "Add profile")
        remove = tr("删除 Profile", "Remove profile")
        back = tr("返回", "Back")
        action = questionary.select(tr("Profile 管理", "Profile Management"), choices=[view, switch, add, remove, back]).ask()
        if action in (None, back):
            return
        profiles = list_profiles(doc)
        if action == view:
            if not profiles:
                console.print(tr("[yellow]还没有配置 Profile。[/yellow]", "[yellow]No profiles configured.[/yellow]"))
                _pause()
                continue
            profile = _normalize_choice(questionary.select("Profile", choices=[*list(profiles.keys()), back]).ask())
            if profile:
                console.print(_profile_detail_table(doc, profile))
                _pause()
        elif action == switch:
            if not profiles:
                console.print(tr("[yellow]还没有配置 Profile。[/yellow]", "[yellow]No profiles configured.[/yellow]"))
                _pause()
                continue
            profile = _normalize_choice(questionary.select(tr("Profile", "Profile"), choices=[*list(profiles.keys()), back]).ask())
            if profile:
                set_root_profile(doc, profile)
                backup = _save_with_backup_choice(config_path, doc)
                console.print(tr(f"已切换到 {profile}。备份：{_backup_label(backup)}", f"Switched to {profile}. Backup: {_backup_label(backup)}"))
                _pause()
        elif action == add:
            provider_id = _normalize_choice(_choose_provider(doc))
            model = _text(tr("模型 ID", "Model ID"))
            name = _text(tr("Profile 名称（留空自动生成）", "Profile name (blank for auto)"))
            effort = _text(tr("推理强度", "Reasoning effort"), "medium") or "medium"
            if provider_id and model:
                created = add_profile(doc, profile_name=name or None, provider_id=provider_id, model=model, reasoning_effort=effort)
                backup = _save_with_backup_choice(config_path, doc)
                console.print(tr(f"已保存 Profile {created}。备份：{_backup_label(backup)}", f"Saved profile {created}. Backup: {_backup_label(backup)}"))
                _pause()
        elif action == remove:
            if not profiles:
                console.print(tr("[yellow]还没有配置 Profile。[/yellow]", "[yellow]No profiles configured.[/yellow]"))
                _pause()
                continue
            profile = _normalize_choice(questionary.select(tr("要删除的 Profile", "Profile to remove"), choices=[*list(profiles.keys()), back]).ask())
            if profile and _confirm(tr(f"确认删除 Profile {profile}？", f"Remove profile {profile}?"), False):
                del doc["profiles"][profile]
                if str(doc.get("profile", "")) == profile and profiles:
                    remaining = [name for name in profiles if name != profile]
                    if remaining and _confirm(tr(f"默认 Profile 是 {profile}。是否切换到 {remaining[0]}？", f"Current profile was {profile}. Switch to {remaining[0]}?"), True):
                        set_root_profile(doc, remaining[0])
                backup = _save_with_backup_choice(config_path, doc)
                console.print(tr(f"已删除 Profile {profile}。备份：{_backup_label(backup)}", f"Removed profile {profile}. Backup: {_backup_label(backup)}"))
                _pause()


def _models_menu(config_path: Path) -> None:
    while True:
        doc = load_config(config_path)
        console.clear()
        fetch_import = tr("导入", "Import")
        back = tr("返回", "Back")
        action = questionary.select(tr("模型管理", "Model Management"), choices=[fetch_import, back]).ask()
        if action in (None, back):
            return
        provider_id = _normalize_choice(_choose_provider(doc, message="Provider"))
        if not provider_id:
            continue
        provider = get_provider(doc, provider_id)
        api_key = os.environ.get(provider.env_key) if provider and provider.env_key else None
        result = fetch_models(doc, provider_id, api_key=api_key)
        if not result.ok:
            console.print(tr(f"[red]失败：[/red] {result.error}", f"[red]Failed:[/red] {result.error}"))
            _pause()
            continue
        choices = [Choice(title=model, value=model) for model in result.models]
        choices.append(Choice(title=back, value="__back__"))
        selected = questionary.checkbox(tr("模型", "Models"), choices=choices).ask() or []
        if "__back__" in selected:
            continue
        if selected:
            created = import_models(doc, provider_id, selected)
            backup = _save_with_backup_choice(config_path, doc)
            console.print(tr("已创建/更新 Profiles：", "Created/updated profiles:"))
            for name in created:
                console.print(f"- {name}")
            console.print(tr(f"备份：{_backup_label(backup)}", f"Backup: {_backup_label(backup)}"))
            _pause()


def _current_profile_provider(doc) -> str | None:
    current = str(doc.get("profile", ""))
    profile = list_profiles(doc).get(current)
    if not profile:
        return None
    provider = profile.get("model_provider")
    return str(provider) if provider else None


def _session_choice_title(info) -> str:
    return tr(
        f"{info.title or info.path.stem} | 当前 {info.model_provider} | 工作区 {info.cwd or '<无>'} | {info.ts or ''}",
        f"{info.title or info.path.stem} | current {info.model_provider} | workspace {info.cwd or '<none>'} | {info.ts or ''}",
    )


def _paths_not_on_provider(infos, provider_id: str) -> set[Path]:
    return {info.path for info in infos if not info.warning and info.model_provider and info.model_provider != provider_id}


def _workspace_output_table(workspace: Path) -> Table:
    outputs = scan_workspace_outputs(workspace)
    summary = summarize_outputs_by_category(outputs)
    title = tr(f"工作区产出：{workspace}", f"Workspace outputs: {workspace}")
    table = Table(title=title)
    table.add_column(tr("类型", "Type"))
    table.add_column(tr("数量", "Count"), justify="right")
    table.add_column(tr("示例", "Examples"))
    for category, count in summary.items():
        examples = [str(output.path.relative_to(workspace)) for output in outputs if output.category == category][:5]
        table.add_row(category, str(count), ", ".join(examples))
    if not summary:
        table.add_row(tr("<无>", "<none>"), "0", "")
    return table


def _workspace_skill_table(workspace: Path) -> Table:
    skills = scan_workspace_skills(workspace)
    table = Table(title=tr(f"工作区 Skills：{workspace}", f"Workspace skills: {workspace}"))
    table.add_column("Skill")
    table.add_column(tr("全局状态", "Global status"))
    table.add_column(tr("路径", "Path"))
    for skill in skills:
        table.add_row(skill.name, tr("已安装", "installed") if skill.installed else tr("未安装", "not installed"), str(skill.path))
    if not skills:
        table.add_row(tr("<无>", "<none>"), "", "")
    return table


def _install_missing_workspace_skills(workspaces: list[Path]) -> None:
    missing = []
    seen: set[Path] = set()
    for workspace in workspaces:
        for skill in scan_workspace_skills(workspace):
            if not skill.installed and skill.path not in seen:
                missing.append(skill)
                seen.add(skill.path)
    if not missing:
        return
    choices = [
        Choice(
            title=f"{skill.name} -> {skill.global_path}",
            value=skill,
            checked=True,
        )
        for skill in missing
    ]
    selected = questionary.checkbox(tr("选择要安装到全局的 Skill", "Select skills to install globally"), choices=choices).ask() or []
    for skill in selected:
        target = install_workspace_skill(skill)
        console.print(tr(f"已安装 Skill：{skill.name} -> {target}", f"Installed skill: {skill.name} -> {target}"))


def _run_session_delete_flow(sessions_dir: Path, infos) -> None:
    valid_infos = [info for info in infos if not info.warning]
    if not valid_infos:
        console.print(tr("[yellow]没有可删除的 Session。[/yellow]", "[yellow]No deletable sessions found.[/yellow]"))
        _pause()
        return
    back = tr("返回", "Back")
    choices = [
        Choice(title=_session_choice_title(info), value=info.path)
        for info in valid_infos
    ]
    choices.append(Choice(title=back, value="__back__"))
    selected_paths = set(questionary.checkbox(tr("选择要删除的 Session", "Select sessions to delete"), choices=choices).ask() or [])
    if "__back__" in selected_paths:
        return
    if not selected_paths:
        console.print(tr("[yellow]没有选择任何 Session。[/yellow]", "[yellow]No sessions selected.[/yellow]"))
        _pause()
        return

    selected_infos = [info for info in valid_infos if info.path in selected_paths]
    preview = Table(title=tr("删除预览（仅删除 Session 文件）", "Delete preview (session files only)"))
    preview.add_column(tr("标题", "Title"))
    preview.add_column("Provider")
    preview.add_column(tr("工作区", "Workspace"))
    preview.add_column(tr("Session 文件", "Session file"))
    for info in selected_infos:
        preview.add_row(info.title or info.path.stem, info.model_provider or "", info.cwd or "", str(info.path))
    console.print(preview)

    workspaces = []
    seen_workspaces: set[Path] = set()
    for info in selected_infos:
        if not info.cwd:
            continue
        workspace = Path(info.cwd).expanduser()
        if workspace not in seen_workspaces:
            workspaces.append(workspace)
            seen_workspaces.add(workspace)
    for workspace in workspaces:
        console.print(_workspace_output_table(workspace))
        console.print(_workspace_skill_table(workspace))
    _install_missing_workspace_skills(workspaces)

    backup_dir = None
    if _confirm(tr("删除前是否备份选中的 Session 文件？", "Back up selected session files before deleting?"), False):
        backup_dir = backup_session_files(sessions_dir, selected_paths)
        if backup_dir:
            console.print(tr(f"备份目录：{backup_dir}", f"Backup directory: {backup_dir}"))
    if not _confirm(tr(f"确认删除 {len(selected_paths)} 个 Session 文件？工作区文件不会被删除。", f"Delete {len(selected_paths)} session files? Workspace files will not be deleted."), False):
        return
    result = delete_session_files(selected_paths)
    console.print(tr(f"已删除 {result.deleted} 个；跳过 {result.skipped} 个。", f"Deleted {result.deleted}; skipped {result.skipped}."))
    for warning in result.warnings:
        console.print(tr(f"[yellow]警告：[/yellow] {warning}", f"[yellow]Warning:[/yellow] {warning}"))
    _pause()


def _run_session_migration_flow(
    sessions_dir: Path,
    valid_infos,
    target_providers: list[str],
    *,
    preset_target: str | None = None,
    preselected_paths: set[Path] | None = None,
) -> None:
    back = tr("返回", "Back")
    preselected_paths = preselected_paths or set()
    session_choices = [
        Choice(
            title=_session_choice_title(info),
            value=info.path,
            checked=info.path in preselected_paths,
        )
        for info in valid_infos
    ]
    session_choices.append(Choice(title=back, value="__back__"))
    selected_paths = set(questionary.checkbox(tr("选择要迁移的 Session", "Select sessions to migrate"), choices=session_choices).ask() or [])
    if "__back__" in selected_paths:
        return
    if not selected_paths:
        console.print(tr("[yellow]没有选择任何 Session。[/yellow]", "[yellow]No sessions selected.[/yellow]"))
        _pause()
        return
    target = preset_target
    if not target:
        target = _normalize_choice(questionary.select(tr("目标 Provider", "Target provider"), choices=[*target_providers, back]).ask())
    if not target:
        return
    selected_infos = [info for info in valid_infos if info.path in selected_paths]
    preview = Table(title=tr("迁移预览", "Migration Preview"))
    preview.add_column(tr("序号", "No."))
    preview.add_column(tr("从", "From"))
    preview.add_column(tr("到", "To"))
    preview.add_column(tr("标题", "Title"))
    preview.add_column(tr("工作区", "Workspace"))
    preview.add_column(tr("模型", "Model"))
    preview.add_column(tr("路径", "Path"))
    for index, info in enumerate(selected_infos, start=1):
        preview.add_row(str(index), info.model_provider or "", target, info.title or "", info.cwd or "", info.model or "", str(info.path))
    console.print(preview)
    dry = tr("仅预览（不写入）", "Dry run (no write)")
    formal = tr("正式迁移", "Migrate")
    mode = questionary.select(tr("执行方式", "Action"), choices=[dry, formal, back]).ask()
    if mode in (None, back):
        return
    dry_run = mode == dry
    backup_sessions = False
    if not dry_run:
        backup_sessions = _confirm(tr("是否创建完整 sessions 目录备份？", "Create full sessions directory backup?"), False)
    if dry_run or _confirm(tr(f"确认修改 {len(selected_paths)} 个选中的 Session 文件？", f"Modify {len(selected_paths)} selected session files?"), False):
        result = migrate_selected_session_files(sessions_dir, selected_paths, target, dry_run=dry_run, backup=backup_sessions)
        console.print(tr(f"{'将会修改' if dry_run else '已修改'} {result.changed} 个；跳过 {result.skipped} 个。", f"{'Would modify' if dry_run else 'Modified'} {result.changed}; skipped {result.skipped}."))
        if result.undo_path:
            console.print(tr(f"Undo 文件：{result.undo_path}", f"Undo file: {result.undo_path}"))
        if result.backup_path:
            console.print(tr(f"备份目录：{result.backup_path}", f"Backup directory: {result.backup_path}"))
        for warning in result.warnings:
            console.print(tr(f"[yellow]警告：[/yellow] {warning}", f"[yellow]Warning:[/yellow] {warning}"))
        _pause()


def _sessions_menu(config_path: Path, sessions_dir: Path) -> None:
    while True:
        doc = load_config(config_path)
        infos = scan_sessions(sessions_dir)
        providers = sorted(provider for provider in summarize_by_provider(infos) if provider != "<unknown>")
        target_providers = sorted(set(providers) | {provider.id for provider in list_providers(doc)})
        console.clear()
        console.print(_session_summary_table(sessions_dir))
        view = tr("查看 Session 文件", "View session files")
        migrate = tr("迁移选中的 Session", "Migrate selected sessions")
        migrate_current = tr("迁移到当前 Provider", "Migrate to current provider")
        delete = tr("删除 Session", "Delete sessions")
        rollback = tr("从 undo JSON 回滚", "Rollback from undo JSON")
        back = tr("返回", "Back")
        action = questionary.select(tr("Session 管理", "Session Management"), choices=[view, migrate, migrate_current, delete, rollback, back]).ask()
        if action in (None, back):
            return
        if action == view:
            console.print(_session_detail_table(sessions_dir))
            _pause()
        elif action == migrate:
            valid_infos = [info for info in infos if not info.warning and info.model_provider]
            if not valid_infos:
                console.print(tr("[yellow]没有可迁移的 Session。[/yellow]", "[yellow]No migratable sessions found.[/yellow]"))
                _pause()
                continue
            _run_session_migration_flow(sessions_dir, valid_infos, target_providers)
        elif action == migrate_current:
            current_provider = _current_profile_provider(doc)
            if not current_provider:
                console.print(tr("[yellow]当前 Profile 没有对应的 Provider。[/yellow]", "[yellow]Current profile has no provider.[/yellow]"))
                _pause()
                continue
            valid_infos = [info for info in infos if not info.warning and info.model_provider]
            preselected = _paths_not_on_provider(valid_infos, current_provider)
            if not preselected:
                console.print(tr(f"[green]所有 Session 已经属于当前 Provider：{current_provider}。[/green]", f"[green]All sessions already belong to current provider: {current_provider}.[/green]"))
                _pause()
                continue
            console.print(tr(f"当前 Provider：{current_provider}。已自动勾选不属于它的 Session。", f"Current provider: {current_provider}. Sessions not using it are preselected."))
            _run_session_migration_flow(sessions_dir, valid_infos, target_providers, preset_target=current_provider, preselected_paths=preselected)
        elif action == delete:
            _run_session_delete_flow(sessions_dir, infos)
        elif action == rollback:
            undo = _text(tr("Undo JSON 路径", "Undo JSON path"))
            if undo:
                dry_run = _confirm(tr("是否仅预览（不写入）？", "Dry run only?"), True)
                result = rollback_sessions(Path(undo).expanduser(), dry_run=dry_run)
                console.print(tr(f"{'将会恢复' if dry_run else '已恢复'} {result.changed} 个；跳过 {result.skipped} 个。", f"{'Would restore' if dry_run else 'Restored'} {result.changed}; skipped {result.skipped}."))
                _pause()


def _env_menu(config_path: Path) -> None:
    console.clear()
    doc = load_config(config_path)
    console.print(_env_table(doc))
    _pause()


def run_tui(config_path: Path, sessions_dir: Path) -> int:
    while True:
        console.clear()
        _dashboard(config_path, sessions_dir)
        providers = tr("Provider 管理", "Provider Management")
        profiles = tr("Profile 管理", "Profile Management")
        models = tr("模型管理", "Model Management")
        sessions = tr("Session 管理", "Session Management")
        env = tr("环境变量检查", "Environment Check")
        quit_item = tr("退出", "Quit")
        action = questionary.select(
            tr("主菜单", "Main Menu"),
            choices=[
                providers,
                profiles,
                models,
                sessions,
                env,
                quit_item,
            ],
        ).ask()
        if action in (None, quit_item):
            return 0
        if action == providers:
            _providers_menu(config_path)
        elif action == profiles:
            _profiles_menu(config_path)
        elif action == models:
            _models_menu(config_path)
        elif action == sessions:
            _sessions_menu(config_path, sessions_dir)
        elif action == env:
            _env_menu(config_path)
