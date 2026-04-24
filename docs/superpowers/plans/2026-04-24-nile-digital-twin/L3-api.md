# L3 — API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FastAPI layer that reads L1's canonical data (Parquet + GeoJSON + YAML), calls L2's sim engine, persists scenarios as JSON files on disk, and serves everything L4 (dashboard) needs over REST. Dockerized; runs locally via `docker compose up`.

**Architecture:** Thin FastAPI app. Stateless except for file-backed scenario store (`data/scenarios/<uuid>.json`). No DB. No auth. Sim calls are synchronous (one run ≈10 ms). The optimizer endpoint is the only background task.

**Tech stack:** Python 3.11, `fastapi>=0.110`, `uvicorn[standard]`, `pydantic>=2.6`, Docker, Docker Compose.

**Lane ownership:** 1 person. Deliverables:
- **Sat 17:00** — stub API (returns hard-coded sim results) published, L4 wires against it. This is the critical unblock.
- **Sun 10:00** — real sim wired; `/scenarios/run` returns real KPIs.
- **Sun 13:00** — Dockerfile + `docker-compose.yml` working; app reachable at http://localhost:8000.

**Shared contracts** (from spec — copied verbatim):

Endpoints:
```
GET    /health
GET    /nodes                            → nodes.geojson
GET    /nodes/{id}                       → static config for one node
GET    /nodes/{id}/timeseries
       ?start=2005-01&end=2024-12
       &vars=precip_mm,pet_mm,...        → column-oriented JSON
GET    /overlays/ndvi/{zone_id}
       ?start=...&end=...                → NDVI time-series

POST   /scenarios/run                    → runs sim synchronously, returns full scenario
GET    /scenarios                        → list (metadata only)
GET    /scenarios/{id}                   → one scenario, results included
POST   /scenarios/{id}/save              → promote run to saved
DELETE /scenarios/{id}
POST   /scenarios/compare                → {scenario_ids: [a, b]} → diff payload

POST   /optimize                         → STRETCH. Background.
GET    /optimize/{job_id}                → poll
```

Column-oriented timeseries JSON shape:
```json
{"month": ["2005-01","2005-02",...],
 "values": {"precip_mm": [...], "pet_mm": [...]}}
```

Compare response shape:
```json
{"scenarios": {"a": {"name": "...", "score": 0.72}, "b": {...}},
 "kpi_deltas": [{"month": "2005-01", "water_served_pct": 0.02, "food_tonnes": -120000, "energy_gwh": 50}, ...],
 "score_delta": 0.09}
```

---

## File Structure

```
api/
  __init__.py
  __main__.py                # uvicorn entry: `python -m api`
  app.py                     # FastAPI factory + CORS + route registration
  deps.py                    # data paths, cached loaders
  models.py                  # API pydantic request/response models (not sim models)
  stub_sim.py                # returns fake sim results for Sat 17:00 deadline
  scenario_store.py          # file-backed CRUD on data/scenarios/*.json
  routes/
    __init__.py
    health.py
    nodes.py
    overlays.py
    scenarios.py
    optimize.py              # stretch
Dockerfile.api
docker-compose.yml
tests/
  test_health.py
  test_nodes_route.py
  test_overlays_route.py
  test_scenarios_route.py
  test_scenario_store.py
  conftest.py                # fixture data dir with stub parquets
```

---

## Task 1: Scaffold + healthz

**Files:**
- Modify: `pyproject.toml` (add fastapi deps)
- Create: `api/__init__.py`, `api/__main__.py`, `api/app.py`, `api/deps.py`, `api/routes/__init__.py`, `api/routes/health.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Add API deps to `pyproject.toml`**

In `[project]` dependencies, add:

```toml
"fastapi>=0.110",
"uvicorn[standard]>=0.29",
"httpx>=0.27",          # for TestClient
```

- [ ] **Step 2: Write the failing test**

`tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from api.app import create_app


def test_health_ok():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 3: Create `api/deps.py`**

```python
"""Data paths and cached loaders."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(os.environ.get("NILE_DATA_DIR", "data")).resolve()


@lru_cache(maxsize=1)
def nodes_geojson() -> dict:
    return json.loads((DATA_DIR / "nodes.geojson").read_text())


@lru_cache(maxsize=1)
def node_config() -> dict[str, Any]:
    return yaml.safe_load((DATA_DIR / "node_config.yaml").read_text())
```

- [ ] **Step 4: Create `api/routes/__init__.py`** (empty)

- [ ] **Step 5: Create `api/routes/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Create `api/app.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health


def create_app() -> FastAPI:
    app = FastAPI(title="Nile Digital Twin API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],         # hackathon; tighten later if deployed
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    return app


app = create_app()
```

- [ ] **Step 7: Create `api/__main__.py`**

```python
def main() -> None:
    import uvicorn
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Run test and smoke test**

```bash
pip install -e ".[dev]"
pytest tests/test_health.py -v
python -m api &
sleep 1
curl -s http://localhost:8000/health
kill %1
```

Expected: test passes, curl returns `{"status":"ok"}`.

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml api/ tests/test_health.py
git commit -m "L3: FastAPI scaffold + /health"
```

---

## Task 2: Nodes routes

**Files:**
- Create: `api/routes/nodes.py`
- Create: `tests/test_nodes_route.py`
- Create: `tests/conftest.py` (fixture data dir)

- [ ] **Step 1: Create `tests/conftest.py` with a tiny fixture data dir**

```python
import json
import os
from pathlib import Path

import pandas as pd
import pytest
import yaml


@pytest.fixture(autouse=True)
def _fixture_data_dir(tmp_path, monkeypatch):
    """Each test gets a fresh data dir with minimal nodes + 2 months of timeseries."""
    d = tmp_path / "data"
    d.mkdir()
    (d / "timeseries").mkdir()
    (d / "overlays" / "ndvi").mkdir(parents=True)
    (d / "scenarios").mkdir()

    # nodes
    gj = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [33.0, 0.4]},
             "properties": {"id": "lake_victoria_outlet", "name": "L. Victoria",
                            "type": "source", "country": "UG",
                            "upstream": [], "downstream": ["gerd"]}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [35.1, 11.2]},
             "properties": {"id": "gerd", "name": "GERD",
                            "type": "reservoir", "country": "ET",
                            "upstream": ["lake_victoria_outlet"], "downstream": []}},
        ],
    }
    (d / "nodes.geojson").write_text(json.dumps(gj))

    cfg = {
        "nodes": {
            "lake_victoria_outlet": {"type": "source", "catchment_area_km2": 100000, "catchment_scale": 1.0},
            "gerd": {"type": "reservoir", "storage_capacity_mcm": 74000, "storage_min_mcm": 14800,
                     "surface_area_km2_at_full": 1874, "initial_storage_mcm": 14800,
                     "hep": {"nameplate_mw": 6450, "head_m": 133, "efficiency": 0.9}},
        },
        "reaches": {},
    }
    (d / "node_config.yaml").write_text(yaml.safe_dump(cfg))

    # 2-month parquets
    for nid in ("lake_victoria_outlet", "gerd"):
        df = pd.DataFrame({
            "month": pd.date_range("2020-01-01", periods=2, freq="MS"),
            "precip_mm": [50.0, 60.0], "temp_c": [25.0, 26.0],
            "radiation_mj_m2": [20.0, 22.0], "wind_ms": [2.0, 2.1],
            "dewpoint_c": [15.0, 16.0], "pet_mm": [150.0, 160.0],
            "runoff_mm": [10.0, 12.0], "historical_discharge_m3s": pd.NA,
        })
        df.to_parquet(d / "timeseries" / f"{nid}.parquet", index=False)

    # 2-month NDVI
    ndf = pd.DataFrame({
        "month": pd.date_range("2020-01-01", periods=2, freq="MS"),
        "ndvi_mean": [0.3, 0.4], "ndvi_std": [0.05, 0.06], "valid_pixel_frac": [0.9, 0.85],
    })
    ndf.to_parquet(d / "overlays" / "ndvi" / "gezira.parquet", index=False)

    monkeypatch.setenv("NILE_DATA_DIR", str(d))
    # Force api.deps to re-read
    import api.deps as deps
    deps.DATA_DIR = d
    deps.nodes_geojson.cache_clear()
    deps.node_config.cache_clear()
    yield d
```

- [ ] **Step 2: Write the failing test**

`tests/test_nodes_route.py`:

```python
from fastapi.testclient import TestClient

from api.app import create_app


def test_list_nodes_returns_geojson():
    r = TestClient(create_app()).get("/nodes")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 2


def test_get_single_node_config():
    r = TestClient(create_app()).get("/nodes/gerd")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "gerd"
    assert body["type"] == "reservoir"
    assert body["storage_capacity_mcm"] == 74000


def test_get_unknown_node_404():
    r = TestClient(create_app()).get("/nodes/does_not_exist")
    assert r.status_code == 404


def test_timeseries_route():
    r = TestClient(create_app()).get(
        "/nodes/lake_victoria_outlet/timeseries?start=2020-01&end=2020-02&vars=precip_mm,pet_mm"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == ["2020-01", "2020-02"]
    assert body["values"]["precip_mm"] == [50.0, 60.0]
    assert body["values"]["pet_mm"] == [150.0, 160.0]
    assert "temp_c" not in body["values"]  # not requested
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_nodes_route.py -v
```

Expected: 404 for all routes (route not registered).

- [ ] **Step 4: Implement `api/routes/nodes.py`**

```python
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from api.deps import DATA_DIR, node_config, nodes_geojson

router = APIRouter()


@router.get("/nodes")
def list_nodes():
    return nodes_geojson()


@router.get("/nodes/{node_id}")
def get_node(node_id: str):
    cfg = node_config()["nodes"]
    if node_id not in cfg:
        raise HTTPException(status_code=404, detail=f"unknown node: {node_id}")
    return {"id": node_id, **cfg[node_id]}


@router.get("/nodes/{node_id}/timeseries")
def get_timeseries(
    node_id: str,
    start: str = Query(default="2005-01", regex=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2024-12", regex=r"^\d{4}-\d{2}$"),
    vars: str | None = Query(default=None),
):
    p = DATA_DIR / "timeseries" / f"{node_id}.parquet"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"no timeseries for {node_id}")
    df = pd.read_parquet(p)
    df["month"] = pd.to_datetime(df["month"])
    df = df[(df["month"] >= f"{start}-01") & (df["month"] <= f"{end}-01")]
    requested = [v.strip() for v in vars.split(",")] if vars else [
        c for c in df.columns if c != "month"
    ]
    return {
        "month": df["month"].dt.strftime("%Y-%m").tolist(),
        "values": {v: df[v].where(df[v].notna(), None).tolist() for v in requested if v in df.columns},
    }
```

- [ ] **Step 5: Register in `api/app.py`**

```python
from api.routes import health, nodes

# ... in create_app():
    app.include_router(health.router)
    app.include_router(nodes.router)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_nodes_route.py -v
```

Expected: all 4 pass.

- [ ] **Step 7: Commit**

```bash
git add api/routes/nodes.py api/app.py tests/test_nodes_route.py tests/conftest.py
git commit -m "L3: /nodes, /nodes/{id}, /nodes/{id}/timeseries"
```

---

## Task 3: Overlays route

**Files:**
- Create: `api/routes/overlays.py`
- Create: `tests/test_overlays_route.py`

- [ ] **Step 1: Write the failing test**

`tests/test_overlays_route.py`:

```python
from fastapi.testclient import TestClient

from api.app import create_app


def test_ndvi_overlay_returns_columns():
    r = TestClient(create_app()).get("/overlays/ndvi/gezira?start=2020-01&end=2020-02")
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == ["2020-01", "2020-02"]
    assert "ndvi_mean" in body["values"]
    assert body["values"]["ndvi_mean"] == [0.3, 0.4]
```

- [ ] **Step 2: Implement `api/routes/overlays.py`**

```python
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from api.deps import DATA_DIR

router = APIRouter()


@router.get("/overlays/ndvi/{zone_id}")
def get_ndvi(
    zone_id: str,
    start: str = Query(default="2005-01", regex=r"^\d{4}-\d{2}$"),
    end: str = Query(default="2024-12", regex=r"^\d{4}-\d{2}$"),
):
    p = DATA_DIR / "overlays" / "ndvi" / f"{zone_id}.parquet"
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"no NDVI for {zone_id}")
    df = pd.read_parquet(p)
    df["month"] = pd.to_datetime(df["month"])
    df = df[(df["month"] >= f"{start}-01") & (df["month"] <= f"{end}-01")]
    return {
        "month": df["month"].dt.strftime("%Y-%m").tolist(),
        "values": {c: df[c].tolist() for c in ("ndvi_mean", "ndvi_std", "valid_pixel_frac")},
    }
```

- [ ] **Step 3: Register + test + commit**

Add `overlays.router` to `api/app.py`. Run `pytest tests/test_overlays_route.py -v` and commit.

---

## Task 4: Scenario store (file-backed CRUD)

**Files:**
- Create: `api/scenario_store.py`
- Create: `tests/test_scenario_store.py`

- [ ] **Step 1: Write the failing test**

`tests/test_scenario_store.py`:

```python
from api.scenario_store import ScenarioStore
from simengine.scenario import Scenario, Policy, Weights


def _sample_scenario(name="t") -> Scenario:
    return Scenario(name=name, period=["2005-01", "2024-12"],
                    policy=Policy(weights=Weights(water=0.4, food=0.3, energy=0.3)))


def test_save_and_list():
    store = ScenarioStore()
    s = _sample_scenario()
    store.save(s)
    ids = [row["id"] for row in store.list()]
    assert s.id in ids


def test_save_and_load():
    store = ScenarioStore()
    s = _sample_scenario()
    store.save(s)
    loaded = store.load(s.id)
    assert loaded.name == s.name


def test_delete():
    store = ScenarioStore()
    s = _sample_scenario()
    store.save(s)
    store.delete(s.id)
    assert all(row["id"] != s.id for row in store.list())
```

- [ ] **Step 2: Implement `api/scenario_store.py`**

```python
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from api.deps import DATA_DIR
from simengine.scenario import Scenario


class ScenarioStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else DATA_DIR / "scenarios"
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, s: Scenario) -> Scenario:
        s.to_file(self.root / f"{s.id}.json")
        return s

    def load(self, scenario_id: str) -> Scenario:
        p = self.root / f"{scenario_id}.json"
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"unknown scenario: {scenario_id}")
        return Scenario.from_file(p)

    def list(self) -> list[dict]:
        out = []
        for p in sorted(self.root.glob("*.json")):
            s = Scenario.from_file(p)
            out.append({
                "id": s.id, "name": s.name, "created_at": s.created_at,
                "score": s.results.score if s.results else None,
                "period": s.period,
            })
        return out

    def delete(self, scenario_id: str) -> None:
        p = self.root / f"{scenario_id}.json"
        if p.exists():
            p.unlink()
```

- [ ] **Step 3: Run, commit**

```bash
pytest tests/test_scenario_store.py -v
git add api/scenario_store.py tests/test_scenario_store.py
git commit -m "L3: file-backed scenario store"
```

---

## Task 5: Stub sim (Saturday 17:00 deliverable)

**Files:**
- Create: `api/stub_sim.py`
- Create: `api/routes/scenarios.py` (stub version)

- [ ] **Step 1: Create the stub sim**

`api/stub_sim.py`:

```python
"""Returns fake but realistic scenario results — used by /scenarios/run until
L2 ships. Lets L4 build the dashboard against the final JSON shape on Saturday."""
from __future__ import annotations

import random

import pandas as pd

from simengine.scenario import Scenario, ScenarioResults


def fake_run(scenario: Scenario) -> Scenario:
    start, end = scenario.period
    months = pd.date_range(f"{start}-01", f"{end}-01", freq="MS").strftime("%Y-%m").tolist()
    rnd = random.Random(hash(scenario.name) & 0xFFFFFFFF)

    # Fake per-node timeseries for 2 nodes so the dashboard can inspect
    ts = {
        "gerd": [{"month": m, "storage_mcm": 50000 + 5000 * ((i % 12) - 6),
                  "release_m3s": 1500 + rnd.randint(-200, 200),
                  "inflow_m3s": 1600, "evap_mcm": 80, "energy_gwh": 300 + rnd.randint(-50, 50)}
                 for i, m in enumerate(months)],
        "aswan": [{"month": m, "storage_mcm": 100000, "release_m3s": 1800,
                   "inflow_m3s": 1850, "evap_mcm": 1200, "energy_gwh": 160}
                  for m in months],
    }
    kpi = [{"month": m, "water_served_pct": 0.92 + rnd.uniform(-0.05, 0.05),
            "food_tonnes": 1_000_000 + rnd.randint(-100_000, 100_000),
            "energy_gwh": 450 + rnd.randint(-30, 30)}
           for m in months]

    scenario.results = ScenarioResults(
        timeseries_per_node=ts, kpi_monthly=kpi,
        score=0.72, score_breakdown={"water": 0.9, "food": 0.6, "energy": 0.7, "delta_penalty": 0.0},
    )
    return scenario
```

- [ ] **Step 2: Create the scenarios route using the stub**

`api/routes/scenarios.py`:

```python
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from api.deps import DATA_DIR
from api.scenario_store import ScenarioStore
from api.stub_sim import fake_run
from simengine.scenario import Scenario

router = APIRouter()
_store = ScenarioStore()


def _run(scenario: Scenario) -> Scenario:
    """Switch between stub and real sim via env."""
    if os.environ.get("NILE_USE_REAL_SIM") == "1":
        from simengine.engine import run as real_run
        return real_run(scenario,
                        config_path=DATA_DIR / "node_config.yaml",
                        geojson_path=DATA_DIR / "nodes.geojson",
                        timeseries_dir=DATA_DIR / "timeseries")
    return fake_run(scenario)


@router.post("/scenarios/run")
def run_scenario(scenario: Scenario):
    return _run(scenario).model_dump()


@router.get("/scenarios")
def list_scenarios():
    return _store.list()


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    return _store.load(scenario_id).model_dump()


@router.post("/scenarios/{scenario_id}/save")
def save_scenario(scenario_id: str, scenario: Scenario):
    if scenario.id != scenario_id:
        raise HTTPException(status_code=400, detail="id mismatch")
    return _store.save(scenario).model_dump()


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: str):
    _store.delete(scenario_id)
    return None
```

- [ ] **Step 3: Write the failing test**

`tests/test_scenarios_route.py`:

```python
from fastapi.testclient import TestClient

from api.app import create_app


def _sample_body():
    return {"name": "t", "period": ["2020-01", "2020-03"],
            "policy": {"reservoirs": {}, "demands": {}, "constraints": {},
                       "weights": {"water": 0.4, "food": 0.3, "energy": 0.3}}}


def test_run_returns_results():
    client = TestClient(create_app())
    r = client.post("/scenarios/run", json=_sample_body())
    assert r.status_code == 200
    body = r.json()
    assert body["results"] is not None
    assert len(body["results"]["kpi_monthly"]) == 3
    assert "score" in body["results"]


def test_save_and_list_and_load():
    client = TestClient(create_app())
    ran = client.post("/scenarios/run", json=_sample_body()).json()
    # Promote to saved
    saved = client.post(f"/scenarios/{ran['id']}/save", json=ran).json()
    assert saved["id"] == ran["id"]

    listed = client.get("/scenarios").json()
    assert any(row["id"] == ran["id"] for row in listed)

    loaded = client.get(f"/scenarios/{ran['id']}").json()
    assert loaded["name"] == "t"


def test_delete():
    client = TestClient(create_app())
    ran = client.post("/scenarios/run", json=_sample_body()).json()
    client.post(f"/scenarios/{ran['id']}/save", json=ran)
    r = client.delete(f"/scenarios/{ran['id']}")
    assert r.status_code == 204
```

- [ ] **Step 4: Register the router, run tests, commit**

In `api/app.py`:

```python
from api.routes import health, nodes, overlays, scenarios
# ... in create_app():
    app.include_router(scenarios.router)
```

```bash
pytest tests/test_scenarios_route.py -v
git add api/stub_sim.py api/routes/scenarios.py api/app.py tests/test_scenarios_route.py
git commit -m "L3: stubbed /scenarios/run + full CRUD"
```

- [ ] **Step 5: Publish stub API for L4**

Post to team chat (by Sat 17:00):
```
L3 stub API ready. Contract:
- GET  /health
- GET  /nodes, /nodes/{id}, /nodes/{id}/timeseries
- GET  /overlays/ndvi/{zone_id}
- POST /scenarios/run  (echoes back with fake results, 3-key score_breakdown)
- GET  /scenarios  POST /scenarios/{id}/save  DELETE /scenarios/{id}
All JSON shapes are final — real sim wires in Sunday AM, contract will not change.
Start it locally with:  NILE_DATA_DIR=/path/to/stub/data python -m api
```

---

## Task 6: Compare endpoint

**Files:**
- Modify: `api/routes/scenarios.py`

- [ ] **Step 1: Add the test**

Append to `tests/test_scenarios_route.py`:

```python
def test_compare_two_scenarios():
    client = TestClient(create_app())
    a = client.post("/scenarios/run", json=_sample_body()).json()
    b_body = _sample_body(); b_body["name"] = "t2"
    b = client.post("/scenarios/run", json=b_body).json()
    client.post(f"/scenarios/{a['id']}/save", json=a)
    client.post(f"/scenarios/{b['id']}/save", json=b)

    r = client.post("/scenarios/compare", json={"scenario_ids": [a["id"], b["id"]]})
    assert r.status_code == 200
    body = r.json()
    assert set(body["scenarios"].keys()) == {a["id"], b["id"]}
    assert "kpi_deltas" in body
    assert "score_delta" in body
    # 3 months
    assert len(body["kpi_deltas"]) == 3
```

- [ ] **Step 2: Append to `api/routes/scenarios.py`**

```python
from pydantic import BaseModel


class CompareRequest(BaseModel):
    scenario_ids: list[str]


@router.post("/scenarios/compare")
def compare_scenarios(req: CompareRequest):
    if len(req.scenario_ids) != 2:
        raise HTTPException(status_code=400, detail="need exactly 2 scenario_ids")
    a = _store.load(req.scenario_ids[0])
    b = _store.load(req.scenario_ids[1])
    if not (a.results and b.results):
        raise HTTPException(status_code=400, detail="both scenarios must have results")

    # Align on month (assume both share the same months; else outer-join)
    a_by_m = {r["month"]: r for r in a.results.kpi_monthly}
    b_by_m = {r["month"]: r for r in b.results.kpi_monthly}
    months = sorted(set(a_by_m) | set(b_by_m))
    deltas = []
    for m in months:
        ra = a_by_m.get(m, {"water_served_pct": 0, "food_tonnes": 0, "energy_gwh": 0})
        rb = b_by_m.get(m, {"water_served_pct": 0, "food_tonnes": 0, "energy_gwh": 0})
        deltas.append({
            "month": m,
            "water_served_pct": rb["water_served_pct"] - ra["water_served_pct"],
            "food_tonnes": rb["food_tonnes"] - ra["food_tonnes"],
            "energy_gwh": rb["energy_gwh"] - ra["energy_gwh"],
        })

    return {
        "scenarios": {a.id: {"name": a.name, "score": a.results.score},
                      b.id: {"name": b.name, "score": b.results.score}},
        "kpi_deltas": deltas,
        "score_delta": (b.results.score or 0) - (a.results.score or 0),
    }
```

- [ ] **Step 3: Run, commit**

```bash
pytest tests/test_scenarios_route.py -v
git add api/routes/scenarios.py tests/test_scenarios_route.py
git commit -m "L3: /scenarios/compare endpoint"
```

---

## Task 7: Wire real sim (Sunday AM)

**Files:**
- Modify: `api/routes/scenarios.py` (already has the switch via `NILE_USE_REAL_SIM`)
- Modify: `api/app.py` or `api/__main__.py` to default to real when data/ has the full 18 nodes

- [ ] **Step 1: Ensure the env switch works**

```bash
# With stub data + default (stub sim):
NILE_DATA_DIR=data python -m api &
curl -s -X POST http://localhost:8000/scenarios/run \
  -H 'Content-Type: application/json' \
  -d '{"name":"t","period":["2005-01","2005-03"],
       "policy":{"reservoirs":{},"demands":{},"constraints":{},
                 "weights":{"water":0.4,"food":0.3,"energy":0.3}}}' \
  | python -c "import json,sys; print(json.load(sys.stdin)['results']['score'])"
# Expect: 0.72 (the stub's fixed score)
kill %1
```

- [ ] **Step 2: Switch to real sim and re-run**

```bash
NILE_DATA_DIR=data NILE_USE_REAL_SIM=1 python -m api &
curl -s -X POST http://localhost:8000/scenarios/run \
  -H 'Content-Type: application/json' \
  -d '{"name":"t","period":["2005-01","2005-03"],
       "policy":{"reservoirs":{},"demands":{},"constraints":{},
                 "weights":{"water":0.4,"food":0.3,"energy":0.3}}}' \
  | python -c "import json,sys; body=json.load(sys.stdin); print('score', body['results']['score']); print('nodes', len(body['results']['timeseries_per_node']))"
kill %1
```

Expected: score is a new real number; `nodes` matches the count in L1's config (18 in production, 4 against stubs).

- [ ] **Step 3: Commit empty marker**

```bash
git commit --allow-empty -m "L3: real sim switch verified against live data"
```

---

## Task 8: Dockerfile + docker-compose

**Files:**
- Create: `Dockerfile.api`
- Create: `docker-compose.yml`

- [ ] **Step 1: Write `Dockerfile.api`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal-dev libproj-dev gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . --no-deps && pip install --no-cache-dir \
      fastapi uvicorn[standard] pydantic pyyaml pandas pyarrow numpy typer xarray

COPY api/ api/
COPY simengine/ simengine/

ENV NILE_DATA_DIR=/data
ENV NILE_USE_REAL_SIM=1
EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Write `docker-compose.yml`**

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data:ro
    environment:
      - NILE_USE_REAL_SIM=1
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.frontend
    ports:
      - "5173:80"
    environment:
      - VITE_API_BASE=http://localhost:8000
    depends_on:
      - api
```

- [ ] **Step 3: Build + smoke test**

```bash
docker compose build api
docker compose up -d api
sleep 3
curl -s http://localhost:8000/health
curl -s http://localhost:8000/nodes | python -c "import json,sys; print(len(json.load(sys.stdin)['features']),'nodes')"
docker compose down
```

Expected: `{"status":"ok"}`, N nodes.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile.api docker-compose.yml
git commit -m "L3: Dockerfile + docker-compose (API + frontend placeholder)"
```

---

## Task 9: Optimizer stretch endpoint

**Files:**
- Create: `api/routes/optimize.py`

- [ ] **Step 1: Implement background-task skeleton**

```python
from __future__ import annotations

import uuid
from threading import Lock
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from simengine.scenario import Scenario

router = APIRouter()
_jobs: dict[str, dict[str, Any]] = {}
_lock = Lock()


@router.post("/optimize")
def start_optimize(scenario: Scenario, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {"status": "pending", "best": None, "progress": 0.0}
    bg.add_task(_run_optimizer, job_id, scenario)
    return {"job_id": job_id}


@router.get("/optimize/{job_id}")
def poll_optimize(job_id: str):
    with _lock:
        if job_id not in _jobs:
            raise HTTPException(status_code=404)
        return _jobs[job_id]


def _run_optimizer(job_id: str, scenario: Scenario) -> None:
    """Delegates to L5's grid_search if importable; else marks unimplemented."""
    try:
        from optimize.grid_search import search
    except ImportError:
        with _lock:
            _jobs[job_id] = {"status": "unimplemented", "best": None, "progress": 1.0}
        return
    for update in search(scenario):                 # yields dicts with progress + best
        with _lock:
            _jobs[job_id].update(update)
    with _lock:
        _jobs[job_id]["status"] = "done"
```

- [ ] **Step 2: Register + commit**

Add router in `api/app.py`. No tests (stretch); smoke-test manually once L5 provides `optimize/grid_search.py`.

```bash
git add api/routes/optimize.py api/app.py
git commit -m "L3: /optimize stretch endpoint (delegates to L5)"
```

---

## L3 Success Criteria

1. `pytest tests/` all green.
2. Sat 17:00 — stub API reachable at http://localhost:8000, L4 wiring against final JSON shape.
3. Sun 10:00 — `NILE_USE_REAL_SIM=1` flip succeeds with no frontend changes required.
4. `docker compose up` spins API + frontend, dashboard loads at http://localhost:5173.
5. `/health`, `/nodes`, `/nodes/{id}/timeseries`, `/overlays/ndvi/{zone_id}`, `/scenarios/run`, `/scenarios`, `/scenarios/{id}`, `/scenarios/{id}/save`, `/scenarios/compare`, `DELETE /scenarios/{id}` all return valid JSON against the contract.

## Explicit non-goals for L3

- No auth, no rate limiting, no DB.
- No async job queue beyond the single-process `BackgroundTasks` for optimize.
- No scenario versioning — save overwrites by id.
- No OpenAPI customization beyond what FastAPI gives us for free.
- No websocket / streaming.
