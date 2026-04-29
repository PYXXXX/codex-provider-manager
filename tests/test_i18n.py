from codex_provider_manager.i18n import _is_chinese_candidate


def test_detects_standard_zh_locale_names() -> None:
    assert _is_chinese_candidate("zh_CN")
    assert _is_chinese_candidate("zh-Hant-TW")


def test_detects_windows_chinese_locale_names() -> None:
    assert _is_chinese_candidate("Chinese (Simplified)_China")
