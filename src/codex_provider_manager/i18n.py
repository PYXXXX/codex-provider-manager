from __future__ import annotations

import ctypes
import locale
import os


def _windows_locale_candidates() -> list[str]:
    if os.name != "nt":
        return []
    candidates: list[str] = []
    try:
        buffer = ctypes.create_unicode_buffer(85)
        length = ctypes.windll.kernel32.GetUserDefaultLocaleName(buffer, len(buffer))
        if length:
            candidates.append(buffer.value)
    except Exception:
        pass
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        primary_lang_id = lang_id & 0x3FF
        if primary_lang_id == 0x04:
            candidates.append("zh")
    except Exception:
        pass
    return candidates


def _is_chinese_candidate(candidate: object) -> bool:
    value = str(candidate).lower()
    return value.startswith("zh") or value.startswith("chinese")


def is_chinese_locale() -> bool:
    candidates = [
        os.environ.get("CPM_LANG"),
        os.environ.get("CODEX_PROVIDER_MANAGER_LANG"),
        os.environ.get("LANGUAGE"),
        locale.getlocale(locale.LC_CTYPE)[0],
        locale.getlocale()[0],
        os.environ.get("LANG"),
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
    ]
    candidates.extend(_windows_locale_candidates())
    return any(_is_chinese_candidate(candidate) for candidate in candidates if candidate)


ZH = is_chinese_locale()


def tr(zh: str, en: str) -> str:
    return zh if ZH else en
