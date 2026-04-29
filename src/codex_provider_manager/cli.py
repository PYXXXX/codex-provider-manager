from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
from pathlib import Path

import questionary
from rich.console import Console
from rich.table import Table

from .config import default_paths, load_config, save_config, set_root_profile
from .env import check_env, set_env_var
from .models import add_profile, fetch_models, import_models, list_profiles
from .providers import get_provider, list_providers, provider_to_dict, referencing_profiles, remove_provider, upsert_provider
from .sessions import migrate_sessions, preview_migration, rollback_sessions, scan_sessions, summarize_by_provider
from .tui import run_tui
from .utils import OFFICIAL_MODELS, split_csv

console = Console()


def _paths(args) -> tuple[Path, Path]:
    home = Path(args.home).expanduser() if getattr(args, "home", None) else None
    paths = default_paths(home)
    return paths.config, paths.sessions


def _load(args):
    config, sessions = _paths(args)
    return config, sessions, load_config(config)


def _ask(text: str, default: str | None = None) -> str:
    value = questionary.text(text, default=default or "").ask()
    if value is None:
        raise SystemExit(1)
    return value.strip()


def _confirm(text: str, default: bool = False) -> bool:
    value = questionary.confirm(text, default=default).ask()
    return bool(value)


def _set_api_key_for_env_key(env_key: str, *, value: str | None = None, persist: bool | None = None, ask_persist: bool = True) -> None:
    api_key = value or questionary.password(f"API key for {env_key}").ask()
    if not api_key:
        return
    should_persist = persist
    if should_persist is None and ask_persist:
        should_persist = _confirm(
            "Persist to the user environment? Recommended on Windows; restart Codex App afterward.",
            platform.system() == "Windows",
        )
    if should_persist is None:
        should_persist = False
    console.print(set_env_var(env_key, api_key, persist=should_persist))


def _print_provider_table(providers) -> None:
    table = Table(title="Codex Providers")
    for column in ["id", "name", "base_url", "env_key", "wire_api", "supports_websockets"]:
        table.add_column(column)
    for provider in providers:
        item = provider_to_dict(provider)
        table.add_row(*(item[column] for column in ["id", "name", "base_url", "env_key", "wire_api", "supports_websockets"]))
    console.print(table)


def _can_create_or_write(path: Path) -> bool:
    if path.exists():
        return os.access(path, os.W_OK)
    parent = path.parent
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    return parent.exists() and os.access(parent, os.W_OK)


def doctor(args) -> int:
    config, sessions, _ = _load(args)
    table = Table(title="Doctor")
    table.add_column("check")
    table.add_column("status")
    table.add_row("config path", str(config))
    table.add_row("config exists", "yes" if config.exists() else "no")
    table.add_row("config readable", "yes" if config.exists() and os.access(config, os.R_OK) else ("n/a" if not config.exists() else "no"))
    table.add_row("config writable", "yes" if _can_create_or_write(config) else "no")
    table.add_row("sessions path", str(sessions))
    table.add_row("sessions exists", "yes" if sessions.exists() else "no")
    console.print(table)
    return 0


def cmd_list_providers(args) -> int:
    _, _, doc = _load(args)
    _print_provider_table(list_providers(doc))
    return 0


def cmd_add_provider(args) -> int:
    config, _, doc = _load(args)
    interactive = not all([args.id, args.name, args.base_url, args.env_key])
    provider_id = args.id or _ask("Provider id")
    exists = get_provider(doc, provider_id) is not None and provider_id != "openai"
    if exists and not (args.yes or _confirm(f"Provider {provider_id} exists. Update it?", False)):
        return 1
    name = args.name or _ask("Display name", provider_id)
    base_url = args.base_url or _ask("Base URL")
    env_key = args.env_key or _ask("Environment variable name")
    upsert_provider(doc, provider_id, name=name, base_url=base_url, env_key=env_key, supports_websockets=args.supports_websockets)
    backup = save_config(config, doc, dry_run=args.dry_run, backup=args.backup)
    console.print(f"{'Would update' if args.dry_run else 'Updated'} provider [bold]{provider_id}[/bold].")
    if backup:
        console.print(f"Config backup: {backup}")
    should_prompt_key = args.prompt_api_key or args.api_key or (interactive and not args.dry_run and _confirm(f"Set API key for {env_key} now?", True))
    if should_prompt_key and not args.dry_run:
        _set_api_key_for_env_key(env_key, value=args.api_key, persist=args.persist_api_key, ask_persist=args.api_key is None)
    return 0


def cmd_edit_provider(args) -> int:
    config, _, doc = _load(args)
    provider_id = args.provider
    provider = get_provider(doc, provider_id)
    if provider is None or provider.builtin:
        console.print(f"[red]Provider {provider_id!r} is not editable.[/red]")
        return 1
    name = args.name or _ask("Display name", provider.name)
    base_url = args.base_url or _ask("Base URL", provider.base_url)
    env_key = args.env_key or _ask("Environment variable name", provider.env_key)
    supports = provider.supports_websockets if args.supports_websockets is None else args.supports_websockets
    upsert_provider(doc, provider_id, name=name, base_url=base_url, env_key=env_key, supports_websockets=bool(supports))
    backup = save_config(config, doc, dry_run=args.dry_run, backup=args.backup)
    console.print(f"{'Would update' if args.dry_run else 'Updated'} provider [bold]{provider_id}[/bold].")
    if backup:
        console.print(f"Config backup: {backup}")
    if (args.prompt_api_key or args.api_key) and not args.dry_run:
        _set_api_key_for_env_key(env_key, value=args.api_key, persist=args.persist_api_key, ask_persist=args.api_key is None)
    return 0


def cmd_remove_provider(args) -> int:
    config, _, doc = _load(args)
    refs = referencing_profiles(doc, args.provider)
    if refs:
        console.print(f"Profiles referencing {args.provider}: {', '.join(refs)}")
    if not args.yes and not _confirm(f"Remove provider {args.provider}?", False):
        return 1
    if refs and (args.delete_profiles or _confirm("Delete referencing profiles too?", False)):
        profiles = doc.get("profiles")
        for name in refs:
            del profiles[name]
    remove_provider(doc, args.provider)
    backup = save_config(config, doc, dry_run=args.dry_run, backup=args.backup)
    console.print(f"{'Would remove' if args.dry_run else 'Removed'} provider [bold]{args.provider}[/bold].")
    if backup:
        console.print(f"Config backup: {backup}")
    return 0


def cmd_fetch_models(args) -> int:
    _, _, doc = _load(args)
    provider = get_provider(doc, args.provider)
    api_key = os.environ.get(provider.env_key) if provider and provider.env_key else None
    result = fetch_models(doc, args.provider, api_key=api_key)
    if not result.ok:
        console.print(f"[red]Failed:[/red] {result.error}")
        console.print("Possible causes: missing env var, unreachable base_url, unsupported /v1/models, or invalid API key.")
        return 1
    for model in result.models:
        console.print(model)
    return 0


def cmd_import_models(args) -> int:
    config, _, doc = _load(args)
    selected = split_csv(args.models)
    if not selected:
        provider = get_provider(doc, args.provider)
        api_key = os.environ.get(provider.env_key) if provider and provider.env_key else None
        result = fetch_models(doc, args.provider, api_key=api_key)
        if not result.ok:
            console.print(f"[red]Failed:[/red] {result.error}")
            return 1
        selected = questionary.checkbox("Select models to import", choices=result.models).ask() or []
    created = import_models(doc, args.provider, selected, reasoning_effort=args.reasoning_effort)
    if args.dry_run:
        console.print("Would create profiles:")
    else:
        backup = save_config(config, doc, backup=args.backup)
        console.print("Created/updated profiles:")
        if backup:
            console.print(f"Config backup: {backup}")
    for name in created:
        console.print(f"- {name}")
    return 0


def cmd_list_profiles(args) -> int:
    _, _, doc = _load(args)
    current = str(doc.get("profile", ""))
    table = Table(title="Codex Profiles")
    table.add_column("current")
    table.add_column("profile")
    table.add_column("model")
    table.add_column("provider")
    for name, data in list_profiles(doc).items():
        table.add_row("*" if name == current else "", name, str(data.get("model", "")), str(data.get("model_provider", "")))
    console.print(table)
    return 0


def cmd_add_profile(args) -> int:
    config, _, doc = _load(args)
    provider_id = args.provider or _ask("Provider id")
    model = args.model or _ask("Model")
    profile_name = args.name or None
    created = add_profile(doc, profile_name=profile_name, provider_id=provider_id, model=model, reasoning_effort=args.reasoning_effort)
    backup = save_config(config, doc, dry_run=args.dry_run, backup=args.backup)
    console.print(f"{'Would create' if args.dry_run else 'Created/updated'} profile [bold]{created}[/bold].")
    if backup:
        console.print(f"Config backup: {backup}")
    return 0


def cmd_switch_profile(args) -> int:
    config, _, doc = _load(args)
    profiles = list_profiles(doc)
    if args.profile not in profiles:
        console.print(f"[red]Profile {args.profile!r} not found.[/red]")
        return 1
    set_root_profile(doc, args.profile)
    backup = save_config(config, doc, dry_run=args.dry_run, backup=args.backup)
    data = profiles[args.profile]
    provider = get_provider(doc, str(data.get("model_provider", "")))
    base = "official auth" if provider and provider.builtin else (provider.base_url if provider else "unknown")
    console.print(f"Current default profile: [bold]{args.profile}[/bold]")
    console.print(f"Model: {data.get('model')}")
    console.print(f"Provider: {data.get('model_provider')}")
    console.print(f"Base: {base}")
    if backup:
        console.print(f"Config backup: {backup}")
    return 0


def cmd_scan_sessions(args) -> int:
    _, sessions, _ = _load(args)
    infos = scan_sessions(sessions)
    table = Table(title="Sessions by Provider")
    table.add_column("provider")
    table.add_column("sessions", justify="right")
    for provider, count in summarize_by_provider(infos).items():
        table.add_row(provider, str(count))
    console.print(table)
    if args.verbose:
        detail = Table(title="Session Files")
        for column in ["provider", "title", "model", "timestamp", "cwd", "path"]:
            detail.add_column(column)
        for info in infos:
            detail.add_row(info.model_provider or "", info.title or "", info.model or "", info.ts or "", info.cwd or "", str(info.path))
        console.print(detail)
    return 0


def cmd_migrate_sessions(args) -> int:
    _, sessions, doc = _load(args)
    infos = scan_sessions(sessions)
    providers = sorted(provider for provider in summarize_by_provider(infos) if provider != "<unknown>")
    target_providers = sorted(set(providers) | {provider.id for provider in list_providers(doc)})
    source = args.source
    target = args.target
    if not source:
        selected = questionary.checkbox("Source providers", choices=providers).ask() or []
        source = ",".join(selected)
    if not target:
        target = questionary.select("Target provider", choices=target_providers).ask()
    if not source or not target:
        console.print("[red]Source and target providers are required.[/red]")
        return 1
    sources = set(split_csv(source))
    candidates = preview_migration(infos, sources)
    preview = Table(title="Session Migration Preview")
    preview.add_column("from")
    preview.add_column("to")
    preview.add_column("title")
    preview.add_column("model")
    preview.add_column("path")
    for info in candidates:
        preview.add_row(info.model_provider or "", target, info.title or "", info.model or "", str(info.path))
    console.print(preview)
    if not args.dry_run and not args.yes and not _confirm(f"Modify {len(candidates)} session files?", False):
        return 1
    result = migrate_sessions(sessions, sources, target, dry_run=args.dry_run, backup=args.backup)
    verb = "Would modify" if args.dry_run else "Modified"
    console.print(f"{verb} {result.changed} session files. Skipped {result.skipped}.")
    if result.undo_path:
        console.print(f"Undo file: {result.undo_path}")
    if result.backup_path:
        console.print(f"Backup directory: {result.backup_path}")
    for warning in result.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")
    if not args.dry_run:
        console.print("Reopen Codex, then check history or run: codex resume --all")
    return 0


def cmd_rollback_sessions(args) -> int:
    result = rollback_sessions(Path(args.undo).expanduser(), dry_run=args.dry_run)
    console.print(f"{'Would restore' if args.dry_run else 'Restored'} {result.changed} session files. Skipped {result.skipped}.")
    for warning in result.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")
    return 0


def cmd_check_env(args) -> int:
    _, _, doc = _load(args)
    for name, status in check_env(doc):
        console.print(f"{name}: {status}")
    return 0


def cmd_set_env(args) -> int:
    _, _, doc = _load(args)
    name = args.name
    if args.provider and not name:
        provider = get_provider(doc, args.provider)
        if not provider or not provider.env_key:
            console.print(f"[red]Provider {args.provider!r} has no env_key.[/red]")
            return 1
        name = provider.env_key
    name = name or _ask("Environment variable name")
    value = args.value or questionary.password(f"Value for {name}").ask()
    if not value:
        return 1
    console.print(set_env_var(name, value, persist=args.persist))
    return 0


def cmd_check_official_auth(args) -> int:
    codex = shutil.which("codex")
    if not codex:
        console.print("[red]codex executable not found. Install Codex CLI, then run codex login.[/red]")
        return 1
    status_cmd = [codex, "/status"]
    try:
        proc = subprocess.run(status_cmd, capture_output=True, text=True, timeout=20)
    except Exception:
        proc = subprocess.run([codex, "--version"], capture_output=True, text=True, timeout=20)
    console.print((proc.stdout or proc.stderr).strip())
    if proc.returncode != 0:
        console.print("If official auth is unavailable, run: codex login")
    return proc.returncode


def cmd_tui(args) -> int:
    config, sessions, _ = _load(args)
    return run_tui(config, sessions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-provider-manager")
    parser.add_argument("--home", help="Override home directory for testing")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor").set_defaults(func=doctor)
    sub.add_parser("tui").set_defaults(func=cmd_tui)
    sub.add_parser("list-providers").set_defaults(func=cmd_list_providers)
    sub.add_parser("providers").set_defaults(func=cmd_list_providers)

    p = sub.add_parser("add-provider")
    p.add_argument("--id")
    p.add_argument("--name")
    p.add_argument("--base-url")
    p.add_argument("--env-key")
    p.add_argument("--supports-websockets", action="store_true")
    p.add_argument("--api-key", help="Set the provider API key into the environment; never written to config.toml")
    p.add_argument("--prompt-api-key", action="store_true", help="Prompt for the provider API key after saving")
    p.add_argument("--persist-api-key", action=argparse.BooleanOptionalAction, default=None, help="Persist API key to the user environment when setting it")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true", help="Create config.toml backup before writing")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=cmd_add_provider)

    p = sub.add_parser("edit-provider")
    p.add_argument("provider")
    p.add_argument("--name")
    p.add_argument("--base-url")
    p.add_argument("--env-key")
    p.add_argument("--supports-websockets", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--api-key", help="Set the provider API key into the environment; never written to config.toml")
    p.add_argument("--prompt-api-key", action="store_true", help="Prompt for the provider API key after saving")
    p.add_argument("--persist-api-key", action=argparse.BooleanOptionalAction, default=None, help="Persist API key to the user environment when setting it")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true", help="Create config.toml backup before writing")
    p.set_defaults(func=cmd_edit_provider)

    p = sub.add_parser("remove-provider")
    p.add_argument("provider")
    p.add_argument("--delete-profiles", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true", help="Create config.toml backup before writing")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=cmd_remove_provider)

    p = sub.add_parser("fetch-models")
    p.add_argument("provider")
    p.set_defaults(func=cmd_fetch_models)
    p = sub.add_parser("models")
    p.add_argument("provider")
    p.set_defaults(func=cmd_fetch_models)

    p = sub.add_parser("import-models")
    p.add_argument("provider")
    p.add_argument("--models", help="Comma-separated model ids")
    p.add_argument("--reasoning-effort", default="medium")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true", help="Create config.toml backup before writing")
    p.set_defaults(func=cmd_import_models)

    sub.add_parser("list-profiles").set_defaults(func=cmd_list_profiles)
    sub.add_parser("profiles").set_defaults(func=cmd_list_profiles)

    p = sub.add_parser("add-profile")
    p.add_argument("--provider")
    p.add_argument("--model")
    p.add_argument("--name")
    p.add_argument("--reasoning-effort", default="medium")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true", help="Create config.toml backup before writing")
    p.set_defaults(func=cmd_add_profile)

    p = sub.add_parser("switch-profile")
    p.add_argument("profile")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true", help="Create config.toml backup before writing")
    p.set_defaults(func=cmd_switch_profile)
    p = sub.add_parser("switch")
    p.add_argument("profile")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true", help="Create config.toml backup before writing")
    p.set_defaults(func=cmd_switch_profile)

    p = sub.add_parser("scan-sessions")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_scan_sessions)
    sub.add_parser("sessions").set_defaults(func=cmd_scan_sessions, verbose=False)

    p = sub.add_parser("migrate-sessions")
    p.add_argument("source", nargs="?")
    p.add_argument("target", nargs="?")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=cmd_migrate_sessions)
    p = sub.add_parser("migrate")
    p.add_argument("source", nargs="?")
    p.add_argument("target", nargs="?")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backup", action="store_true")
    p.add_argument("-y", "--yes", action="store_true")
    p.set_defaults(func=cmd_migrate_sessions)

    p = sub.add_parser("rollback-sessions")
    p.add_argument("--undo", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_rollback_sessions)
    p = sub.add_parser("rollback")
    p.add_argument("--undo", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_rollback_sessions)

    sub.add_parser("check-env").set_defaults(func=cmd_check_env)

    p = sub.add_parser("set-env")
    p.add_argument("--provider")
    p.add_argument("--name")
    p.add_argument("--value")
    p.add_argument("--persist", action="store_true")
    p.set_defaults(func=cmd_set_env)

    sub.add_parser("check-official-auth").set_defaults(func=cmd_check_official_auth)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
