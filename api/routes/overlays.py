from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from api import deps

router = APIRouter()


@router.get("/overlays/ndvi/{zone_id}")
def get_ndvi(
    zone_id: str,
    start: str = Query(default="2005-01", pattern=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2024-12", pattern=r"^\d{4}-\d{2}$"),
):
    p = deps.DATA_DIR / "overlays" / "ndvi" / f"{zone_id}.parquet"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"no NDVI for {zone_id}")
    df = pd.read_parquet(p)
    df["month"] = pd.to_datetime(df["month"])
    df = df[(df["month"] >= f"{start}-01") & (df["month"] <= f"{end}-01")]
    return {
        "month": df["month"].dt.strftime("%Y-%m").tolist(),
        "values": {
            c: df[c].tolist()
            for c in ("ndvi_mean", "ndvi_std", "valid_pixel_frac")
        },
    }
