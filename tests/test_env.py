import os

from codex_provider_manager.env import set_env_var


def test_set_env_var_does_not_echo_secret(monkeypatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")

    message = set_env_var("CPM_TEST_KEY", "sk-secret-value", persist=True)

    assert os.environ["CPM_TEST_KEY"] == "sk-secret-value"
    assert "sk-secret-value" not in message
    assert "CPM_TEST_KEY" in message
