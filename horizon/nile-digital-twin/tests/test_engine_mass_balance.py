import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from simengine.engine import run
from simengine.scenario import Scenario


def _setup_three_node(tmp_path):
    # source → reservoir → sink, 12 months, constant inflow, no evap
    cfg = tmp_path / "config.yaml"
    cfg.write_text("""
nodes:
  src: {type: source, catchment_area_km2: 100000, catchment_scale: 1.0}
  res:
    type: reservoir
    storage_capacity_mcm: 10000
    storage_min_mcm: 100
    surface_area_km2_at_full: 1
    initial_storage_mcm: 5000
    hep: {nameplate_mw: 100, head_m: 50, efficiency: 0.9}
  snk: {type: sink, min_environmental_flow_m3s: 0}
reaches: {}
""")
    topo = tmp_path / "topo.json"
    topo.write_text('{"edges":[["src","res"],["res","snk"]]}')

    # Forcings: 30 mm/month runoff, zero PET (no evap)
    ts_dir = tmp_path / "timeseries"
    ts_dir.mkdir()
    months = pd.date_range("2020-01-01", periods=12, freq="MS")
    for nid in ("src", "res", "snk"):
        df = pd.DataFrame({"month": months, "runoff_mm": [30.0] * 12,
                           "pet_mm": [0.0] * 12, "precip_mm": [0.0] * 12,
                           "temp_c": [25.0] * 12, "radiation_mj_m2": [20.0] * 12,
                           "wind_ms": [2.0] * 12, "dewpoint_c": [15.0] * 12,
                           "historical_discharge_m3s": pd.NA})
        df.to_parquet(ts_dir / f"{nid}.parquet", index=False)

    scenario = Scenario(
        name="t", period=["2020-01", "2020-12"],
        policy={"reservoirs": {}, "demands": {}, "constraints": {},
                "weights": {"water": 0.34, "food": 0.33, "energy": 0.33}},
    )
    return cfg, topo, ts_dir, scenario


def test_mass_conservation_over_year(tmp_path):
    cfg, topo, ts_dir, scenario = _setup_three_node(tmp_path)
    result = run(scenario, config_path=cfg, topology_path=topo, timeseries_dir=ts_dir)
    # Sum inflow at source; sum outflow at sink; sum evap; storage change at reservoir
    # inflow_total = snk_inflow_total + evap_total + (storage_end - storage_start)
    src_ts = result.results.timeseries_per_node["src"]
    res_ts = result.results.timeseries_per_node["res"]
    snk_ts = result.results.timeseries_per_node["snk"]
    src_total = sum(r["outflow_m3s"] * pd.Timestamp(r["month"]).days_in_month * 86400 for r in src_ts)
    snk_total = sum(r["inflow_m3s"] * pd.Timestamp(r["month"]).days_in_month * 86400 for r in snk_ts)
    evap_total = sum(r["evap_mcm"] * 1e6 for r in res_ts)
    d_storage_m3 = (res_ts[-1]["storage_mcm"] - 5000.0) * 1e6
    # Mass balance in m³
    assert abs(src_total - (snk_total + evap_total + d_storage_m3)) / src_total < 0.001
