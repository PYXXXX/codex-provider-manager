from codex_provider_manager.utils import env_key_for_provider_id


def test_env_key_for_provider_id_uses_stable_uppercase_name() -> None:
    assert env_key_for_provider_id("onetoken") == "ONETOKEN_API_KEY"
    assert env_key_for_provider_id("codex-lb") == "CODEX_LB_API_KEY"
    assert env_key_for_provider_id("huaibao_router") == "HUAIBAO_ROUTER_API_KEY"
