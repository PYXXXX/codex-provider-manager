from pathlib import Path

import tomlkit

from codex_provider_manager.tui import _current_profile_provider, _paths_not_on_provider
from codex_provider_manager.sessions import SessionInfo


def test_current_profile_provider_reads_active_profile() -> None:
    doc = tomlkit.parse(
        """
profile = "codexlb_gpt_5_4"

[profiles.codexlb_gpt_5_4]
model = "gpt-5.4"
model_provider = "codexlb"
""".lstrip()
    )

    assert _current_profile_provider(doc) == "codexlb"


def test_paths_not_on_provider_preselects_only_sessions_outside_current_provider() -> None:
    infos = [
        SessionInfo(Path("a.jsonl"), None, "A", "gpt-5.4", "huaibao", None, None),
        SessionInfo(Path("b.jsonl"), None, "B", "gpt-5.4", "codexlb", None, None),
        SessionInfo(Path("bad.jsonl"), None, None, None, None, None, None, "bad first line"),
    ]

    assert _paths_not_on_provider(infos, "codexlb") == {Path("a.jsonl")}
