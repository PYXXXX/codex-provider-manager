from __future__ import annotations

import locale
import os


def is_chinese_locale() -> bool:
    candidates = [
        locale.getlocale(locale.LC_CTYPE)[0],
        os.environ.get("LANG"),
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
    ]
    return any(str(candidate).lower().startswith("zh") for candidate in candidates if candidate)


ZH = is_chinese_locale()


def tr(zh: str, en: str) -> str:
    return zh if ZH else en
