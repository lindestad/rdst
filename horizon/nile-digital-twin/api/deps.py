"""Data paths and cached loaders."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(os.environ.get("NILE_DATA_DIR", "data")).resolve()


@lru_cache(maxsize=1)
def nodes_geojson() -> dict:
    return json.loads((DATA_DIR / "nodes.geojson").read_text())


@lru_cache(maxsize=1)
def node_config() -> dict[str, Any]:
    return yaml.safe_load((DATA_DIR / "node_config.yaml").read_text())
