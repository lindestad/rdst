"""Per-node forcings loader — reads data/timeseries/<node_id>.parquet."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_forcings(node_id: str, timeseries_dir: Path) -> pd.DataFrame:
    path = Path(timeseries_dir) / f"{node_id}.parquet"
    if not path.exists():
        # Nodes without per-node forcings (e.g., confluences) get an empty frame.
        return pd.DataFrame()
    return pd.read_parquet(path)
