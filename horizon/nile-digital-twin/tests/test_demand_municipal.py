import pandas as pd

from simengine.nodes.demand_municipal import DemandMunicipal


def test_served_fraction():
    d = DemandMunicipal(id="m", upstream=["u"], downstream=["x"],
                        population_baseline=10_000_000, per_capita_l_day=200)
    d.load_forcings(pd.DataFrame({"month": pd.date_range("2020-07-01", periods=1, freq="MS"),
                                  "pet_mm": [0.0]}))
    state = {"u": {"outflow_m3s": 100.0}}  # 100 m³/s ~ enough
    d.step(0, state, policy={"population_scale": 1.0})
    assert state["m"]["served_pct"] > 0.9
