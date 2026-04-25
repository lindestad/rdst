from simengine.scoring import score_scenario


def test_perfect_scenario_scores_high():
    kpis = [{"month": "2020-01", "water_served_pct": 1.0, "food_tonnes": 50000, "energy_gwh": 450}]
    baseline = {"food_tonnes": 40000, "energy_gwh": 300}
    weights = {"water": 0.4, "food": 0.3, "energy": 0.3}
    sink_outflow_m3s_by_month = {"2020-01": 1000.0}
    out = score_scenario(kpis, baseline, weights,
                         min_delta_flow_m3s=500, sink_outflow=sink_outflow_m3s_by_month)
    assert out["score"] > 0.9
    assert out["breakdown"]["delta_penalty"] == 0.0


def test_delta_violation_penalizes():
    kpis = [{"month": "2020-01", "water_served_pct": 1.0, "food_tonnes": 50000, "energy_gwh": 450}]
    baseline = {"food_tonnes": 40000, "energy_gwh": 300}
    weights = {"water": 0.4, "food": 0.3, "energy": 0.3}
    out = score_scenario(kpis, baseline, weights,
                         min_delta_flow_m3s=500, sink_outflow={"2020-01": 100.0})
    assert out["breakdown"]["delta_penalty"] > 0.0
    assert out["score"] < 0.9
