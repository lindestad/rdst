import numpy as np
import pandas as pd

from simengine.nodes.source import Source


def test_source_outflow_from_runoff():
    # 100,000 km² catchment × 30 mm runoff/month × scale 1.0
    # → 30 mm × 1e5 km² = 3.0e9 m³/month → m³/s ÷ (30×86400) ≈ 1157 m³/s
    src = Source(id="src", upstream=[], downstream=["x"],
                 catchment_area_km2=100000, catchment_scale=1.0)
    forcings = pd.DataFrame({
        "month": pd.date_range("2020-01-01", periods=3, freq="MS"),
        "runoff_mm": [30.0, 30.0, 30.0],
    })
    src.load_forcings(forcings)
    state: dict = {}
    src.step(0, state)
    assert "src" in state
    flow = state["src"]["outflow_m3s"]
    assert 1100 < flow < 1200, flow


def test_source_catchment_scale_multiplies():
    src = Source(id="src", upstream=[], downstream=["x"],
                 catchment_area_km2=100000, catchment_scale=2.0)
    forcings = pd.DataFrame({"month": pd.date_range("2020-01-01", periods=1, freq="MS"),
                             "runoff_mm": [30.0]})
    src.load_forcings(forcings)
    state: dict = {}
    src.step(0, state)
    assert 2300 < state["src"]["outflow_m3s"] < 2400
