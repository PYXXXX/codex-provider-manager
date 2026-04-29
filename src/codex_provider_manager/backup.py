from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def backup_file(path: Path) -> Path:
    backup = path.with_name(f"{path.name}.backup-{timestamp()}")
    shutil.copy2(path, backup)
    return backup


def backup_sessions_dir(sessions_dir: Path) -> Path:
    target = sessions_dir.with_name(f"{sessions_dir.name}.backup-{timestamp()}")
    shutil.copytree(sessions_dir, target)
    return target
