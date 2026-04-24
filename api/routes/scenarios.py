from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api import deps
from api.scenario_store import ScenarioStore
from api.stub_sim import fake_run
from simengine.scenario import Scenario

router = APIRouter()


def _store() -> ScenarioStore:
    """Fresh store per call so the tests' monkeypatched DATA_DIR is picked up."""
    return ScenarioStore()


def _run(scenario: Scenario) -> Scenario:
    """Real sim when NILE_USE_REAL_SIM=1, stub otherwise."""
    if os.environ.get("NILE_USE_REAL_SIM") == "1":
        from simengine.engine import run as real_run
        return real_run(
            scenario,
            config_path=deps.DATA_DIR / "node_config.yaml",
            geojson_path=deps.DATA_DIR / "nodes.geojson",
            timeseries_dir=deps.DATA_DIR / "timeseries",
        )
    return fake_run(scenario)


@router.post("/scenarios/run")
def run_scenario(scenario: Scenario):
    return _run(scenario).model_dump()


@router.get("/scenarios")
def list_scenarios():
    return _store().list()


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    return _store().load(scenario_id).model_dump()


@router.post("/scenarios/{scenario_id}/save")
def save_scenario(scenario_id: str, scenario: Scenario):
    if scenario.id != scenario_id:
        raise HTTPException(status_code=400, detail="id mismatch")
    return _store().save(scenario).model_dump()


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: str):
    _store().delete(scenario_id)
    return None


class CompareRequest(BaseModel):
    scenario_ids: list[str]


@router.post("/scenarios/compare")
def compare_scenarios(req: CompareRequest):
    if len(req.scenario_ids) != 2:
        raise HTTPException(status_code=400, detail="need exactly 2 scenario_ids")
    store = _store()
    a = store.load(req.scenario_ids[0])
    b = store.load(req.scenario_ids[1])
    if not (a.results and b.results):
        raise HTTPException(status_code=400, detail="both scenarios must have results")

    a_by_m = {r["month"]: r for r in a.results.kpi_monthly}
    b_by_m = {r["month"]: r for r in b.results.kpi_monthly}
    months = sorted(set(a_by_m) | set(b_by_m))
    zero = {"water_served_pct": 0.0, "food_tonnes": 0.0, "energy_gwh": 0.0}
    deltas = []
    for m in months:
        ra = a_by_m.get(m, zero)
        rb = b_by_m.get(m, zero)
        deltas.append({
            "month": m,
            "water_served_pct": rb["water_served_pct"] - ra["water_served_pct"],
            "food_tonnes": rb["food_tonnes"] - ra["food_tonnes"],
            "energy_gwh": rb["energy_gwh"] - ra["energy_gwh"],
        })

    return {
        "scenarios": {
            a.id: {"name": a.name, "score": a.results.score},
            b.id: {"name": b.name, "score": b.results.score},
        },
        "kpi_deltas": deltas,
        "score_delta": (b.results.score or 0) - (a.results.score or 0),
    }
