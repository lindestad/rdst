import pandas as pd

from simengine.kpi import compute_monthly_kpis


def test_kpi_aggregates_across_nodes():
    ts = {
        "cairo_muni":   [{"month": "2020-01", "population_served": 18e6, "demand_m3": 124e6, "delivered_m3": 120e6}],
        "gezira_irr":   [{"month": "2020-01", "food_tonnes_month": 10000}],
        "egypt_ag":     [{"month": "2020-01", "food_tonnes_month": 40000}],
        "gerd":         [{"month": "2020-01", "energy_gwh": 300}],
        "aswan":        [{"month": "2020-01", "energy_gwh": 150}],
    }
    kpis = compute_monthly_kpis(ts)
    assert len(kpis) == 1
    k = kpis[0]
    assert k["month"] == "2020-01"
    assert abs(k["water_served_pct"] - (120/124)) < 1e-3
    assert k["food_tonnes"] == 50000
    assert k["energy_gwh"] == 450
