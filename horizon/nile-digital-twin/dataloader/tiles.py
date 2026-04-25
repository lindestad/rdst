"""Render monthly NDVI rasters to flat-colour XYZ tile stubs.

Each (zone, month) pair gets one 256x256 PNG whose color reflects mean NDVI.
Good enough for the dashboard overlay at the pitch. A production implementation
would mosaic real S2 scenes with rio-tiler.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from dataloader import config
from dataloader.nodes import NDVI_ZONES

# Tan -> olive -> green gradient, NDVI roughly -0.2..0.9
NDVI_CMAP = np.array([
    [198, 183, 151], [212, 197, 140], [220, 212, 129], [200, 215, 115],
    [170, 210, 100], [130, 200,  80], [ 90, 180,  60], [ 50, 150,  40],
    [ 20, 120,  25], [ 10,  90,  15],
], dtype=np.uint8)


def build() -> None:
    config.TILES_DIR.mkdir(parents=True, exist_ok=True)
    for zone_id in NDVI_ZONES:
        parq = config.OVERLAYS_DIR / f"{zone_id}.parquet"
        if not parq.exists():
            continue
        df = pd.read_parquet(parq)
        for _, row in df.iterrows():
            _write_flat_tile(zone_id, row["month"], float(row["ndvi_mean"]))


def _write_flat_tile(zone_id: str, month, ndvi: float) -> None:
    month_str = pd.Timestamp(month).strftime("%Y-%m")
    out_dir = config.TILES_DIR / zone_id / month_str / "7" / "0"
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = int(np.clip((ndvi + 0.2) / 1.1 * (len(NDVI_CMAP) - 1), 0, len(NDVI_CMAP) - 1))
    color = tuple(NDVI_CMAP[idx].tolist()) + (180,)   # RGBA
    img = Image.new("RGBA", (256, 256), color)
    img.save(out_dir / "0.png", format="PNG")
