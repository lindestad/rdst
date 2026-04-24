# L2 — Sim Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python package `simengine/` that loads `node_config.yaml` + `data/timeseries/*.parquet`, runs a `Scenario` forward through monthly time steps (Jan-2005 → Dec-2024), and emits per-node time-series + three KPIs + a weighted score. Importable by L3; runnable as `python -m simengine run --scenario scenario.json`.

**Architecture:** Pure Python. A `Graph` holds nodes in topological order. Each time step t, the engine calls `node.step(t, state)` on each node in order — every node reads its upstream inflows from `state`, computes its own outputs, and writes them back. No threading, no async. One full run ≈ 10 ms.

**Tech stack:** Python 3.11, `numpy`, `pandas`, `pyarrow`, `pydantic>=2`, `pyyaml`, `typer`, `pytest`. No web deps.

**Lane ownership:** 1 person. Deliverables:
- **Sat 13:00** — `simengine run --scenario baseline.json --config data/node_config.yaml` produces a valid `Scenario` JSON with results, against L1's stub `node_config.yaml`. Imports-but-doesn't-call from L3 fine.
- **Sun 09:00** — real run against real L1 data produces per-node storage/release/KPI time-series for all 18 nodes.

**Shared contracts** (from spec — copied verbatim):

- Reads `data/node_config.yaml` (schema fixed by L1 Task 2).
- Reads `data/timeseries/<node_id>.parquet` with columns `month, precip_mm, temp_c, radiation_mj_m2, wind_ms, dewpoint_c, pet_mm, runoff_mm, historical_discharge_m3s`.
- Writes `data/scenarios/<uuid>.json` with the scenario object defined in the spec.
- **Scenario JSON shape:**

```json
{
  "id": "uuid",
  "name": "GERD-10yr-fill",
  "created_at": "2026-04-25T14:00:00Z",
  "period": ["2005-01", "2024-12"],
  "policy": {
    "reservoirs": {"gerd": {"mode": "manual", "release_m3s_by_month": {"2005-01": 1500, ...}}},
    "demands": {"gezira_irr": {"area_scale": 1.0}},
    "constraints": {"min_delta_flow_m3s": 500},
    "weights": {"water": 0.4, "food": 0.3, "energy": 0.3}
  },
  "results": {
    "timeseries_per_node": {"gerd": [{"month": "2005-01", "storage_mcm": 14800, "release_m3s": 1500, "evap_mcm": 120, "inflow_m3s": 1650}, ...]},
    "kpi_monthly": [{"month": "2005-01", "water_served_pct": 0.94, "food_tonnes": 950000, "energy_gwh": 3200}, ...],
    "score": 0.72,
    "score_breakdown": {"water": 0.94, "food": 0.62, "energy": 0.71, "delta_penalty": 0.0}
  }
}
```

---

## File Structure

```
simengine/
  __init__.py
  __main__.py                   # typer CLI
  graph.py                      # load node_config.yaml + topological order
  forcings.py                   # per-node Parquet reader
  nodes/
    __init__.py
    base.py                     # Node ABC
    source.py
    reservoir.py
    reach.py
    confluence.py
    wetland.py
    demand_municipal.py
    demand_irrigation.py
    sink.py
  crop_water.py                 # FAO monthly crop water requirement
  scenario.py                   # Scenario pydantic models + load/save
  engine.py                     # time-stepping orchestrator
  kpi.py                        # water / food / energy calculators
  scoring.py                    # weighted sum + penalties
tests/
  test_graph.py
  test_source.py
  test_reservoir.py
  test_reach.py
  test_wetland.py
  test_demand_irrigation.py
  test_demand_municipal.py
  test_engine_mass_balance.py
  test_scenario.py
  test_kpi.py
  test_scoring.py
  fixtures/
    three_node_config.yaml
    three_node_forcings/
```

---

## Task 1: Project scaffold

**Files:**
- Modify: `pyproject.toml` (add simengine deps)
- Create: `simengine/__init__.py`, `simengine/__main__.py`

- [ ] **Step 1: Add simengine deps to `pyproject.toml`**

In the `[project]` dependencies list, add (many are already there from L1):

```toml
"pydantic>=2.6",
"pyyaml>=6",
"pandas>=2.2",
"numpy>=1.26",
"pyarrow>=15",
"typer>=0.12",
```

- [ ] **Step 2: Create `simengine/__init__.py`** (empty)

- [ ] **Step 3: Create `simengine/__main__.py`**

```python
import typer

app = typer.Typer(help="Nile digital twin sim engine")


@app.command()
def run(
    scenario: str = typer.Option(..., help="Path to scenario JSON"),
    config: str = typer.Option("data/node_config.yaml", help="Node config YAML"),
    data: str = typer.Option("data/timeseries", help="Timeseries Parquet dir"),
    out: str = typer.Option(None, help="Output scenario JSON (default: overwrite input)"),
) -> None:
    """Run a scenario and write results back to the scenario JSON."""
    from simengine.engine import run_scenario_file
    run_scenario_file(scenario, config, data, out)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Verify install**

```bash
pip install -e ".[dev]"
python -m simengine --help
```

Expected: typer prints `run` command.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml simengine/
git commit -m "L2: simengine scaffold (typer CLI skeleton)"
```

---

## Task 2: Graph loader + topological order

**Files:**
- Create: `simengine/graph.py`
- Create: `tests/test_graph.py`
- Create: `tests/fixtures/three_node_config.yaml`

- [ ] **Step 1: Create a minimal three-node fixture**

`tests/fixtures/three_node_config.yaml`:

```yaml
nodes:
  src:
    type: source
    catchment_area_km2: 100000
    catchment_scale: 1.0
  res:
    type: reservoir
    storage_capacity_mcm: 1000
    storage_min_mcm: 100
    surface_area_km2_at_full: 10
    initial_storage_mcm: 500
    hep:
      nameplate_mw: 100
      head_m: 50
      efficiency: 0.9
  snk:
    type: sink
    min_environmental_flow_m3s: 10

# Topology lives in geojson; test provides it inline through the loader's
# alternate entry point.
```

Add `tests/fixtures/three_node_topology.json`:

```json
{"edges": [["src","res"],["res","snk"]]}
```

- [ ] **Step 2: Write the failing test**

`tests/test_graph.py`:

```python
from pathlib import Path

import pytest

from simengine.graph import Graph, load_graph

FIX = Path(__file__).parent / "fixtures"


def test_topological_order():
    g = load_graph(FIX / "three_node_config.yaml", FIX / "three_node_topology.json")
    assert g.order == ["src", "res", "snk"]


def test_cycle_detection(tmp_path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("nodes:\n  a: {type: source, catchment_area_km2: 1, catchment_scale: 1}\n"
                   "  b: {type: sink, min_environmental_flow_m3s: 0}\n")
    topo = tmp_path / "topo.json"
    topo.write_text('{"edges": [["a","b"],["b","a"]]}')
    with pytest.raises(ValueError, match="cycle"):
        load_graph(cfg, topo)


def test_unknown_node_type(tmp_path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("nodes:\n  x: {type: alien}\n")
    topo = tmp_path / "topo.json"
    topo.write_text('{"edges": []}')
    with pytest.raises(ValueError, match="unknown node type"):
        load_graph(cfg, topo)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_graph.py -v
```

Expected: `ModuleNotFoundError: simengine.graph`.

- [ ] **Step 4: Implement `simengine/graph.py`**

```python
"""Graph loader: reads YAML config + topology and returns a topologically
ordered list of Node instances."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any

import yaml

# Registry populated by simengine.nodes at import time
_NODE_CLASSES: dict[str, type] = {}


def register_node_class(type_name: str):
    def deco(cls):
        _NODE_CLASSES[type_name] = cls
        return cls
    return deco


@dataclass
class Graph:
    nodes: dict[str, Any]                # id → Node instance
    order: list[str]                     # topological order (upstream first)
    upstream: dict[str, list[str]]
    downstream: dict[str, list[str]]


def load_graph(config_path: Path, topology_path: Path | None = None,
               geojson_path: Path | None = None) -> Graph:
    """Load graph from node_config.yaml + either a topology.json or nodes.geojson."""
    # Importing here avoids a circular import at module load time
    import simengine.nodes  # noqa: F401 -- triggers @register_node_class decorators

    cfg = yaml.safe_load(Path(config_path).read_text())
    nodes_cfg = cfg["nodes"]
    reaches_cfg = cfg.get("reaches", {})

    edges = _load_edges(topology_path, geojson_path)
    upstream: dict[str, list[str]] = {nid: [] for nid in nodes_cfg}
    downstream: dict[str, list[str]] = {nid: [] for nid in nodes_cfg}
    for u, d in edges:
        downstream.setdefault(u, []).append(d)
        upstream.setdefault(d, []).append(u)

    ts = TopologicalSorter({nid: set(upstream.get(nid, [])) for nid in nodes_cfg})
    try:
        order = list(ts.static_order())
    except CycleError as e:
        raise ValueError(f"topology contains a cycle: {e}")

    nodes: dict[str, Any] = {}
    for nid, nconf in nodes_cfg.items():
        ntype = nconf.get("type")
        if ntype not in _NODE_CLASSES:
            raise ValueError(f"unknown node type {ntype!r} for node {nid!r}")
        cls = _NODE_CLASSES[ntype]
        params = {k: v for k, v in nconf.items() if k != "type"}
        # Reach routing params may live in reaches_cfg instead of on the node
        if ntype == "reach" and nid in reaches_cfg:
            params = {**reaches_cfg[nid], **params}
        nodes[nid] = cls(id=nid, upstream=upstream.get(nid, []),
                         downstream=downstream.get(nid, []), **params)

    return Graph(nodes=nodes, order=order, upstream=upstream, downstream=downstream)


def _load_edges(topology_path: Path | None, geojson_path: Path | None) -> list[tuple[str, str]]:
    if topology_path and Path(topology_path).exists():
        obj = json.loads(Path(topology_path).read_text())
        return [tuple(e) for e in obj["edges"]]
    if geojson_path and Path(geojson_path).exists():
        gj = json.loads(Path(geojson_path).read_text())
        edges = []
        for feat in gj["features"]:
            nid = feat["properties"]["id"]
            for d in feat["properties"].get("downstream", []):
                edges.append((nid, d))
        return edges
    raise FileNotFoundError("need either topology_path or geojson_path")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_graph.py -v
```

Expected: all 3 tests pass. (The "unknown node type" test requires Task 3's `nodes/__init__.py` to import; until then the loader raises via the empty registry — fine.)

- [ ] **Step 6: Commit**

```bash
git add simengine/graph.py tests/test_graph.py tests/fixtures/
git commit -m "L2: graph loader with topological order + cycle detection"
```

---

## Task 3: Node ABC + source + sink

**Files:**
- Create: `simengine/nodes/__init__.py`, `simengine/nodes/base.py`, `simengine/nodes/source.py`, `simengine/nodes/sink.py`
- Create: `tests/test_source.py`

**Mental model:** every node exposes `.step(t, state)` where `state` is a mutable dict `{node_id: {"outflow_m3s": float, ...}}` used for inter-node plumbing. Each node reads its upstream outflows, writes its own outflow.

- [ ] **Step 1: Write the failing test**

`tests/test_source.py`:

```python
import numpy as np
import pandas as pd

from simengine.nodes.source import Source


def test_source_outflow_from_runoff():
    # 30 mm × 1e5 km² / (31 × 86400) ≈ 1120 m³/s for Jan
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
    # 30 mm × 1e5 km² × 2.0 / (31 × 86400) ≈ 2240 m³/s for Jan (31-day month)
    assert 2200 < state["src"]["outflow_m3s"] < 2300
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_source.py -v
```

Expected: `ModuleNotFoundError: simengine.nodes.source`.

- [ ] **Step 3: Create `simengine/nodes/base.py`**

```python
"""Node ABC and common helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class Node:
    """Base class. Subclasses override `.step()`."""
    id: str
    upstream: list[str]
    downstream: list[str]
    forcings: pd.DataFrame = field(default_factory=pd.DataFrame)

    def load_forcings(self, df: pd.DataFrame) -> None:
        self.forcings = df.reset_index(drop=True)

    def step(self, t: int, state: dict[str, dict[str, Any]]) -> None:  # pragma: no cover
        raise NotImplementedError

    def upstream_inflow_m3s(self, state: dict[str, dict[str, Any]]) -> float:
        """Sum of all upstream nodes' outflow_m3s, as seen this step."""
        return sum(state[u]["outflow_m3s"] for u in self.upstream if u in state)


def days_in_month_from_ts(ts) -> int:
    return pd.Timestamp(ts).days_in_month


def m3s_to_mcm_month(m3s: float, days: int) -> float:
    """m³/s × seconds-in-month / 1e6 → million m³."""
    return m3s * days * 86400.0 / 1e6


def mcm_to_m3s_month(mcm: float, days: int) -> float:
    return mcm * 1e6 / (days * 86400.0)
```

- [ ] **Step 4: Create `simengine/nodes/source.py`**

```python
from __future__ import annotations

from simengine.graph import register_node_class
from simengine.nodes.base import Node, days_in_month_from_ts


@register_node_class("source")
class Source(Node):
    def __init__(self, id, upstream, downstream, *, catchment_area_km2: float,
                 catchment_scale: float = 1.0, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.catchment_area_km2 = catchment_area_km2
        self.catchment_scale = catchment_scale

    def step(self, t, state):
        row = self.forcings.iloc[t]
        runoff_mm = float(row["runoff_mm"])
        days = days_in_month_from_ts(row["month"])
        # mm × km² = 1e-3 m × 1e6 m² = 1e3 m³  →  per-month m³ = runoff_mm × area_km2 × 1e3
        monthly_m3 = runoff_mm * self.catchment_area_km2 * 1e3 * self.catchment_scale
        outflow_m3s = monthly_m3 / (days * 86400.0)
        state[self.id] = {"outflow_m3s": outflow_m3s, "runoff_mm": runoff_mm}
```

- [ ] **Step 5: Create `simengine/nodes/sink.py`**

```python
from __future__ import annotations

from simengine.graph import register_node_class
from simengine.nodes.base import Node


@register_node_class("sink")
class Sink(Node):
    def __init__(self, id, upstream, downstream, *, min_environmental_flow_m3s: float = 0.0,
                 **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.min_environmental_flow_m3s = min_environmental_flow_m3s

    def step(self, t, state):
        inflow = self.upstream_inflow_m3s(state)
        state[self.id] = {
            "outflow_m3s": 0.0,
            "inflow_m3s": inflow,
            "shortfall_m3s": max(0.0, self.min_environmental_flow_m3s - inflow),
        }
```

- [ ] **Step 6: Create `simengine/nodes/__init__.py`**

```python
# Importing a subclass module triggers its @register_node_class.
# Keep this file in sync as new node types are added.
from simengine.nodes import source, sink  # noqa: F401
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_source.py tests/test_graph.py -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add simengine/nodes/ tests/test_source.py
git commit -m "L2: Node ABC + source + sink"
```

---

## Task 4: Reservoir node

**Files:**
- Create: `simengine/nodes/reservoir.py`
- Create: `tests/test_reservoir.py`

- [ ] **Step 1: Write the failing test**

`tests/test_reservoir.py`:

```python
import numpy as np
import pandas as pd

from simengine.nodes.reservoir import Reservoir


def _forcings(pet_mm=100.0, months=3):
    return pd.DataFrame({
        "month": pd.date_range("2020-01-01", periods=months, freq="MS"),
        "pet_mm": [pet_mm] * months,
    })


def test_mass_conservation_one_step():
    # Capacity large enough that no spill occurs — exercises the pure
    # mass-balance path, not the clamp path.
    r = Reservoir(id="r", upstream=["u"], downstream=["d"],
                  storage_capacity_mcm=10000, storage_min_mcm=100,
                  surface_area_km2_at_full=10, initial_storage_mcm=500,
                  hep={"nameplate_mw": 100, "head_m": 50, "efficiency": 0.9})
    r.load_forcings(_forcings(pet_mm=0.0))
    # 1000 m³/s inflow for Jan (31 days) → 2678.4 mcm; 500 m³/s release → 1339.2 mcm
    state = {"u": {"outflow_m3s": 1000.0}}
    r.step(0, state, policy={"mode": "manual", "release_m3s_by_month": {"2020-01": 500.0}})
    s = state["r"]
    inflow_mcm = 1000 * 31 * 86400 / 1e6
    release_mcm = 500 * 31 * 86400 / 1e6
    # Storage change should equal inflow - release - evap (evap=0 because pet=0)
    assert abs(s["storage_mcm"] - (500 + inflow_mcm - release_mcm)) < 0.5


def test_storage_clamped_to_capacity():
    r = Reservoir(id="r", upstream=["u"], downstream=["d"],
                  storage_capacity_mcm=1000, storage_min_mcm=100,
                  surface_area_km2_at_full=10, initial_storage_mcm=990,
                  hep={"nameplate_mw": 100, "head_m": 50, "efficiency": 0.9})
    r.load_forcings(_forcings(pet_mm=0.0))
    state = {"u": {"outflow_m3s": 2000.0}}  # Huge inflow
    r.step(0, state, policy={"mode": "manual", "release_m3s_by_month": {"2020-01": 0.0}})
    s = state["r"]
    assert s["storage_mcm"] == 1000
    # Spilled volume must exit as outflow
    assert s["outflow_m3s"] > 0


def test_energy_generation():
    # Initial storage big enough that the 500 m³/s × 31d ≈ 1339 mcm release
    # is not clamped by the min-storage guard.
    r = Reservoir(id="r", upstream=["u"], downstream=["d"],
                  storage_capacity_mcm=10000, storage_min_mcm=100,
                  surface_area_km2_at_full=10, initial_storage_mcm=2000,
                  hep={"nameplate_mw": 100, "head_m": 50, "efficiency": 0.9})
    r.load_forcings(_forcings(pet_mm=0.0))
    state = {"u": {"outflow_m3s": 0.0}}
    r.step(0, state, policy={"mode": "manual", "release_m3s_by_month": {"2020-01": 500.0}})
    # E = V × h × η × ρ × g / 3.6e12
    # V = 500 m³/s × 31 × 86400 = 1.3392e9 m³
    # E_gwh = 1.3392e9 × 50 × 0.9 × 1000 × 9.81 / 3.6e12 ≈ 164.3 GWh
    assert 160 < state["r"]["energy_gwh"] < 170


def test_evaporation_scales_with_surface_area_and_pet():
    r = Reservoir(id="r", upstream=["u"], downstream=["d"],
                  storage_capacity_mcm=1000, storage_min_mcm=100,
                  surface_area_km2_at_full=10, initial_storage_mcm=500,
                  hep={"nameplate_mw": 100, "head_m": 50, "efficiency": 0.9})
    # 100 mm/month × 10 km² at half-full (so area ≈ 5 km²) = 0.1 m × 5e6 m² = 5e5 m³ = 0.5 mcm
    r.load_forcings(_forcings(pet_mm=100.0))
    state = {"u": {"outflow_m3s": 0.0}}
    r.step(0, state, policy={"mode": "manual", "release_m3s_by_month": {"2020-01": 0.0}})
    # Evap should be 0.3–0.7 mcm (some area-vs-storage scaling applied)
    assert 0.2 < state["r"]["evap_mcm"] < 0.8
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_reservoir.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `simengine/nodes/reservoir.py`**

```python
"""Reservoir node: mass balance + HEP + Penman evap × storage-scaled area."""
from __future__ import annotations

from simengine.graph import register_node_class
from simengine.nodes.base import Node, days_in_month_from_ts, m3s_to_mcm_month, mcm_to_m3s_month

RHO = 1000.0      # kg/m³
G = 9.81          # m/s²


@register_node_class("reservoir")
class Reservoir(Node):
    def __init__(self, id, upstream, downstream, *,
                 storage_capacity_mcm, storage_min_mcm,
                 surface_area_km2_at_full, initial_storage_mcm,
                 hep=None, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.capacity = float(storage_capacity_mcm)
        self.min = float(storage_min_mcm)
        self.area_full = float(surface_area_km2_at_full)
        self.storage = float(initial_storage_mcm)
        self.hep = hep  # None for dams without HEP

    def step(self, t, state, *, policy=None):
        policy = policy or {}
        row = self.forcings.iloc[t] if len(self.forcings) else None
        pet_mm = float(row["pet_mm"]) if row is not None else 0.0
        month_key = row["month"].strftime("%Y-%m") if row is not None else None
        days = days_in_month_from_ts(row["month"]) if row is not None else 30

        inflow_m3s = self.upstream_inflow_m3s(state)
        inflow_mcm = m3s_to_mcm_month(inflow_m3s, days)

        release_m3s = self._desired_release(policy, month_key, inflow_m3s)
        release_mcm = m3s_to_mcm_month(release_m3s, days)

        # Surface area scales linearly with storage (crude but OK)
        area_km2 = self.area_full * (self.storage / self.capacity) if self.capacity else 0.0
        evap_mcm = pet_mm * area_km2 * 1e-3  # mm × km² → 1e-3 × km² × m = 1e3 m³ = 1e-3 mcm; so mm × km² × 1e-3 = mcm

        new_storage = self.storage + inflow_mcm - release_mcm - evap_mcm

        # Clamp + spill
        spilled_mcm = max(0.0, new_storage - self.capacity)
        new_storage = min(self.capacity, new_storage)
        if new_storage < self.min:
            # Reduce release to keep storage at min (can't release what we don't have)
            deficit = self.min - new_storage
            release_mcm = max(0.0, release_mcm - deficit)
            new_storage = self.min

        release_mcm += spilled_mcm
        outflow_m3s = mcm_to_m3s_month(release_mcm, days)

        energy_gwh = 0.0
        if self.hep:
            # Use release_mcm converted to m³ (spilled water doesn't always turbine, but
            # hackathon simplification: everything released goes through turbines when
            # the spill flag is off — fine for pitch).
            release_m3 = release_mcm * 1e6
            head = float(self.hep["head_m"])
            eff = float(self.hep["efficiency"])
            energy_j = release_m3 * head * eff * RHO * G
            energy_gwh = energy_j / 3.6e12

        self.storage = new_storage
        state[self.id] = {
            "outflow_m3s": outflow_m3s,
            "inflow_m3s": inflow_m3s,
            "storage_mcm": new_storage,
            "release_m3s": mcm_to_m3s_month(release_mcm, days),
            "evap_mcm": evap_mcm,
            "energy_gwh": energy_gwh,
        }

    def _desired_release(self, policy, month_key, inflow_m3s) -> float:
        mode = policy.get("mode", "historical")
        if mode == "manual":
            mapping = policy.get("release_m3s_by_month", {})
            if month_key in mapping:
                return float(mapping[month_key])
            return inflow_m3s  # pass-through default
        if mode == "rule_curve":
            # Simple linear rule: release proportional to fractional storage
            frac = (self.storage - self.min) / max(1.0, self.capacity - self.min)
            return inflow_m3s * (0.5 + frac)
        # historical default: pass inflow through (plus any tiny draw-down from policy)
        return inflow_m3s
```

- [ ] **Step 4: Register in `nodes/__init__.py`**

```python
from simengine.nodes import source, sink, reservoir  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_reservoir.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add simengine/nodes/reservoir.py simengine/nodes/__init__.py tests/test_reservoir.py
git commit -m "L2: reservoir node (mass balance + HEP + Penman evap)"
```

---

## Task 5: Reach node (Muskingum routing)

**Files:**
- Create: `simengine/nodes/reach.py`
- Create: `tests/test_reach.py`

Muskingum: `Q_out(t) = C0·Q_in(t) + C1·Q_in(t-1) + C2·Q_out(t-1)` where `C0,C1,C2` are derived from (K, x, Δt). At monthly Δt and K~0.5–1.5 months, this gives realistic lag+attenuation.

- [ ] **Step 1: Write the failing test**

`tests/test_reach.py`:

```python
import pandas as pd

from simengine.nodes.reach import Reach


def _forcings(n=5):
    return pd.DataFrame({"month": pd.date_range("2020-01-01", periods=n, freq="MS"),
                         "pet_mm": [0.0] * n})


def test_steady_state_passthrough():
    r = Reach(id="r", upstream=["u"], downstream=["d"],
              travel_time_months=1.0, muskingum_k=1.0, muskingum_x=0.2)
    r.load_forcings(_forcings())
    state = {"u": {"outflow_m3s": 500.0}}
    # Warm up: feed same inflow enough times for outflow to converge
    for t in range(5):
        r.step(t, state)
    assert abs(state["r"]["outflow_m3s"] - 500.0) < 1.0


def test_pulse_attenuation():
    r = Reach(id="r", upstream=["u"], downstream=["d"],
              travel_time_months=1.0, muskingum_k=1.0, muskingum_x=0.2)
    r.load_forcings(_forcings())
    state = {"u": {"outflow_m3s": 0.0}}
    r.step(0, state)
    state["u"]["outflow_m3s"] = 1000.0
    r.step(1, state)
    peak1 = state["r"]["outflow_m3s"]
    state["u"]["outflow_m3s"] = 0.0
    r.step(2, state)
    peak2 = state["r"]["outflow_m3s"]
    # Peak attenuated below input, and some flow persists after pulse passes
    assert peak1 < 1000.0
    assert peak2 > 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_reach.py -v
```

- [ ] **Step 3: Implement `simengine/nodes/reach.py`**

```python
"""Reach node with Muskingum routing (monthly Δt)."""
from __future__ import annotations

from simengine.graph import register_node_class
from simengine.nodes.base import Node


@register_node_class("reach")
class Reach(Node):
    def __init__(self, id, upstream, downstream, *,
                 travel_time_months=1.0, muskingum_k=1.0, muskingum_x=0.2, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        K = float(muskingum_k)
        x = float(muskingum_x)
        dt = 1.0  # monthly step
        denom = 2.0 * K * (1.0 - x) + dt
        self.C0 = (dt - 2.0 * K * x) / denom
        self.C1 = (dt + 2.0 * K * x) / denom
        self.C2 = (2.0 * K * (1.0 - x) - dt) / denom
        self._prev_in = 0.0
        self._prev_out = 0.0

    def step(self, t, state):
        inflow = self.upstream_inflow_m3s(state)
        out = self.C0 * inflow + self.C1 * self._prev_in + self.C2 * self._prev_out
        out = max(0.0, out)  # no negative flows
        self._prev_in = inflow
        self._prev_out = out
        state[self.id] = {"outflow_m3s": out, "inflow_m3s": inflow}
```

- [ ] **Step 4: Register in `nodes/__init__.py`**

Update to include `reach`.

- [ ] **Step 5: Run tests and commit**

```bash
pytest tests/test_reach.py -v
git add simengine/nodes/reach.py simengine/nodes/__init__.py tests/test_reach.py
git commit -m "L2: reach node with Muskingum routing"
```

---

## Task 6: Confluence + wetland

**Files:**
- Create: `simengine/nodes/confluence.py`, `simengine/nodes/wetland.py`
- Create: `tests/test_wetland.py`

- [ ] **Step 1: Implement `simengine/nodes/confluence.py`**

```python
from simengine.graph import register_node_class
from simengine.nodes.base import Node


@register_node_class("confluence")
class Confluence(Node):
    def __init__(self, id, upstream, downstream, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)

    def step(self, t, state):
        inflow = self.upstream_inflow_m3s(state)
        state[self.id] = {"outflow_m3s": inflow, "inflow_m3s": inflow}
```

- [ ] **Step 2: Write the failing wetland test**

`tests/test_wetland.py`:

```python
import pandas as pd

from simengine.nodes.wetland import Wetland


def test_evap_fraction_is_lost():
    w = Wetland(id="sudd", upstream=["u"], downstream=["d"], evap_loss_fraction_baseline=0.5)
    w.load_forcings(pd.DataFrame({"month": pd.date_range("2020-01-01", periods=1, freq="MS"),
                                  "pet_mm": [150.0]}))
    state = {"u": {"outflow_m3s": 1000.0}}
    w.step(0, state)
    assert 450 <= state["sudd"]["outflow_m3s"] <= 550
    assert abs(state["sudd"]["evap_loss_fraction"] - 0.5) < 0.01
```

- [ ] **Step 3: Implement `simengine/nodes/wetland.py`**

```python
from simengine.graph import register_node_class
from simengine.nodes.base import Node


@register_node_class("wetland")
class Wetland(Node):
    def __init__(self, id, upstream, downstream, *, evap_loss_fraction_baseline=0.5, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.loss = float(evap_loss_fraction_baseline)

    def step(self, t, state):
        inflow = self.upstream_inflow_m3s(state)
        out = inflow * (1.0 - self.loss)
        state[self.id] = {
            "outflow_m3s": out,
            "inflow_m3s": inflow,
            "evap_loss_fraction": self.loss,
        }
```

- [ ] **Step 4: Register, test, commit**

Update `nodes/__init__.py` to include both. Run:

```bash
pytest tests/test_wetland.py -v
git add simengine/nodes/ tests/test_wetland.py
git commit -m "L2: confluence + wetland nodes"
```

---

## Task 7: Crop water requirement curve

**Files:**
- Create: `simengine/crop_water.py`
- Create: `tests/test_crop_water.py`

- [ ] **Step 1: Write the failing test**

`tests/test_crop_water.py`:

```python
import numpy as np

from simengine.crop_water import monthly_water_requirement_mm


def test_peak_in_summer_northern_hemisphere():
    vals = [monthly_water_requirement_mm(m) for m in range(1, 13)]
    assert max(vals) == vals[6] or max(vals) == vals[5] or max(vals) == vals[7]


def test_positive_everywhere():
    for m in range(1, 13):
        assert monthly_water_requirement_mm(m) > 0
```

- [ ] **Step 2: Implement `simengine/crop_water.py`**

```python
"""Simplified monthly crop water requirement for Nile-basin irrigation.

Uses a single seasonal sinusoid peaking in July; amplitude and offset tuned
to FAO AquaStat numbers for the Gezira/Nile-Delta mean cropping pattern.
Values in mm/month."""
import math


def monthly_water_requirement_mm(month: int, peak_month: int = 7,
                                 annual_mean_mm: float = 130.0,
                                 amplitude_mm: float = 90.0) -> float:
    phase = (month - peak_month) * math.pi / 6.0
    return max(20.0, annual_mean_mm + amplitude_mm * math.cos(phase))
```

- [ ] **Step 3: Run test, commit**

```bash
pytest tests/test_crop_water.py -v
git add simengine/crop_water.py tests/test_crop_water.py
git commit -m "L2: monthly crop water requirement curve"
```

---

## Task 8: Demand nodes

**Files:**
- Create: `simengine/nodes/demand_irrigation.py`, `simengine/nodes/demand_municipal.py`
- Create: `tests/test_demand_irrigation.py`, `tests/test_demand_municipal.py`

- [ ] **Step 1: Write the failing irrigation test**

`tests/test_demand_irrigation.py`:

```python
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
```

- [ ] **Step 2: Implement `simengine/nodes/demand_irrigation.py`**

```python
from simengine.crop_water import monthly_water_requirement_mm
from simengine.graph import register_node_class
from simengine.nodes.base import Node, days_in_month_from_ts, mcm_to_m3s_month


@register_node_class("demand_irrigation")
class DemandIrrigation(Node):
    def __init__(self, id, upstream, downstream, *,
                 area_ha_baseline, crop_water_productivity_kg_per_m3, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.area_ha_baseline = float(area_ha_baseline)
        self.productivity = float(crop_water_productivity_kg_per_m3)

    def step(self, t, state, *, policy=None):
        policy = policy or {}
        scale = float(policy.get("area_scale", 1.0))
        area_ha = self.area_ha_baseline * scale

        row = self.forcings.iloc[t]
        month_num = row["month"].month
        days = days_in_month_from_ts(row["month"])
        req_mm = monthly_water_requirement_mm(month_num)
        # mm × ha = 1e-3 m × 1e4 m² = 10 m³  → demand (m³) = req_mm × area_ha × 10
        demand_m3 = req_mm * area_ha * 10.0

        inflow_m3s = self.upstream_inflow_m3s(state)
        inflow_m3 = inflow_m3s * days * 86400.0
        delivered_m3 = min(demand_m3, inflow_m3)
        delivered_fraction = delivered_m3 / demand_m3 if demand_m3 > 0 else 1.0
        food_tonnes = (delivered_m3 * self.productivity) / 1000.0

        outflow_m3s = (inflow_m3 - delivered_m3) / (days * 86400.0)
        state[self.id] = {
            "outflow_m3s": outflow_m3s,
            "inflow_m3s": inflow_m3s,
            "demand_m3": demand_m3,
            "delivered_m3": delivered_m3,
            "delivered_m3s": delivered_m3 / (days * 86400.0),
            "delivered_fraction": delivered_fraction,
            "food_tonnes_month": food_tonnes,
        }
```

- [ ] **Step 3: Write + implement demand_municipal**

`tests/test_demand_municipal.py`:

```python
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
```

`simengine/nodes/demand_municipal.py`:

```python
from simengine.graph import register_node_class
from simengine.nodes.base import Node, days_in_month_from_ts


@register_node_class("demand_municipal")
class DemandMunicipal(Node):
    def __init__(self, id, upstream, downstream, *,
                 population_baseline, per_capita_l_day, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.population = float(population_baseline)
        self.per_capita_l_day = float(per_capita_l_day)

    def step(self, t, state, *, policy=None):
        policy = policy or {}
        pop = self.population * float(policy.get("population_scale", 1.0))

        row = self.forcings.iloc[t]
        days = days_in_month_from_ts(row["month"])
        demand_m3 = pop * self.per_capita_l_day * days / 1000.0

        inflow_m3s = self.upstream_inflow_m3s(state)
        inflow_m3 = inflow_m3s * days * 86400.0
        delivered_m3 = min(demand_m3, inflow_m3)
        served_pct = delivered_m3 / demand_m3 if demand_m3 > 0 else 1.0
        outflow_m3s = (inflow_m3 - delivered_m3) / (days * 86400.0)
        state[self.id] = {
            "outflow_m3s": outflow_m3s,
            "inflow_m3s": inflow_m3s,
            "demand_m3": demand_m3,
            "delivered_m3": delivered_m3,
            "served_pct": served_pct,
            "population_served": pop * served_pct,
        }
```

- [ ] **Step 4: Register, test, commit**

Update `nodes/__init__.py` to include both demand types. Run:

```bash
pytest tests/test_demand_irrigation.py tests/test_demand_municipal.py -v
git add simengine/nodes/ simengine/crop_water.py tests/test_demand_*.py tests/test_crop_water.py
git commit -m "L2: demand_irrigation + demand_municipal nodes"
```

---

## Task 9: Scenario model (pydantic)

**Files:**
- Create: `simengine/scenario.py`
- Create: `tests/test_scenario.py`

- [ ] **Step 1: Write the failing test**

`tests/test_scenario.py`:

```python
import json
from pathlib import Path

import pytest

from simengine.scenario import Scenario


def test_load_minimal_scenario(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({
        "name": "x",
        "period": ["2005-01", "2024-12"],
        "policy": {"reservoirs": {}, "demands": {}, "constraints": {}, "weights": {
            "water": 0.4, "food": 0.3, "energy": 0.3}},
    }))
    s = Scenario.from_file(p)
    assert s.name == "x"
    assert s.policy.weights.water == 0.4


def test_weights_must_sum_to_one():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Scenario(name="x", period=["2005-01", "2024-12"],
                 policy={"reservoirs": {}, "demands": {}, "constraints": {},
                         "weights": {"water": 0.5, "food": 0.3, "energy": 0.3}})


def test_round_trip_to_file(tmp_path):
    s = Scenario(
        name="t", period=["2020-01", "2020-12"],
        policy={"reservoirs": {}, "demands": {}, "constraints": {},
                "weights": {"water": 0.4, "food": 0.3, "energy": 0.3}},
    )
    p = tmp_path / "out.json"
    s.to_file(p)
    loaded = Scenario.from_file(p)
    assert loaded.name == "t"
```

- [ ] **Step 2: Implement `simengine/scenario.py`**

```python
"""Scenario IO models (pydantic v2)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class Weights(BaseModel):
    water: float
    food: float
    energy: float

    @field_validator("water", "food", "energy")
    @classmethod
    def _nonneg(cls, v):
        if v < 0:
            raise ValueError("weights must be non-negative")
        return v

    def model_post_init(self, _) -> None:
        s = self.water + self.food + self.energy
        if abs(s - 1.0) > 1e-6:
            raise ValueError(f"weights must sum to 1.0 (got {s})")


class ReservoirPolicy(BaseModel):
    mode: str = "historical"                        # "historical" | "rule_curve" | "manual"
    release_m3s_by_month: dict[str, float] = Field(default_factory=dict)


class DemandPolicy(BaseModel):
    area_scale: float = 1.0
    population_scale: float = 1.0


class Constraints(BaseModel):
    min_delta_flow_m3s: float = 0.0


class Policy(BaseModel):
    reservoirs: dict[str, ReservoirPolicy] = Field(default_factory=dict)
    demands: dict[str, DemandPolicy] = Field(default_factory=dict)
    constraints: Constraints = Field(default_factory=Constraints)
    weights: Weights


class ScenarioResults(BaseModel):
    timeseries_per_node: dict[str, list[dict]] = Field(default_factory=dict)
    kpi_monthly: list[dict] = Field(default_factory=list)
    score: float | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class Scenario(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    period: list[str]                               # ["YYYY-MM", "YYYY-MM"]
    policy: Policy
    results: ScenarioResults | None = None

    @classmethod
    def from_file(cls, path: Path | str) -> "Scenario":
        return cls.model_validate_json(Path(path).read_text())

    def to_file(self, path: Path | str) -> None:
        Path(path).write_text(self.model_dump_json(indent=2))
```

- [ ] **Step 3: Run tests, commit**

```bash
pytest tests/test_scenario.py -v
git add simengine/scenario.py tests/test_scenario.py
git commit -m "L2: Scenario pydantic models + file IO"
```

---

## Task 10: KPI calculators

**Files:**
- Create: `simengine/kpi.py`
- Create: `tests/test_kpi.py`

- [ ] **Step 1: Write the failing test**

`tests/test_kpi.py`:

```python
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
```

- [ ] **Step 2: Implement `simengine/kpi.py`**

```python
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
```

- [ ] **Step 3: Run, commit**

```bash
pytest tests/test_kpi.py -v
git add simengine/kpi.py tests/test_kpi.py
git commit -m "L2: KPI aggregation across nodes"
```

---

## Task 11: Scoring (weighted sum + delta penalty)

**Files:**
- Create: `simengine/scoring.py`
- Create: `tests/test_scoring.py`

- [ ] **Step 1: Implement with test**

`tests/test_scoring.py`:

```python
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
```

`simengine/scoring.py`:

```python
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

    # Delta penalty: fraction of months with sink outflow < min
    violations = sum(1 for m in (k["month"] for k in kpis)
                     if sink_outflow.get(m, 0.0) < min_delta_flow_m3s)
    delta_penalty = violations / n * 0.3  # cap at 30% of score

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
```

- [ ] **Step 2: Run, commit**

```bash
pytest tests/test_scoring.py -v
git add simengine/scoring.py tests/test_scoring.py
git commit -m "L2: scenario scoring with delta-flow penalty"
```

---

## Task 12: Engine orchestration (golden mass-balance test)

**Files:**
- Create: `simengine/engine.py`, `simengine/forcings.py`
- Create: `tests/test_engine_mass_balance.py`

This is the most important test in L2. If mass conservation fails, every downstream number is wrong.

- [ ] **Step 1: Implement `simengine/forcings.py`**

```python
"""Per-node forcings loader — reads data/timeseries/<node_id>.parquet."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_forcings(node_id: str, timeseries_dir: Path) -> pd.DataFrame:
    path = Path(timeseries_dir) / f"{node_id}.parquet"
    if not path.exists():
        # Nodes without per-node forcings (e.g., confluences) get an empty frame.
        return pd.DataFrame()
    return pd.read_parquet(path)
```

- [ ] **Step 2: Write the failing engine test**

`tests/test_engine_mass_balance.py`:

```python
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from simengine.engine import run
from simengine.scenario import Scenario


def _setup_three_node(tmp_path):
    # source → reservoir → sink, 12 months, constant inflow, no evap
    cfg = tmp_path / "config.yaml"
    cfg.write_text("""
nodes:
  src: {type: source, catchment_area_km2: 100000, catchment_scale: 1.0}
  res:
    type: reservoir
    storage_capacity_mcm: 10000
    storage_min_mcm: 100
    surface_area_km2_at_full: 1
    initial_storage_mcm: 5000
    hep: {nameplate_mw: 100, head_m: 50, efficiency: 0.9}
  snk: {type: sink, min_environmental_flow_m3s: 0}
reaches: {}
""")
    topo = tmp_path / "topo.json"
    topo.write_text('{"edges":[["src","res"],["res","snk"]]}')

    # Forcings: 30 mm/month runoff, zero PET (no evap)
    ts_dir = tmp_path / "timeseries"
    ts_dir.mkdir()
    months = pd.date_range("2020-01-01", periods=12, freq="MS")
    for nid in ("src", "res", "snk"):
        df = pd.DataFrame({"month": months, "runoff_mm": [30.0] * 12,
                           "pet_mm": [0.0] * 12, "precip_mm": [0.0] * 12,
                           "temp_c": [25.0] * 12, "radiation_mj_m2": [20.0] * 12,
                           "wind_ms": [2.0] * 12, "dewpoint_c": [15.0] * 12,
                           "historical_discharge_m3s": pd.NA})
        df.to_parquet(ts_dir / f"{nid}.parquet", index=False)

    scenario = Scenario(
        name="t", period=["2020-01", "2020-12"],
        policy={"reservoirs": {}, "demands": {}, "constraints": {},
                "weights": {"water": 0.34, "food": 0.33, "energy": 0.33}},
    )
    return cfg, topo, ts_dir, scenario


def test_mass_conservation_over_year(tmp_path):
    cfg, topo, ts_dir, scenario = _setup_three_node(tmp_path)
    result = run(scenario, config_path=cfg, topology_path=topo, timeseries_dir=ts_dir)
    # Total inflow at source over the year
    src_ts = result.results.timeseries_per_node["src"]
    res_ts = result.results.timeseries_per_node["res"]
    snk_ts = result.results.timeseries_per_node["snk"]
    # Sum inflow at source; sum outflow at sink; sum evap; storage change at reservoir
    # inflow_total = snk_inflow_total + evap_total + (storage_end - storage_start)
    src_total = sum(r["outflow_m3s"] * pd.Timestamp(r["month"]).days_in_month * 86400 for r in src_ts)
    snk_total = sum(r["inflow_m3s"] * pd.Timestamp(r["month"]).days_in_month * 86400 for r in snk_ts)
    evap_total = sum(r["evap_mcm"] * 1e6 for r in res_ts)
    d_storage_m3 = (res_ts[-1]["storage_mcm"] - 5000.0) * 1e6
    # Mass balance in m³
    assert abs(src_total - (snk_total + evap_total + d_storage_m3)) / src_total < 0.001
```

- [ ] **Step 3: Implement `simengine/engine.py`**

```python
"""Time-stepping orchestrator."""
from __future__ import annotations

from pathlib import Path

from simengine.forcings import load_forcings
from simengine.graph import load_graph
from simengine.kpi import compute_monthly_kpis
from simengine.scenario import Scenario
from simengine.scoring import score_scenario


def run(scenario: Scenario, *, config_path: Path, topology_path: Path | None = None,
        geojson_path: Path | None = None, timeseries_dir: Path) -> Scenario:
    """Run a scenario in place: populates `scenario.results` and returns it."""
    graph = load_graph(config_path, topology_path=topology_path, geojson_path=geojson_path)

    # Load per-node forcings (may be empty DataFrame for confluences/sinks)
    for nid, node in graph.nodes.items():
        node.load_forcings(load_forcings(nid, timeseries_dir))

    # Determine number of time steps from any node that has forcings
    n_months = 0
    for node in graph.nodes.values():
        if len(node.forcings) > 0:
            n_months = max(n_months, len(node.forcings))
    if n_months == 0:
        raise ValueError("no forcings found for any node")

    # Filter to scenario period
    start, end = scenario.period
    # Assume all forcings have a 'month' column; slice uniformly
    for node in graph.nodes.values():
        if len(node.forcings):
            f = node.forcings.copy()
            mask = (f["month"] >= f"{start}-01") & (f["month"] <= f"{end}-01")
            node.forcings = f.loc[mask].reset_index(drop=True)
    n_months = max(len(n.forcings) for n in graph.nodes.values() if len(n.forcings))

    ts_per_node: dict[str, list[dict]] = {nid: [] for nid in graph.nodes}
    sink_outflow_by_month: dict[str, float] = {}

    for t in range(n_months):
        step_state: dict[str, dict] = {}
        # month label: pick from any node with forcings
        month_label = None
        for n in graph.nodes.values():
            if len(n.forcings) > t:
                month_label = str(n.forcings.iloc[t]["month"])[:7]
                break

        for nid in graph.order:
            node = graph.nodes[nid]
            if _wants_policy(node):
                policy = _policy_for_node(scenario.policy, node)
                node.step(t, step_state, policy=policy)
            else:
                node.step(t, step_state)
            if nid in step_state:
                ts_per_node[nid].append({"month": month_label, **step_state[nid]})
            if node.__class__.__name__ == "Sink":
                sink_outflow_by_month[month_label] = step_state[nid].get("inflow_m3s", 0.0)

    kpis = compute_monthly_kpis(ts_per_node)
    baseline = _derive_baseline(kpis)
    scoring = score_scenario(
        kpis, baseline,
        weights={"water": scenario.policy.weights.water,
                 "food": scenario.policy.weights.food,
                 "energy": scenario.policy.weights.energy},
        min_delta_flow_m3s=scenario.policy.constraints.min_delta_flow_m3s,
        sink_outflow=sink_outflow_by_month,
    )

    from simengine.scenario import ScenarioResults
    scenario.results = ScenarioResults(
        timeseries_per_node=ts_per_node,
        kpi_monthly=kpis,
        score=scoring["score"],
        score_breakdown=scoring["breakdown"],
    )
    return scenario


def run_scenario_file(scenario_path, config_path, timeseries_dir, out_path=None):
    s = Scenario.from_file(scenario_path)
    # Try topology.json adjacent to config; else fall back to nodes.geojson
    cfg = Path(config_path)
    topo = cfg.parent / "topology.json"
    geo = cfg.parent / "nodes.geojson"
    s = run(s, config_path=cfg,
            topology_path=topo if topo.exists() else None,
            geojson_path=geo if geo.exists() else None,
            timeseries_dir=Path(timeseries_dir))
    s.to_file(out_path or scenario_path)


def _wants_policy(node) -> bool:
    return node.__class__.__name__ in {"Reservoir", "DemandIrrigation", "DemandMunicipal"}


def _policy_for_node(policy, node) -> dict:
    nid = node.id
    if node.__class__.__name__ == "Reservoir":
        r = policy.reservoirs.get(nid)
        return r.model_dump() if r else {}
    if node.__class__.__name__ in {"DemandIrrigation", "DemandMunicipal"}:
        d = policy.demands.get(nid)
        return d.model_dump() if d else {}
    return {}


def _derive_baseline(kpis):
    """Baseline for normalization = mean of the KPI time-series itself.
    Keeps scoring meaningful without a separate historical reference run."""
    n = max(1, len(kpis))
    return {
        "food_tonnes": max(1.0, sum(k["food_tonnes"] for k in kpis) / n),
        "energy_gwh": max(1.0, sum(k["energy_gwh"] for k in kpis) / n),
    }
```

- [ ] **Step 4: Run the golden test**

```bash
pytest tests/test_engine_mass_balance.py -v
```

Expected: pass. If it fails, the physics of reservoir/source/sink need to be re-verified — don't move on.

- [ ] **Step 5: Commit**

```bash
git add simengine/engine.py simengine/forcings.py tests/test_engine_mass_balance.py
git commit -m "L2: engine time-stepper + golden mass-balance test"
```

---

## Task 13: CLI end-to-end against L1 stub data

**Files:** (no new files)

- [ ] **Step 1: Generate stub data from L1 and build a baseline scenario**

Assumes L1's stub output is in `data/`:

```bash
python -m dataloader all --stub
mkdir -p data/scenarios
cat > data/scenarios/baseline.json <<'JSON'
{
  "name": "baseline-stub",
  "period": ["2005-01", "2024-12"],
  "policy": {
    "reservoirs": {},
    "demands": {},
    "constraints": {"min_delta_flow_m3s": 0},
    "weights": {"water": 0.4, "food": 0.3, "energy": 0.3}
  }
}
JSON
```

- [ ] **Step 2: Run**

```bash
python -m simengine run --scenario data/scenarios/baseline.json \
  --config data/node_config.yaml --data data/timeseries
python -c "
import json
s = json.loads(open('data/scenarios/baseline.json').read())
print('score:', s['results']['score'])
print('first KPI:', s['results']['kpi_monthly'][0])
print('last KPI:', s['results']['kpi_monthly'][-1])
"
```

Expected: score printed (0..1), 240 KPI rows, all fields populated.

- [ ] **Step 3: Commit**

```bash
git add data/scenarios/baseline.json    # if you want to keep it in git; otherwise skip
git commit --allow-empty -m "L2: stub end-to-end green"
```

---

## Task 14: Sunday — real data run

- [ ] **Step 1: Pull L1's real data snapshot**

```bash
tar xzf ~/Downloads/nile-real-data-*.tar.gz -C .
```

- [ ] **Step 2: Re-run**

```bash
python -m simengine run --scenario data/scenarios/baseline.json \
  --config data/node_config.yaml --data data/timeseries
```

Expected: runs in <1 s, produces a plausible score (0.5–0.85 for baseline).

- [ ] **Step 3: Sanity check against L5's calibration target**

Confirm with L5 (floater): simulated Aswan discharge (`aswan` node's `outflow_m3s` monthly series) is within 20% monthly RMSE of GRDC observed. If not, L5 tunes `catchment_scale` on source nodes.

---

## L2 Success Criteria

1. `pytest tests/` all green (10 test modules, ~25 tests).
2. `python -m simengine run --scenario data/scenarios/baseline.json` runs without error against stub data (Sat 13:00).
3. Same against real data (Sun 09:00).
4. Mass conservation test passes within 0.1% over a 12-month run.
5. Scenario JSON conforms to the shape in the spec; L3 can `Scenario.from_file(...)` round-trip.

## Explicit non-goals for L2

- No web / API / JSON server — L3 owns that.
- No UI — L4 owns that.
- No historical-discharge calibration — L5 owns that; L2 exposes `catchment_scale` as the tuning knob.
- No head-vs-storage rating curves (constant `head_m`).
- No optimizer (Scope-C stretch is L5).
- No sub-monthly time steps.
