"""Weighted-sum score of KPIs with a delta-flow penalty."""
from __future__ import annotations


def score_scenario(kpis, baseline, weights, min_delta_flow_m3s, sink_outflow):
    """kpis: list of dicts from simengine.kpi.compute_monthly_kpis
    baseline: dict with reference food_tonnes + energy_gwh (per-month mean) for normalization
    weights: dict with water/food/energy summing to 1
    min_delta_flow_m3s: scalar constraint
    sink_outflow: {"YYYY-MM": m3s} at the sink node
    """
    n = max(1, len(kpis))
    water_avg = sum(k["water_served_pct"] for k in kpis) / n
    food_avg = sum(k["food_tonnes"] for k in kpis) / n
    energy_avg = sum(k["energy_gwh"] for k in kpis) / n

    food_score = min(1.0, food_avg / max(1.0, baseline["food_tonnes"]))
    energy_score = min(1.0, energy_avg / max(1.0, baseline["energy_gwh"]))

    violations = sum(1 for m in (k["month"] for k in kpis)
                     if sink_outflow.get(m, 0.0) < min_delta_flow_m3s)
    delta_penalty = violations / n * 0.3

    raw = weights["water"] * water_avg + weights["food"] * food_score + weights["energy"] * energy_score
    score = max(0.0, raw - delta_penalty)
    return {
        "score": score,
        "breakdown": {
            "water": water_avg,
            "food": food_score,
            "energy": energy_score,
            "delta_penalty": delta_penalty,
        },
    }
