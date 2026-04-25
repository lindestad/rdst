from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from api import deps

router = APIRouter()


@router.get("/nodes")
def list_nodes():
    return deps.nodes_geojson()


@router.get("/nodes/{node_id}")
def get_node(node_id: str):
    cfg = deps.node_config()["nodes"]
    if node_id not in cfg:
        raise HTTPException(status_code=404, detail=f"unknown node: {node_id}")
    return {"id": node_id, **cfg[node_id]}


@router.get("/nodes/{node_id}/timeseries")
def get_timeseries(
    node_id: str,
    start: str = Query(default="2005-01", pattern=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2024-12", pattern=r"^\d{4}-\d{2}$"),
    vars: str | None = Query(default=None),
):
    p = deps.DATA_DIR / "timeseries" / f"{node_id}.parquet"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"no timeseries for {node_id}")
    df = pd.read_parquet(p)
    df["month"] = pd.to_datetime(df["month"])
    df = df[(df["month"] >= f"{start}-01") & (df["month"] <= f"{end}-01")]
    requested = [v.strip() for v in vars.split(",")] if vars else [
        c for c in df.columns if c != "month"
    ]
    return {
        "month": df["month"].dt.strftime("%Y-%m").tolist(),
        "values": {
            v: df[v].where(df[v].notna(), None).tolist()
            for v in requested if v in df.columns
        },
    }
