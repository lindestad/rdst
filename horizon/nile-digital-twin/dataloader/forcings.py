"""Orchestrates ERA5 fetch -> monthly aggregation -> Parquet per node."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from dataloader import config
from dataloader.aggregate import SPEC_COLUMNS


def build(stub: bool = False) -> None:
    geojson = json.loads(config.NODES_GEOJSON.read_text())
    config.TIMESERIES_DIR.mkdir(parents=True, exist_ok=True)
    for feat in geojson["features"]:
        node_id = feat["properties"]["id"]
        out_path = config.TIMESERIES_DIR / f"{node_id}.parquet"
        if out_path.exists():
            continue
        if stub:
            df = _stub_timeseries(seed=abs(hash(node_id)) % (2**32))
        else:
            lon, lat = feat["geometry"]["coordinates"]
            bbox = _bbox_for_node(feat["properties"]["type"], lat, lon)
            nc = config.DATA_DIR / "raw_era5" / f"{node_id}.nc"
            from dataloader.aggregate import monthly_forcings_from_era5
            from dataloader.era5 import fetch_era5_daily
            fetch_era5_daily(bbox, config.PERIOD_START, config.PERIOD_END, nc)
            df = monthly_forcings_from_era5(
                nc,
                lat_min=bbox[2], lat_max=bbox[0],
                lon_min=bbox[1], lon_max=bbox[3],
            )
        df.to_parquet(out_path, index=False)


def _bbox_for_node(node_type: str, lat: float, lon: float) -> tuple[float, float, float, float]:
    """Return (lat_max, lon_min, lat_min, lon_max) — CDS API order."""
    d = 3.0 if node_type == "source" else 0.5
    return (lat + d, lon - d, lat - d, lon + d)


def _stub_timeseries(seed: int = 42) -> pd.DataFrame:
    """240 months (2005-2024) of schema-correct synthetic data."""
    months = pd.date_range("2005-01-01", "2024-12-01", freq="MS")
    n = len(months)
    rng = np.random.default_rng(seed)
    doy = months.month.to_numpy()
    season = np.sin(2 * np.pi * (doy - 4) / 12)
    df = pd.DataFrame({
        "month": months,
        "precip_mm":               np.clip(40 + 50 * season + rng.normal(0, 10, n), 0, None),
        "temp_c":                  25 + 5 * season + rng.normal(0, 1, n),
        "radiation_mj_m2":         20 + 5 * season + rng.normal(0, 1, n),
        "wind_ms":                 2.5 + rng.normal(0, 0.3, n),
        "dewpoint_c":              10 + 5 * season + rng.normal(0, 1, n),
        "pet_mm":                  120 + 40 * season + rng.normal(0, 10, n),
        "runoff_mm":               np.clip(5 + 10 * season + rng.normal(0, 3, n), 0, None),
        "historical_discharge_m3s": pd.NA,
    })
    return df[SPEC_COLUMNS]
