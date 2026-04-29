from pathlib import Path

import requests_mock

from codex_provider_manager.config import load_config
from codex_provider_manager.models import fetch_models
from codex_provider_manager.providers import upsert_provider


def test_fetch_models_openai_compatible_response() -> None:
    doc = load_config(Path("does-not-exist.toml"))
    upsert_provider(
        doc,
        "codexlb",
        name="codex-lb",
        base_url="https://aiapi.bilirec.com/v1",
        env_key="CODEX_LB_API_KEY",
    )
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://aiapi.bilirec.com/v1/models",
            json={"object": "list", "data": [{"id": "gpt-5.5"}, {"id": "gpt-5.4"}]},
        )
        result = fetch_models(doc, "codexlb", api_key="secret")

    assert result.ok is True
    assert result.models == ["gpt-5.4", "gpt-5.5"]


def test_fetch_models_reports_missing_env_key() -> None:
    doc = load_config(Path("does-not-exist.toml"))
    upsert_provider(
        doc,
        "huaibao",
        name="huaibao",
        base_url="https://ai.huaibao.top/v1",
        env_key="HUAIBAO_API_KEY",
    )
    result = fetch_models(doc, "huaibao", api_key=None)
    assert result.ok is False
    assert "HUAIBAO_API_KEY" in result.error
