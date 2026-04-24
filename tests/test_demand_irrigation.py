import pandas as pd

from simengine.nodes.demand_irrigation import DemandIrrigation


def test_pulls_demand_up_to_available():
    d = DemandIrrigation(id="ir", upstream=["u"], downstream=["x"],
                         area_ha_baseline=100000, crop_water_productivity_kg_per_m3=1.0)
    d.load_forcings(pd.DataFrame({"month": pd.date_range("2020-07-01", periods=1, freq="MS"),
                                  "pet_mm": [200.0]}))
    # Huge upstream supply → fully met
    state = {"u": {"outflow_m3s": 10000.0}}
    d.step(0, state, policy={"area_scale": 1.0})
    assert state["ir"]["delivered_fraction"] == 1.0
    # Outflow = inflow - delivered
    delivered_m3s = state["ir"]["delivered_m3s"]
    assert state["ir"]["outflow_m3s"] == 10000.0 - delivered_m3s


def test_partial_delivery_when_supply_short():
    d = DemandIrrigation(id="ir", upstream=["u"], downstream=["x"],
                         area_ha_baseline=100000, crop_water_productivity_kg_per_m3=1.0)
    d.load_forcings(pd.DataFrame({"month": pd.date_range("2020-07-01", periods=1, freq="MS"),
                                  "pet_mm": [200.0]}))
    state = {"u": {"outflow_m3s": 10.0}}
    d.step(0, state, policy={"area_scale": 1.0})
    assert state["ir"]["delivered_fraction"] < 1.0
    assert state["ir"]["outflow_m3s"] == 0.0
