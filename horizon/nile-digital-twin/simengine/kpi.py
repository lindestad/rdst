"""Aggregate per-node timeseries into the three KPIs."""
from __future__ import annotations

from collections import defaultdict


def compute_monthly_kpis(ts_per_node: dict[str, list[dict]]) -> list[dict]:
    """Return sorted-by-month list of {month, water_served_pct, food_tonnes, energy_gwh}."""
    months: dict[str, dict] = defaultdict(lambda: {
        "water_demand_total": 0.0, "water_delivered_total": 0.0,
        "food_tonnes": 0.0, "energy_gwh": 0.0,
    })
    for node_id, rows in ts_per_node.items():
        for r in rows:
            m = r["month"]
            if "demand_m3" in r and "delivered_m3" in r and "population_served" in r:
                months[m]["water_demand_total"] += r["demand_m3"]
                months[m]["water_delivered_total"] += r["delivered_m3"]
            if "food_tonnes_month" in r:
                months[m]["food_tonnes"] += r["food_tonnes_month"]
            if "energy_gwh" in r:
                months[m]["energy_gwh"] += r["energy_gwh"]

    out = []
    for m in sorted(months):
        agg = months[m]
        served = (agg["water_delivered_total"] / agg["water_demand_total"]
                  if agg["water_demand_total"] > 0 else 1.0)
        out.append({
            "month": m,
            "water_served_pct": served,
            "food_tonnes": agg["food_tonnes"],
            "energy_gwh": agg["energy_gwh"],
        })
    return out
