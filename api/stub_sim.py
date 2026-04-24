"""Returns fake but schema-correct scenario results.

Used by /scenarios/run when NILE_USE_REAL_SIM != "1". Lets L4 (dashboard) build
against the final JSON shape before L2 is wired in through L3. In this repo the
real sim is already available, but the stub stays around for offline demos."""
from __future__ import annotations

import random

import pandas as pd

from simengine.scenario import Scenario, ScenarioResults


def fake_run(scenario: Scenario) -> Scenario:
    start, end = scenario.period
    months = pd.date_range(f"{start}-01", f"{end}-01", freq="MS").strftime("%Y-%m").tolist()
    rnd = random.Random(hash(scenario.name) & 0xFFFFFFFF)

    ts = {
        "gerd": [{"month": m,
                  "storage_mcm": 50000 + 5000 * ((i % 12) - 6),
                  "release_m3s": 1500 + rnd.randint(-200, 200),
                  "inflow_m3s": 1600,
                  "evap_mcm": 80,
                  "energy_gwh": 300 + rnd.randint(-50, 50)}
                 for i, m in enumerate(months)],
        "aswan": [{"month": m, "storage_mcm": 100000, "release_m3s": 1800,
                   "inflow_m3s": 1850, "evap_mcm": 1200, "energy_gwh": 160}
                  for m in months],
    }
    kpi = [{"month": m,
            "water_served_pct": 0.92 + rnd.uniform(-0.05, 0.05),
            "food_tonnes": 1_000_000 + rnd.randint(-100_000, 100_000),
            "energy_gwh": 450 + rnd.randint(-30, 30)}
           for m in months]

    scenario.results = ScenarioResults(
        timeseries_per_node=ts,
        kpi_monthly=kpi,
        score=0.72,
        score_breakdown={"water": 0.9, "food": 0.6, "energy": 0.7, "delta_penalty": 0.0},
    )
    return scenario
