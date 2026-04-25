from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml


def read_period_start(path: Path | str) -> date | None:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        return None
    settings = value.get("settings")
    if not isinstance(settings, dict):
        return None
    start = settings.get("start_date")
    if isinstance(start, date):
        return start
    if isinstance(start, str):
        return date.fromisoformat(start)
    return None
