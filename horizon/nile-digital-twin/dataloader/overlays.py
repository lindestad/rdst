"""Sentinel-2 + CGLS NDVI aggregation per irrigation zone -> monthly Parquet."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from dataloader import config
from dataloader.nodes import NDVI_ZONES

NDVI_SPEC_COLUMNS = ["month", "ndvi_mean", "ndvi_std", "valid_pixel_frac"]


def build(stub: bool = False) -> None:
    config.OVERLAYS_DIR.mkdir(parents=True, exist_ok=True)
    for zone_id in NDVI_ZONES:
        out_path = config.OVERLAYS_DIR / f"{zone_id}.parquet"
        if out_path.exists():
            continue
        df = _stub_ndvi(seed=abs(hash(zone_id)) % (2**32)) if stub else _real_ndvi(zone_id)
        df.to_parquet(out_path, index=False)


def _stub_ndvi(seed: int = 7) -> pd.DataFrame:
    months = pd.date_range("2005-01-01", "2024-12-01", freq="MS")
    n = len(months)
    season = np.sin(2 * np.pi * (months.month - 4) / 12)
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "month": months,
        "ndvi_mean": np.clip(0.35 + 0.25 * season + rng.normal(0, 0.03, n), 0, 0.9),
        "ndvi_std":  np.clip(0.05 + rng.normal(0, 0.01, n), 0.01, 0.2),
        "valid_pixel_frac": np.clip(0.8 + rng.normal(0, 0.1, n), 0, 1),
    })
    return df[NDVI_SPEC_COLUMNS]


def _real_ndvi(zone_id: str) -> pd.DataFrame:
    """Placeholder for the real Sentinel-2 + CGLS fetch.

    Real implementation lives in L1 Task 9 (Sunday deliverable). Deps required:
    pystac-client, stackstac, rioxarray. Until then, fall back to stub data so
    downstream lanes aren't blocked.
    """
    warnings.warn(f"_real_ndvi for {zone_id} not yet implemented; using stub", stacklevel=2)
    return _stub_ndvi()
