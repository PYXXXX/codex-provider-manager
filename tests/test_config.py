from pathlib import Path

from codex_provider_manager.config import ensure_root_profile_first, load_config, save_config, set_root_profile
from codex_provider_manager.models import add_profile, import_models
from codex_provider_manager.providers import list_providers, upsert_provider


def test_toml_preserves_unknown_sections_and_profiles(tmp_path: Path) -> None:
    path = tmp_path / ".codex" / "config.toml"
    path.parent.mkdir()
    path.write_text(
        """
[marketplaces.openai-bundled]
enabled = true

[profiles.existing]
model = "gpt-5.4"
model_provider = "openai"
""".lstrip(),
        encoding="utf-8",
    )

    doc = load_config(path)
    upsert_provider(
        doc,
        "codexlb",
        name="codex-lb",
        base_url="https://aiapi.bilirec.com/v1",
        env_key="CODEX_LB_API_KEY",
    )
    add_profile(doc, profile_name="codexlb_gpt_5_4", provider_id="codexlb", model="gpt-5.4")
    set_root_profile(doc, "codexlb_gpt_5_4")
    save_config(path, doc)

    text = path.read_text(encoding="utf-8")
    assert text.index('profile = "codexlb_gpt_5_4"') < text.index("[marketplaces.openai-bundled]")
    assert "[marketplaces.openai-bundled]" in text
    assert "[profiles.existing]" in text
    assert "[model_providers.codexlb]" in text
    assert list_providers(load_config(path))[1].id == "codexlb"


def test_config_backup_is_opt_in(tmp_path: Path) -> None:
    path = tmp_path / ".codex" / "config.toml"
    path.parent.mkdir()
    path.write_text('profile = "old"\n', encoding="utf-8")

    doc = load_config(path)
    set_root_profile(doc, "new")
    backup = save_config(path, doc)
    assert backup is None
    assert not list(path.parent.glob("config.toml.backup-*"))

    doc = load_config(path)
    set_root_profile(doc, "newer")
    backup = save_config(path, doc, backup=True)
    assert backup is not None
    assert backup.exists()


def test_import_models_creates_stable_profile_names() -> None:
    doc = ensure_root_profile_first(load_config(Path("does-not-exist.toml")))
    created = import_models(doc, "codexlb", ["gpt-5.4", "gpt-5.5"])
    assert created == ["codexlb_gpt_5_4", "codexlb_gpt_5_5"]
    assert doc["profiles"]["codexlb_gpt_5_4"]["model_provider"] == "codexlb"
    assert doc["profiles"]["codexlb_gpt_5_4"]["model_reasoning_effort"] == "medium"


def test_builtin_openai_provider_is_listed() -> None:
    doc = load_config(Path("does-not-exist.toml"))
    providers = list_providers(doc)
    assert providers[0].id == "openai"
    assert providers[0].builtin is True
