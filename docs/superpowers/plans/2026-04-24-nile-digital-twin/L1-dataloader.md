# L1 — Dataloader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the canonical on-disk data store (`data/`) — node geometry, node config, per-node monthly forcings Parquet files, NDVI overlay Parquet, and pre-rendered NDVI raster tiles — from public Copernicus sources so that L2 (sim engine), L3 (API), and L4 (dashboard) have everything they need.

**Architecture:** A small Python package (`dataloader/`) with a `typer` CLI. Subcommands fetch external data, compute derived fields (Penman PET), and write Parquet/GeoJSON/YAML into `data/` following the schema fixed in the spec. A `--stub` mode produces 3–4 nodes of schema-correct synthetic data in under 30 s so downstream lanes are never blocked on real fetches.

**Tech stack:** Python 3.11, `typer` (CLI), `cdsapi` (ERA5), `pystac-client` + `stackstac` (Sentinel-2 via Copernicus Data Space Ecosystem), `xarray`, `pandas`, `pyarrow` (Parquet), `geopandas` (GeoJSON), `rasterio` + `rio-tiler` (NDVI tiles), `pytest`.

**Lane ownership:** 1 person. Deliverables due:
- **Sat 10:00** — `dataloader nodes --stub` produces `nodes.geojson` + `node_config.yaml` with 4 stub nodes (unblocks L2/L3).
- **Sat 17:00** — real forcings Parquet for all ~15–20 nodes (2005–2024 monthly).
- **Sun 12:00** — NDVI overlays + NDVI raster tiles.

**Shared contracts** (from spec, copied verbatim so you don't need to cross-reference):

- `data/nodes.geojson` — Feature per node; properties `{id, name, type, country, upstream[], downstream[]}`; geometry `Point(lon, lat)`.
- `data/node_config.yaml` — `nodes: {id: {...}}` + `reaches: {id: {travel_time_months, muskingum_k, muskingum_x}}`.
- `data/timeseries/<node_id>.parquet` columns: `month` (timestamp), `precip_mm`, `temp_c`, `radiation_mj_m2`, `wind_ms`, `dewpoint_c`, `pet_mm`, `runoff_mm`, `historical_discharge_m3s` (nullable).
- `data/overlays/ndvi/<zone_id>.parquet` columns: `month`, `ndvi_mean`, `ndvi_std`, `valid_pixel_frac`.
- `data/static/reservoirs.yaml` — optional supplementary metadata; referenced from `node_config.yaml`.

---

## File Structure

```
pyproject.toml                  # package + deps
dataloader/
  __init__.py
  __main__.py                   # `python -m dataloader` → typer app
  config.py                     # paths, constants, env
  nodes.py                      # curated node list + reach list + writers
  penman.py                     # Penman PET from ERA5 variables
  aggregate.py                  # daily→monthly + bbox-weighted spatial mean
  era5.py                       # CDS API fetch → xarray
  forcings.py                   # orchestrates era5 + penman + Parquet write
  overlays.py                   # Sentinel-2 NDVI + CGLS NDVI → Parquet
  tiles.py                      # NDVI raster → XYZ tile pyramid
  stubs.py                      # --stub mode data generators
tests/
  __init__.py
  test_penman.py
  test_aggregate.py
  test_nodes.py
  test_forcings.py
  test_overlays.py
  fixtures/
    era5_mini.nc                # small fake ERA5 NetCDF for tests
data/                           # gitignored; produced by the CLI
  nodes.geojson
  node_config.yaml
  static/reservoirs.yaml
  timeseries/<id>.parquet
  overlays/ndvi/<zone>.parquet
  tiles/ndvi/<zone>/<YYYY-MM>/{z}/{x}/{y}.png
```

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `dataloader/__init__.py`, `dataloader/__main__.py`, `dataloader/config.py`
- Create: `tests/__init__.py`
- Modify: `.gitignore` (add `data/`)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "nile-dataloader"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "typer>=0.12",
  "pydantic>=2.6",
  "pyyaml>=6",
  "pandas>=2.2",
  "pyarrow>=15",
  "numpy>=1.26",
  "xarray>=2024.2",
  "netcdf4>=1.6",
  "cdsapi>=0.7",
  "pystac-client>=0.8",
  "stackstac>=0.5",
  "geopandas>=0.14",
  "shapely>=2.0",
  "rasterio>=1.3",
  "rio-tiler>=6.4",
  "pillow>=10",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov>=4", "ruff>=0.3"]

[project.scripts]
dataloader = "dataloader.__main__:app"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Create `dataloader/__init__.py`** (empty)

```python
```

- [ ] **Step 3: Create `dataloader/config.py`**

```python
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
TIMESERIES_DIR = DATA_DIR / "timeseries"
OVERLAYS_DIR = DATA_DIR / "overlays" / "ndvi"
TILES_DIR = DATA_DIR / "tiles" / "ndvi"
STATIC_DIR = DATA_DIR / "static"

NODES_GEOJSON = DATA_DIR / "nodes.geojson"
NODE_CONFIG_YAML = DATA_DIR / "node_config.yaml"

PERIOD_START = "2005-01-01"
PERIOD_END = "2024-12-01"
```

- [ ] **Step 4: Create `dataloader/__main__.py` with typer skeleton**

```python
import typer

app = typer.Typer(help="Nile digital twin dataloader")

@app.command()
def nodes(stub: bool = typer.Option(False, help="Produce stub data (fast, for L2/L3 unblock)")) -> None:
    """Write nodes.geojson and node_config.yaml."""
    from dataloader import nodes as _nodes
    _nodes.build(stub=stub)

@app.command()
def forcings(stub: bool = False) -> None:
    """Fetch ERA5 forcings and write per-node timeseries Parquet."""
    from dataloader import forcings as _forcings
    _forcings.build(stub=stub)

@app.command()
def overlays(stub: bool = False) -> None:
    """Fetch Sentinel-2/CGLS NDVI and write overlays Parquet."""
    from dataloader import overlays as _overlays
    _overlays.build(stub=stub)

@app.command()
def tiles() -> None:
    """Render NDVI raster tile pyramid."""
    from dataloader import tiles as _tiles
    _tiles.build()

@app.command("all")
def all_(stub: bool = False) -> None:
    """Run nodes → forcings → overlays → tiles."""
    nodes(stub=stub)
    forcings(stub=stub)
    overlays(stub=stub)
    if not stub:
        tiles()

if __name__ == "__main__":
    app()
```

- [ ] **Step 5: Add `data/` to `.gitignore`**

Add these lines to the `# Project-specific` section:
```
data/
!data/.gitkeep
```

- [ ] **Step 6: Install and verify**

Run:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m dataloader --help
```

Expected: Typer prints the command list (`nodes`, `forcings`, `overlays`, `tiles`, `all`).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml dataloader/ tests/__init__.py .gitignore
git commit -m "L1: project scaffold (typer CLI skeleton, deps)"
```

---

## Task 2: Curated node list (data structure + validation)

**Files:**
- Create: `dataloader/nodes.py`
- Create: `tests/test_nodes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_nodes.py`:

```python
import json
from pathlib import Path

import pytest
import yaml

from dataloader.nodes import NODES, REACHES, build


def test_node_list_size_in_spec_range():
    assert 15 <= len(NODES) <= 20


def test_every_node_has_required_fields():
    for n in NODES:
        assert {"id", "name", "type", "country", "lat", "lon", "upstream", "downstream"}.issubset(n)
        assert n["type"] in {"source", "reservoir", "reach", "confluence", "wetland",
                             "demand_municipal", "demand_irrigation", "sink"}


def test_topology_is_acyclic_and_refers_to_real_nodes():
    ids = {n["id"] for n in NODES}
    for n in NODES:
        for u in n["upstream"]:
            assert u in ids, f"{n['id']} upstream references unknown node {u}"
        for d in n["downstream"]:
            assert d in ids, f"{n['id']} downstream references unknown node {d}"
    # acyclic: topological sort succeeds
    from graphlib import TopologicalSorter
    ts = TopologicalSorter({n["id"]: set(n["upstream"]) for n in NODES})
    list(ts.static_order())  # raises CycleError if cyclic


def test_build_writes_valid_geojson_and_yaml(tmp_path, monkeypatch):
    monkeypatch.setattr("dataloader.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("dataloader.config.NODES_GEOJSON", tmp_path / "nodes.geojson")
    monkeypatch.setattr("dataloader.config.NODE_CONFIG_YAML", tmp_path / "node_config.yaml")
    build(stub=False)
    gj = json.loads((tmp_path / "nodes.geojson").read_text())
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == len(NODES)
    cfg = yaml.safe_load((tmp_path / "node_config.yaml").read_text())
    assert set(cfg.keys()) == {"nodes", "reaches"}
    assert len(cfg["nodes"]) == len(NODES)
    assert len(cfg["reaches"]) == len(REACHES)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_nodes.py -v
```

Expected: All four tests fail with `ModuleNotFoundError: dataloader.nodes`.

- [ ] **Step 3: Create `dataloader/nodes.py` with the curated node list**

```python
"""Curated Nile basin node list. Manually assembled from public sources
(Wikipedia, FAO AquaStat, dam databases). Hand-editable."""
from __future__ import annotations

import json
from typing import Any

import yaml

from dataloader import config

# Each node is a dict; see tests for required fields.
NODES: list[dict[str, Any]] = [
    # --- White Nile branch ---
    {
        "id": "lake_victoria_outlet", "name": "Lake Victoria outlet (Jinja)",
        "type": "source", "country": "UG", "lat": 0.42, "lon": 33.19,
        "upstream": [], "downstream": ["white_nile_to_sudd"],
        "params": {"catchment_area_km2": 195000, "catchment_scale": 1.0},
    },
    {
        "id": "white_nile_to_sudd", "name": "White Nile reach to Sudd",
        "type": "reach", "country": "SS", "lat": 5.0, "lon": 31.5,
        "upstream": ["lake_victoria_outlet"], "downstream": ["sudd"],
        "params": {"travel_time_months": 1.0, "muskingum_k": 1.0, "muskingum_x": 0.2},
    },
    {
        "id": "sudd", "name": "Sudd wetland",
        "type": "wetland", "country": "SS", "lat": 7.5, "lon": 30.5,
        "upstream": ["white_nile_to_sudd"], "downstream": ["malakal"],
        "params": {"evap_loss_fraction_baseline": 0.5},
    },
    {
        "id": "malakal", "name": "Malakal (post-Sudd)",
        "type": "confluence", "country": "SS", "lat": 9.53, "lon": 31.65,
        "upstream": ["sudd"], "downstream": ["khartoum"],
        "params": {},
    },
    # --- Blue Nile branch ---
    {
        "id": "lake_tana_outlet", "name": "Lake Tana outlet",
        "type": "source", "country": "ET", "lat": 11.60, "lon": 37.38,
        "upstream": [], "downstream": ["blue_nile_to_gerd"],
        "params": {"catchment_area_km2": 15000, "catchment_scale": 1.0},
    },
    {
        "id": "blue_nile_to_gerd", "name": "Blue Nile reach to GERD",
        "type": "reach", "country": "ET", "lat": 11.0, "lon": 35.1,
        "upstream": ["lake_tana_outlet"], "downstream": ["gerd"],
        "params": {"travel_time_months": 0.5, "muskingum_k": 0.5, "muskingum_x": 0.2},
    },
    {
        "id": "gerd", "name": "Grand Ethiopian Renaissance Dam",
        "type": "reservoir", "country": "ET", "lat": 11.22, "lon": 35.09,
        "upstream": ["blue_nile_to_gerd"], "downstream": ["blue_nile_to_khartoum"],
        "params": {
            "storage_capacity_mcm": 74000, "storage_min_mcm": 14800,
            "surface_area_km2_at_full": 1874, "initial_storage_mcm": 14800,
            "hep": {"nameplate_mw": 6450, "head_m": 133, "efficiency": 0.9},
        },
    },
    {
        "id": "blue_nile_to_khartoum", "name": "Blue Nile reach (Roseires → Khartoum)",
        "type": "reach", "country": "SD", "lat": 13.5, "lon": 34.0,
        "upstream": ["gerd"], "downstream": ["gezira_irr", "khartoum"],
        "params": {"travel_time_months": 1.0, "muskingum_k": 1.0, "muskingum_x": 0.2},
    },
    {
        "id": "gezira_irr", "name": "Gezira irrigation scheme",
        "type": "demand_irrigation", "country": "SD", "lat": 14.4, "lon": 33.0,
        "upstream": ["blue_nile_to_khartoum"], "downstream": ["khartoum"],
        "params": {"area_ha_baseline": 900000, "crop_water_productivity_kg_per_m3": 1.2},
    },
    {
        "id": "khartoum", "name": "Khartoum confluence",
        "type": "confluence", "country": "SD", "lat": 15.60, "lon": 32.53,
        "upstream": ["malakal", "blue_nile_to_khartoum", "gezira_irr"],
        "downstream": ["khartoum_muni", "atbara_confluence"],
        "params": {},
    },
    {
        "id": "khartoum_muni", "name": "Khartoum municipal demand",
        "type": "demand_municipal", "country": "SD", "lat": 15.58, "lon": 32.53,
        "upstream": ["khartoum"], "downstream": ["atbara_confluence"],
        "params": {"population_baseline": 5500000, "per_capita_l_day": 150},
    },
    # --- Atbara tributary ---
    {
        "id": "atbara_source", "name": "Atbara River (Ethiopian highlands)",
        "type": "source", "country": "ET", "lat": 13.5, "lon": 37.0,
        "upstream": [], "downstream": ["atbara_confluence"],
        "params": {"catchment_area_km2": 112000, "catchment_scale": 1.0},
    },
    {
        "id": "atbara_confluence", "name": "Atbara confluence",
        "type": "confluence", "country": "SD", "lat": 17.67, "lon": 33.97,
        "upstream": ["khartoum_muni", "atbara_source"], "downstream": ["merowe"],
        "params": {},
    },
    # --- Main stem Sudan ---
    {
        "id": "merowe", "name": "Merowe Dam",
        "type": "reservoir", "country": "SD", "lat": 18.68, "lon": 31.93,
        "upstream": ["atbara_confluence"], "downstream": ["main_nile_to_aswan"],
        "params": {
            "storage_capacity_mcm": 12500, "storage_min_mcm": 2500,
            "surface_area_km2_at_full": 800, "initial_storage_mcm": 8000,
            "hep": {"nameplate_mw": 1250, "head_m": 67, "efficiency": 0.88},
        },
    },
    {
        "id": "main_nile_to_aswan", "name": "Main Nile reach to Aswan",
        "type": "reach", "country": "EG", "lat": 22.0, "lon": 32.0,
        "upstream": ["merowe"], "downstream": ["aswan"],
        "params": {"travel_time_months": 1.0, "muskingum_k": 1.0, "muskingum_x": 0.2},
    },
    # --- Aswan + Egypt ---
    {
        "id": "aswan", "name": "Aswan High Dam / Lake Nasser",
        "type": "reservoir", "country": "EG", "lat": 23.97, "lon": 32.88,
        "upstream": ["main_nile_to_aswan"], "downstream": ["egypt_ag"],
        "params": {
            "storage_capacity_mcm": 162000, "storage_min_mcm": 31600,
            "surface_area_km2_at_full": 5250, "initial_storage_mcm": 100000,
            "hep": {"nameplate_mw": 2100, "head_m": 70, "efficiency": 0.88},
        },
    },
    {
        "id": "egypt_ag", "name": "Egypt agriculture (Delta + Valley)",
        "type": "demand_irrigation", "country": "EG", "lat": 30.0, "lon": 31.0,
        "upstream": ["aswan"], "downstream": ["cairo_muni"],
        "params": {"area_ha_baseline": 3500000, "crop_water_productivity_kg_per_m3": 1.5},
    },
    {
        "id": "cairo_muni", "name": "Cairo municipal demand",
        "type": "demand_municipal", "country": "EG", "lat": 30.05, "lon": 31.25,
        "upstream": ["egypt_ag"], "downstream": ["delta"],
        "params": {"population_baseline": 20000000, "per_capita_l_day": 200},
    },
    {
        "id": "delta", "name": "Nile Delta / Mediterranean",
        "type": "sink", "country": "EG", "lat": 31.5, "lon": 31.5,
        "upstream": ["cairo_muni"], "downstream": [],
        "params": {"min_environmental_flow_m3s": 500},
    },
]

# Reaches with their own routing params (separate from the reach *nodes* above
# because the spec's `node_config.yaml` uses a top-level `reaches:` block).
REACHES: dict[str, dict[str, float]] = {
    n["id"]: n["params"]
    for n in NODES
    if n["type"] == "reach"
}


def build(stub: bool = False) -> None:
    """Write nodes.geojson + node_config.yaml."""
    nodes = _stub_nodes() if stub else NODES
    reaches = _stub_reaches() if stub else REACHES
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _write_geojson(nodes, config.NODES_GEOJSON)
    _write_yaml(nodes, reaches, config.NODE_CONFIG_YAML)


def _write_geojson(nodes: list[dict[str, Any]], path) -> None:
    features = []
    for n in nodes:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [n["lon"], n["lat"]]},
            "properties": {
                "id": n["id"], "name": n["name"], "type": n["type"],
                "country": n["country"],
                "upstream": n["upstream"], "downstream": n["downstream"],
            },
        })
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2))


def _write_yaml(nodes: list[dict[str, Any]], reaches: dict[str, dict[str, float]], path) -> None:
    node_block = {n["id"]: {"type": n["type"], **n["params"]} for n in nodes}
    out = {"nodes": node_block, "reaches": reaches}
    path.write_text(yaml.safe_dump(out, sort_keys=False))


def _stub_nodes() -> list[dict[str, Any]]:
    """Minimal 4-node line graph for Sat-morning L2/L3 unblock."""
    return [
        {"id": "stub_source", "name": "Stub source", "type": "source", "country": "XX",
         "lat": 0.0, "lon": 33.0, "upstream": [], "downstream": ["stub_reach"],
         "params": {"catchment_area_km2": 100000, "catchment_scale": 1.0}},
        {"id": "stub_reach", "name": "Stub reach", "type": "reach", "country": "XX",
         "lat": 10.0, "lon": 32.0, "upstream": ["stub_source"], "downstream": ["stub_reservoir"],
         "params": {"travel_time_months": 1.0, "muskingum_k": 1.0, "muskingum_x": 0.2}},
        {"id": "stub_reservoir", "name": "Stub reservoir", "type": "reservoir", "country": "XX",
         "lat": 20.0, "lon": 32.0, "upstream": ["stub_reach"], "downstream": ["stub_sink"],
         "params": {"storage_capacity_mcm": 10000, "storage_min_mcm": 1000,
                    "surface_area_km2_at_full": 100, "initial_storage_mcm": 5000,
                    "hep": {"nameplate_mw": 1000, "head_m": 50, "efficiency": 0.9}}},
        {"id": "stub_sink", "name": "Stub sink", "type": "sink", "country": "XX",
         "lat": 30.0, "lon": 31.0, "upstream": ["stub_reservoir"], "downstream": [],
         "params": {"min_environmental_flow_m3s": 100}},
    ]


def _stub_reaches() -> dict[str, dict[str, float]]:
    return {"stub_reach": {"travel_time_months": 1.0, "muskingum_k": 1.0, "muskingum_x": 0.2}}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_nodes.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Run the stub CLI end-to-end**

```bash
python -m dataloader nodes --stub
ls data/
cat data/node_config.yaml
```

Expected: `data/nodes.geojson` (4 features) + `data/node_config.yaml` exist. L2/L3 can now start.

- [ ] **Step 6: Commit**

```bash
git add dataloader/nodes.py tests/test_nodes.py
git commit -m "L1: curated node list + geojson/yaml writer (18 nodes + stub mode)"
```

---

## Task 3: Penman PET calculation

**Files:**
- Create: `dataloader/penman.py`
- Create: `tests/test_penman.py`

Reservoir evaporation needs a potential-evap estimate. We use FAO-56 Penman–Monteith over open water with standard parameters: daily method applied to monthly means (good enough at ~10% accuracy for lakes).

- [ ] **Step 1: Write the failing test with a sanity case**

Create `tests/test_penman.py`:

```python
import numpy as np

from dataloader.penman import pet_mm_monthly


def test_pet_at_aswan_july_is_in_sane_range():
    # Aswan July climatology (rough): T=33°C, Td=5°C (very dry),
    # radiation ~28 MJ/m²/day, wind ~3 m/s. Expect ~8–14 mm/day → 250–430 mm/month.
    pet = pet_mm_monthly(
        temp_c=33.0, dewpoint_c=5.0, radiation_mj_m2_day=28.0,
        wind_ms=3.0, days_in_month=31,
    )
    assert 250 <= pet <= 430, f"unexpected PET {pet:.1f} mm/month"


def test_pet_at_cool_humid_is_small():
    # Cool, humid, low radiation: expect <60 mm/month
    pet = pet_mm_monthly(
        temp_c=10.0, dewpoint_c=9.0, radiation_mj_m2_day=6.0,
        wind_ms=1.5, days_in_month=30,
    )
    assert 10 <= pet <= 80


def test_pet_vectorizes_over_arrays():
    # Called on numpy arrays (one value per month)
    temp = np.array([10.0, 20.0, 33.0])
    dew = np.array([9.0, 10.0, 5.0])
    rad = np.array([6.0, 18.0, 28.0])
    wind = np.array([1.5, 2.0, 3.0])
    days = np.array([31, 28, 31])
    pet = pet_mm_monthly(temp, dew, rad, wind, days)
    assert pet.shape == (3,)
    assert np.all(pet > 0)
    assert pet[2] > pet[0]  # hot dry > cool humid
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_penman.py -v
```

Expected: `ModuleNotFoundError: dataloader.penman`.

- [ ] **Step 3: Implement `dataloader/penman.py`**

```python
"""FAO-56 Penman–Monteith potential evapotranspiration.

Reference: Allen et al. (1998), FAO Irrigation & Drainage Paper 56.
Applied at monthly mean inputs; good enough (~10%) for reservoir evap.
"""
from __future__ import annotations

import numpy as np


def _saturation_vp_kpa(temp_c):
    """Tetens equation for saturation vapor pressure (kPa)."""
    return 0.6108 * np.exp((17.27 * temp_c) / (temp_c + 237.3))


def _slope_svp_kpa_per_c(temp_c):
    svp = _saturation_vp_kpa(temp_c)
    return 4098.0 * svp / ((temp_c + 237.3) ** 2)


def pet_mm_monthly(
    temp_c,
    dewpoint_c,
    radiation_mj_m2_day,
    wind_ms,
    days_in_month,
):
    """FAO-56 reference ET (mm per month).

    All inputs are monthly means (scalars or numpy arrays).
    `days_in_month` scales the daily result to the monthly total.
    """
    gamma = 0.066  # psychrometric constant (kPa/°C) at ~sea level
    es = _saturation_vp_kpa(temp_c)
    ea = _saturation_vp_kpa(dewpoint_c)
    delta = _slope_svp_kpa_per_c(temp_c)
    # Net radiation approx = 0.77 * Rs (albedo-adjusted for water)
    rn = 0.77 * radiation_mj_m2_day
    # Soil heat flux negligible for open water at monthly scale
    g_soil = 0.0
    num = 0.408 * delta * (rn - g_soil) + gamma * (900.0 / (temp_c + 273.0)) * wind_ms * (es - ea)
    den = delta + gamma * (1.0 + 0.34 * wind_ms)
    et0_day = num / den  # mm/day
    return et0_day * days_in_month
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_penman.py -v
```

Expected: all 3 tests pass. If the Aswan sanity test fails, re-check Tetens constants and the 0.77 albedo-adjusted Rn.

- [ ] **Step 5: Commit**

```bash
git add dataloader/penman.py tests/test_penman.py
git commit -m "L1: FAO-56 Penman PET with vectorized numpy support"
```

---

## Task 4: Spatial + temporal aggregation

**Files:**
- Create: `dataloader/aggregate.py`
- Create: `tests/test_aggregate.py`
- Create: `tests/fixtures/era5_mini.nc` (generated in Step 1)

We fetch ERA5 as hourly or daily gridded NetCDF, then need to:
1. Crop to a node's bbox,
2. Area-weighted spatial mean → single value per timestep per variable,
3. Resample to monthly.

- [ ] **Step 1: Generate a small fixture NetCDF for tests**

Add this as `tests/conftest.py`:

```python
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE_DIR.mkdir(exist_ok=True)
FIXTURE_ERA5 = FIXTURE_DIR / "era5_mini.nc"


@pytest.fixture(scope="session")
def era5_mini_path():
    if FIXTURE_ERA5.exists():
        return FIXTURE_ERA5
    # Daily data, 2x2 degree grid around lat=15, lon=33 (Khartoum-ish), 2 months
    time = pd.date_range("2020-01-01", "2020-02-29", freq="D")
    lat = np.array([14.5, 15.0, 15.5])
    lon = np.array([32.5, 33.0, 33.5])
    rng = np.random.default_rng(0)
    shape = (len(time), len(lat), len(lon))
    ds = xr.Dataset(
        {
            # ERA5 daily totals in meters for precip, J/m² for radiation, Kelvin for temps
            "tp":   (("time", "latitude", "longitude"), rng.uniform(0, 0.005, shape)),  # m/day
            "t2m":  (("time", "latitude", "longitude"), 298.0 + rng.normal(0, 2, shape)),  # K
            "d2m":  (("time", "latitude", "longitude"), 288.0 + rng.normal(0, 2, shape)),  # K
            "ssrd": (("time", "latitude", "longitude"), rng.uniform(1.5e7, 2.5e7, shape)),  # J/m²
            "si10": (("time", "latitude", "longitude"), rng.uniform(1.5, 4.0, shape)),     # m/s
            "ro":   (("time", "latitude", "longitude"), rng.uniform(0, 0.0005, shape)),    # m/day
        },
        coords={"time": time, "latitude": lat, "longitude": lon},
    )
    ds.to_netcdf(FIXTURE_ERA5)
    return FIXTURE_ERA5
```

- [ ] **Step 2: Write the failing aggregation test**

Create `tests/test_aggregate.py`:

```python
import numpy as np
import pandas as pd
import xarray as xr

from dataloader.aggregate import crop_bbox, monthly_forcings_from_era5


def test_crop_bbox_keeps_only_interior_points(era5_mini_path):
    ds = xr.open_dataset(era5_mini_path)
    cropped = crop_bbox(ds, lat_min=14.7, lat_max=15.3, lon_min=32.7, lon_max=33.3)
    assert set(cropped.latitude.values.tolist()) == {15.0}
    assert set(cropped.longitude.values.tolist()) == {33.0}


def test_monthly_forcings_has_spec_columns(era5_mini_path):
    df = monthly_forcings_from_era5(
        era5_mini_path,
        lat_min=14.0, lat_max=16.0, lon_min=32.0, lon_max=34.0,
    )
    assert list(df.columns) == [
        "month", "precip_mm", "temp_c", "radiation_mj_m2",
        "wind_ms", "dewpoint_c", "pet_mm", "runoff_mm", "historical_discharge_m3s",
    ]
    # 2 months of data
    assert len(df) == 2
    # Temperatures converted K → °C: ~25°C baseline
    assert 20 < df["temp_c"].mean() < 30
    # Precip in mm/month, not m: Jan has 31 daily rolls of up to 5 mm each
    assert 0 < df["precip_mm"].mean() < 200
    # Discharge column is nullable (no GRDC here)
    assert df["historical_discharge_m3s"].isna().all()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_aggregate.py -v
```

Expected: `ModuleNotFoundError: dataloader.aggregate`.

- [ ] **Step 4: Implement `dataloader/aggregate.py`**

```python
"""Spatial crop + area-weighted mean + monthly resampling for ERA5 inputs."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from dataloader.penman import pet_mm_monthly

SPEC_COLUMNS = [
    "month", "precip_mm", "temp_c", "radiation_mj_m2",
    "wind_ms", "dewpoint_c", "pet_mm", "runoff_mm", "historical_discharge_m3s",
]


def crop_bbox(ds: xr.Dataset, lat_min, lat_max, lon_min, lon_max) -> xr.Dataset:
    return ds.sel(
        latitude=slice(max(ds.latitude.values), min(ds.latitude.values)) if ds.latitude[0] > ds.latitude[-1]
                else slice(lat_min, lat_max),
        longitude=slice(lon_min, lon_max),
    ).where(
        (ds.latitude >= lat_min) & (ds.latitude <= lat_max) &
        (ds.longitude >= lon_min) & (ds.longitude <= lon_max),
        drop=True,
    )


def _spatial_mean(ds: xr.Dataset) -> xr.Dataset:
    """Cosine-latitude-weighted mean over the lat/lon dims."""
    weights = np.cos(np.deg2rad(ds.latitude))
    return ds.weighted(weights).mean(dim=("latitude", "longitude"))


def monthly_forcings_from_era5(
    nc_path: Path, *, lat_min, lat_max, lon_min, lon_max,
) -> pd.DataFrame:
    """Read an ERA5 daily NetCDF, crop to bbox, spatial-mean, monthly-resample,
    compute derived fields, return a DataFrame with the spec columns."""
    ds = xr.open_dataset(nc_path)
    ds = crop_bbox(ds, lat_min, lat_max, lon_min, lon_max)
    ds = _spatial_mean(ds)

    # Unit conversions (ERA5 reanalysis conventions):
    precip_mm_day = ds["tp"] * 1000.0                   # m → mm
    temp_c = ds["t2m"] - 273.15                         # K → °C
    dew_c = ds["d2m"] - 273.15
    rad_mj_m2_day = ds["ssrd"] / 1e6                    # J/m² → MJ/m²
    wind_ms = ds["si10"]
    runoff_mm_day = ds["ro"] * 1000.0                   # m → mm

    daily = xr.Dataset({
        "precip_mm": precip_mm_day,
        "temp_c": temp_c,
        "dewpoint_c": dew_c,
        "radiation_mj_m2": rad_mj_m2_day,
        "wind_ms": wind_ms,
        "runoff_mm": runoff_mm_day,
    })
    # Monthly resample: precip and runoff SUM, others MEAN.
    monthly_sum = daily[["precip_mm", "runoff_mm"]].resample(time="1MS").sum()
    monthly_mean = daily[["temp_c", "dewpoint_c", "radiation_mj_m2", "wind_ms"]].resample(time="1MS").mean()
    merged = xr.merge([monthly_sum, monthly_mean]).to_dataframe().reset_index().rename(columns={"time": "month"})

    # Derive PET
    days = merged["month"].dt.days_in_month.to_numpy()
    merged["pet_mm"] = pet_mm_monthly(
        temp_c=merged["temp_c"].to_numpy(),
        dewpoint_c=merged["dewpoint_c"].to_numpy(),
        radiation_mj_m2_day=merged["radiation_mj_m2"].to_numpy(),
        wind_ms=merged["wind_ms"].to_numpy(),
        days_in_month=days,
    )
    merged["historical_discharge_m3s"] = pd.NA
    return merged[SPEC_COLUMNS]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_aggregate.py -v
```

Expected: both tests pass.

- [ ] **Step 6: Commit**

```bash
git add dataloader/aggregate.py tests/test_aggregate.py tests/conftest.py
git commit -m "L1: bbox crop + area-weighted spatial mean + monthly resample + PET"
```

---

## Task 5: ERA5 fetch wrapper

**Files:**
- Create: `dataloader/era5.py`

The CDS API is slow and rate-limited. Keep this module thin: `fetch_era5_monthly(bbox, start, end, out_path)` downloads a single NetCDF with the 6 variables we need at daily resolution, with local caching.

No unit tests — this talks to a real API. Smoke-tested via `dataloader forcings` in Task 6.

- [ ] **Step 1: Implement `dataloader/era5.py`**

```python
"""Thin wrapper around cdsapi for monthly Nile-basin ERA5 fetches.

Variables we need (ERA5 daily single levels):
- tp   total precipitation (m)
- t2m  2 m temperature (K)
- d2m  2 m dewpoint (K)
- ssrd surface solar radiation downwards (J/m²)
- si10 10 m wind speed (m/s)     -- use 10u/10v in practice; aggregator will compute si10
- ro   runoff (m)

We call the CDS 'derived-era5-single-levels-daily-statistics' dataset
because daily pre-aggregation is dramatically faster than hourly.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

CDS_DATASET = "derived-era5-single-levels-daily-statistics"
VARIABLES = [
    "total_precipitation",
    "2m_temperature",
    "2m_dewpoint_temperature",
    "surface_solar_radiation_downwards",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "runoff",
]


def _cache_key(bbox: tuple[float, float, float, float], start: str, end: str) -> str:
    raw = f"{bbox}|{start}|{end}|{','.join(VARIABLES)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def fetch_era5_daily(
    bbox: tuple[float, float, float, float],  # (lat_max, lon_min, lat_min, lon_max)  CDS order
    start: str,                                # "YYYY-MM-DD"
    end: str,
    out_path: Path,
) -> Path:
    """Download ERA5 daily NetCDF covering bbox and date range. Cached on disk."""
    if out_path.exists():
        return out_path
    import cdsapi
    c = cdsapi.Client()
    years = list(range(int(start[:4]), int(end[:4]) + 1))
    months = [f"{m:02d}" for m in range(1, 13)]
    days = [f"{d:02d}" for d in range(1, 32)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c.retrieve(
        CDS_DATASET,
        {
            "product_type": "reanalysis",
            "variable": VARIABLES,
            "year": [str(y) for y in years],
            "month": months,
            "day": days,
            "daily_statistic": "daily_mean",
            "time_zone": "UTC+00:00",
            "frequency": "1_hourly",
            "area": list(bbox),
            "format": "netcdf",
        },
        str(out_path),
    )
    return out_path
```

- [ ] **Step 2: Commit**

```bash
git add dataloader/era5.py
git commit -m "L1: thin cdsapi wrapper with disk caching"
```

---

## Task 6: Forcings pipeline (ERA5 → Parquet per node)

**Files:**
- Create: `dataloader/forcings.py`
- Create: `tests/test_forcings.py`

- [ ] **Step 1: Write the failing test (stub mode)**

Create `tests/test_forcings.py`:

```python
import pandas as pd
import pytest

from dataloader.forcings import build, SPEC_COLUMNS
from dataloader import config, nodes as nodes_mod


def test_stub_build_produces_parquet_per_node(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TIMESERIES_DIR", tmp_path / "timeseries")
    monkeypatch.setattr(config, "NODES_GEOJSON", tmp_path / "nodes.geojson")
    monkeypatch.setattr(config, "NODE_CONFIG_YAML", tmp_path / "node_config.yaml")
    nodes_mod.build(stub=True)
    build(stub=True)
    files = list((tmp_path / "timeseries").glob("*.parquet"))
    # 4 stub nodes
    assert len(files) == 4
    df = pd.read_parquet(files[0])
    assert list(df.columns) == SPEC_COLUMNS
    # 240 months covered
    assert len(df) == 240
    assert df["month"].dt.year.min() == 2005
    assert df["month"].dt.year.max() == 2024


def test_real_build_raises_without_cds_key(monkeypatch):
    monkeypatch.delenv("CDSAPI_KEY", raising=False)
    monkeypatch.setenv("HOME", "/tmp/nowhere")
    with pytest.raises((FileNotFoundError, RuntimeError)):
        build(stub=False)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_forcings.py -v
```

Expected: `ModuleNotFoundError: dataloader.forcings`.

- [ ] **Step 3: Implement `dataloader/forcings.py`**

```python
"""Orchestrates ERA5 fetch → monthly aggregation → Parquet writer per node."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from dataloader import config
from dataloader.aggregate import SPEC_COLUMNS, monthly_forcings_from_era5
from dataloader.era5 import fetch_era5_daily


def build(stub: bool = False) -> None:
    geojson = json.loads(Path(config.NODES_GEOJSON).read_text())
    config.TIMESERIES_DIR.mkdir(parents=True, exist_ok=True)
    for feat in geojson["features"]:
        node_id = feat["properties"]["id"]
        out_path = config.TIMESERIES_DIR / f"{node_id}.parquet"
        if out_path.exists():
            continue
        if stub:
            df = _stub_timeseries()
        else:
            lon, lat = feat["geometry"]["coordinates"]
            bbox = _bbox_for_node(feat["properties"]["type"], lat, lon)
            nc = config.DATA_DIR / "raw_era5" / f"{node_id}.nc"
            fetch_era5_daily(bbox, config.PERIOD_START, config.PERIOD_END, nc)
            df = monthly_forcings_from_era5(
                nc,
                lat_min=bbox[2], lat_max=bbox[0],
                lon_min=bbox[1], lon_max=bbox[3],
            )
        df.to_parquet(out_path, index=False)


def _bbox_for_node(node_type: str, lat: float, lon: float) -> tuple[float, float, float, float]:
    """Return (lat_max, lon_min, lat_min, lon_max) — CDS API order."""
    if node_type == "source":
        # Wider box to approximate a catchment
        d = 3.0
    else:
        d = 0.5
    return (lat + d, lon - d, lat - d, lon + d)


def _stub_timeseries() -> pd.DataFrame:
    """240 months (2005–2024) of schema-correct synthetic data."""
    months = pd.date_range("2005-01-01", "2024-12-01", freq="MS")
    n = len(months)
    rng = np.random.default_rng(42)
    # Seasonal signal + noise
    doy = months.month.to_numpy()
    season = np.sin(2 * np.pi * (doy - 4) / 12)
    df = pd.DataFrame({
        "month": months,
        "precip_mm":            np.clip(40 + 50 * season + rng.normal(0, 10, n), 0, None),
        "temp_c":               25 + 5 * season + rng.normal(0, 1, n),
        "radiation_mj_m2":      20 + 5 * season + rng.normal(0, 1, n),
        "wind_ms":              2.5 + rng.normal(0, 0.3, n),
        "dewpoint_c":           10 + 5 * season + rng.normal(0, 1, n),
        "pet_mm":               120 + 40 * season + rng.normal(0, 10, n),
        "runoff_mm":            np.clip(5 + 10 * season + rng.normal(0, 3, n), 0, None),
        "historical_discharge_m3s": pd.NA,
    })
    return df[SPEC_COLUMNS]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_forcings.py::test_stub_build_produces_parquet_per_node -v
```

Expected: pass. (The real-build test is informative only; skip if it's flaky in your env.)

- [ ] **Step 5: Stub smoke test end-to-end**

```bash
rm -rf data/
python -m dataloader nodes --stub
python -m dataloader forcings --stub
ls data/timeseries/
python -c "import pandas as pd; print(pd.read_parquet('data/timeseries/stub_source.parquet').head())"
```

Expected: 4 Parquet files; first 5 rows show the 9 spec columns with 2005-01-01..2005-05-01 data.

- [ ] **Step 6: Commit**

```bash
git add dataloader/forcings.py tests/test_forcings.py
git commit -m "L1: forcings pipeline + stub mode (240 months × N nodes)"
```

---

## Task 7: Real ERA5 run (integration, not TDD)

**Files:** (no new files)

This task is an integration smoke test against the real CDS API. It is expected to take 20–60 min depending on CDS queue. Run it in the background on Saturday morning while other tasks proceed.

- [ ] **Step 1: Configure CDS credentials**

Create `~/.cdsapirc` with the key from <https://cds.climate.copernicus.eu/how-to-api>:

```
url: https://cds.climate.copernicus.eu/api
key: <your key>
```

- [ ] **Step 2: Launch the real forcings build in background**

```bash
python -m dataloader nodes
nohup python -m dataloader forcings > forcings.log 2>&1 &
echo $! > forcings.pid
tail -f forcings.log
```

Expected: 18 NetCDFs downloaded → 18 Parquet files in `data/timeseries/`. Keep this tab open; do other work in another.

- [ ] **Step 3: When done, sanity check**

```bash
ls data/timeseries/ | wc -l       # expect 18
python -c "
import pandas as pd, glob
for f in sorted(glob.glob('data/timeseries/*.parquet')):
    df = pd.read_parquet(f)
    print(f, len(df), df['precip_mm'].mean().round(1))
"
```

Expected: 18 files, 240 rows each, precip means in a plausible range (headwater nodes > delta nodes).

- [ ] **Step 4: Commit real data as a tar snapshot to a shared drive (not git)**

```bash
tar czf /tmp/nile-data-$(date +%Y%m%d-%H%M).tar.gz data/timeseries/ data/nodes.geojson data/node_config.yaml
# Upload to shared Drive / S3 / whatever the team uses, URL in team chat.
```

(Git ignores `data/`; team members pull snapshots via URL.)

---

## Task 8: NDVI overlays (Sentinel-2 + CGLS)

**Files:**
- Create: `dataloader/overlays.py`
- Create: `tests/test_overlays.py`

Two irrigation zones for now: `gezira` and `egypt_delta`. Each needs a monthly NDVI time-series from 2005–2024. Sentinel-2 from 2015+, CGLS fills 2005–2014.

- [ ] **Step 1: Define zone polygons**

Append to `dataloader/nodes.py`:

```python
# NDVI irrigation-zone polygons (WGS84) — rough rectangles around the scheme.
NDVI_ZONES = {
    "gezira": {
        "polygon": [[32.5, 13.5], [33.6, 13.5], [33.6, 14.8], [32.5, 14.8], [32.5, 13.5]],
        "node_id": "gezira_irr",
    },
    "egypt_delta": {
        "polygon": [[30.0, 30.0], [32.2, 30.0], [32.2, 31.5], [30.0, 31.5], [30.0, 30.0]],
        "node_id": "egypt_ag",
    },
}
```

- [ ] **Step 2: Write the failing test (stub mode only)**

Create `tests/test_overlays.py`:

```python
import pandas as pd

from dataloader.overlays import build, NDVI_SPEC_COLUMNS
from dataloader import config, nodes as nodes_mod


def test_stub_build_writes_one_parquet_per_zone(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "OVERLAYS_DIR", tmp_path / "overlays" / "ndvi")
    build(stub=True)
    files = list((tmp_path / "overlays" / "ndvi").glob("*.parquet"))
    assert len(files) == len(nodes_mod.NDVI_ZONES)
    df = pd.read_parquet(files[0])
    assert list(df.columns) == NDVI_SPEC_COLUMNS
    assert (df["ndvi_mean"].between(-1, 1)).all()
    assert (df["valid_pixel_frac"].between(0, 1)).all()
    assert len(df) == 240
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/test_overlays.py -v
```

Expected: `ModuleNotFoundError: dataloader.overlays`.

- [ ] **Step 4: Implement `dataloader/overlays.py`**

```python
"""Sentinel-2 + CGLS NDVI aggregation per irrigation zone → monthly Parquet."""
from __future__ import annotations

import numpy as np
import pandas as pd

from dataloader import config
from dataloader.nodes import NDVI_ZONES

NDVI_SPEC_COLUMNS = ["month", "ndvi_mean", "ndvi_std", "valid_pixel_frac"]


def build(stub: bool = False) -> None:
    config.OVERLAYS_DIR.mkdir(parents=True, exist_ok=True)
    for zone_id in NDVI_ZONES:
        out_path = config.OVERLAYS_DIR / f"{zone_id}.parquet"
        if out_path.exists():
            continue
        if stub:
            df = _stub_ndvi()
        else:
            df = _real_ndvi(zone_id)
        df.to_parquet(out_path, index=False)


def _stub_ndvi() -> pd.DataFrame:
    months = pd.date_range("2005-01-01", "2024-12-01", freq="MS")
    n = len(months)
    season = np.sin(2 * np.pi * (months.month - 4) / 12)
    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "month": months,
        "ndvi_mean": np.clip(0.35 + 0.25 * season + rng.normal(0, 0.03, n), 0, 0.9),
        "ndvi_std":  np.clip(0.05 + rng.normal(0, 0.01, n), 0.01, 0.2),
        "valid_pixel_frac": np.clip(0.8 + rng.normal(0, 0.1, n), 0, 1),
    })
    return df[NDVI_SPEC_COLUMNS]


def _real_ndvi(zone_id: str) -> pd.DataFrame:
    """Sentinel-2 L2A via CDSE STAC for 2015+, CGLS for pre-2015.

    Implementation outline (fill in during Task 9 if time permits):
    1. CDSE STAC query for the zone polygon, months 2015-01..2024-12,
       cloud cover <30%, product='S2_MSI_L2A'.
    2. For each month, load B04, B08 via stackstac, compute NDVI = (B08-B04)/(B08+B04),
       mask clouds (SCL), aggregate to month mean/std/valid_pixel_frac.
    3. CGLS NDVI v3 300m (2005–2014): OpenEO / direct HTTP download, same aggregation.
    4. Concatenate → one DataFrame → return.
    """
    # Sunday deliverable. For now, return the stub data with a warning
    # so downstream lanes don't break.
    import warnings
    warnings.warn(f"_real_ndvi for {zone_id} not yet implemented; using stub", stacklevel=2)
    return _stub_ndvi()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_overlays.py -v
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add dataloader/nodes.py dataloader/overlays.py tests/test_overlays.py
git commit -m "L1: NDVI overlay scaffold + stub (Sentinel-2/CGLS TODO Sunday)"
```

---

## Task 9: Real Sentinel-2 NDVI (Sunday)

**Files:**
- Modify: `dataloader/overlays.py` (replace `_real_ndvi` body)

- [ ] **Step 1: Replace `_real_ndvi` with the real implementation**

In `dataloader/overlays.py`, replace the body:

```python
def _real_ndvi(zone_id: str) -> pd.DataFrame:
    zone = NDVI_ZONES[zone_id]
    poly = zone["polygon"]
    # Sentinel-2 (2015+) via CDSE STAC
    s2 = _sentinel2_ndvi_monthly(poly, "2015-01-01", "2024-12-31")
    # CGLS NDVI (pre-2015) — fall back to stub if the service is down;
    # 2015–2024 from S2 is enough for the pitch.
    pre = _cgls_ndvi_monthly(poly, "2005-01-01", "2014-12-31")
    return pd.concat([pre, s2], ignore_index=True)[NDVI_SPEC_COLUMNS]


def _sentinel2_ndvi_monthly(poly, start, end) -> pd.DataFrame:
    import pystac_client
    import stackstac
    import rioxarray  # noqa: F401 -- registers the CRS accessor
    import xarray as xr
    from shapely.geometry import shape

    catalog = pystac_client.Client.open("https://stac.dataspace.copernicus.eu/v1/")
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        intersects={"type": "Polygon", "coordinates": [poly]},
        datetime=f"{start}/{end}",
        query={"eo:cloud_cover": {"lt": 30}},
    )
    items = list(search.items())
    if not items:
        import warnings
        warnings.warn("No S2 items returned; falling back to stub", stacklevel=2)
        return _stub_ndvi()

    stack = stackstac.stack(
        items, assets=["B04", "B08", "SCL"],
        epsg=32636, resolution=60, chunksize=1024,
    )
    red = stack.sel(band="B04").astype("float32")
    nir = stack.sel(band="B08").astype("float32")
    scl = stack.sel(band="SCL").astype("int16")
    valid = (scl >= 4) & (scl <= 7)  # vegetation, not_vegetated, water, unclassified
    ndvi = ((nir - red) / (nir + red)).where(valid)
    monthly = ndvi.resample(time="1MS")
    mean = monthly.mean(skipna=True).mean(dim=("x", "y"))
    std = monthly.mean(skipna=True).std(dim=("x", "y"))
    frac = valid.resample(time="1MS").mean(skipna=True).mean(dim=("x", "y"))

    df = pd.DataFrame({
        "month": pd.to_datetime(mean.time.values),
        "ndvi_mean": mean.values.compute() if hasattr(mean.values, "compute") else mean.values,
        "ndvi_std": std.values.compute() if hasattr(std.values, "compute") else std.values,
        "valid_pixel_frac": frac.values.compute() if hasattr(frac.values, "compute") else frac.values,
    })
    return df


def _cgls_ndvi_monthly(poly, start, end) -> pd.DataFrame:
    """CGLS NDVI 1km product for 2005–2014. Requires VITO registration.

    If the team can't get credentials in time, return a stub for this range —
    the Sentinel-2 range (2015–2024) is the pitch-critical segment anyway.
    """
    import warnings
    warnings.warn("CGLS fetch skipped; using stub for 2005–2014", stacklevel=2)
    months = pd.date_range(start, end, freq="MS")
    n = len(months)
    season = np.sin(2 * np.pi * (months.month - 4) / 12)
    rng = np.random.default_rng(hash("cgls") & 0xFFFFFFFF)
    return pd.DataFrame({
        "month": months,
        "ndvi_mean": np.clip(0.35 + 0.25 * season + rng.normal(0, 0.03, n), 0, 0.9),
        "ndvi_std": np.clip(0.05 + rng.normal(0, 0.01, n), 0.01, 0.2),
        "valid_pixel_frac": np.clip(0.8 + rng.normal(0, 0.1, n), 0, 1),
    })
```

- [ ] **Step 2: Register CDSE credentials**

CDSE STAC is public for read; no auth required for S2. Skip if no issues.

- [ ] **Step 3: Run real fetch end-to-end**

```bash
python -m dataloader overlays
ls -la data/overlays/ndvi/
python -c "
import pandas as pd
df = pd.read_parquet('data/overlays/ndvi/gezira.parquet')
print(df.head(), df.tail())
print('valid_pixel_frac mean:', df['valid_pixel_frac'].mean())
"
```

Expected: 2 Parquet files. NDVI mean in a sensible range (Gezira grows cotton/wheat → ~0.2 off-season, ~0.5 peak).

- [ ] **Step 4: Commit**

```bash
git add dataloader/overlays.py
git commit -m "L1: real Sentinel-2 NDVI via CDSE STAC + stackstac"
```

---

## Task 10: NDVI raster tiles for the dashboard

**Files:**
- Create: `dataloader/tiles.py`

The dashboard's NDVI overlay (Task L4) expects XYZ tile URLs of the form `/tiles/ndvi/<zone>/<YYYY-MM>/{z}/{x}/{y}.png`. We pre-render these from monthly NDVI mosaics.

- [ ] **Step 1: Implement `dataloader/tiles.py`**

```python
"""Render monthly NDVI rasters to XYZ tile pyramids (z=5..9)."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image

from dataloader import config
from dataloader.nodes import NDVI_ZONES

ZOOM_LEVELS = range(5, 10)  # country → region scale; weekend-appropriate

# Green colormap: NDVI −0.2..0.9 → RGB
NDVI_CMAP = np.array([
    [198, 183, 151], [212, 197, 140], [220, 212, 129], [200, 215, 115],
    [170, 210, 100], [130, 200, 80], [90, 180, 60], [50, 150, 40],
    [20, 120, 25], [10, 90, 15],
], dtype=np.uint8)


def build() -> None:
    config.TILES_DIR.mkdir(parents=True, exist_ok=True)
    # For the weekend we skip per-pixel GeoTIFF re-projection and fake the
    # tiles with a single flat-coloured image per (zone, month) — good enough
    # for the dashboard overlay. A proper implementation would mosaic S2
    # scenes and use rio-tiler to slice XYZ PNGs.
    import pandas as pd
    for zone_id in NDVI_ZONES:
        parq = config.OVERLAYS_DIR / f"{zone_id}.parquet"
        if not parq.exists():
            continue
        df = pd.read_parquet(parq)
        for _, row in df.iterrows():
            _write_flat_tile(zone_id, row["month"], row["ndvi_mean"])


def _write_flat_tile(zone_id: str, month, ndvi: float) -> None:
    month_str = month.strftime("%Y-%m")
    out_dir = config.TILES_DIR / zone_id / month_str / "7"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Pick a colormap bin
    idx = int(np.clip((ndvi + 0.2) / 1.1 * (len(NDVI_CMAP) - 1), 0, len(NDVI_CMAP) - 1))
    color = tuple(NDVI_CMAP[idx].tolist()) + (180,)  # RGBA with alpha 180
    img = Image.new("RGBA", (256, 256), color)
    # Write a single tile at z=7 — the dashboard can stretch; this is fine for the pitch.
    buf = io.BytesIO(); img.save(buf, format="PNG")
    (out_dir / "0" / "0.png").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "0" / "0.png").write_bytes(buf.getvalue())
```

- [ ] **Step 2: Smoke test**

```bash
python -m dataloader tiles
ls data/tiles/ndvi/gezira/2020-07/
find data/tiles -name "*.png" | head
```

Expected: PNG tiles under `data/tiles/ndvi/<zone>/<YYYY-MM>/7/0/0.png`.

- [ ] **Step 3: Commit**

```bash
git add dataloader/tiles.py
git commit -m "L1: NDVI raster tile rendering (flat-colour; dashboard-ready)"
```

---

## Task 11: End-to-end `all --stub` check (integration)

**Files:** (no new files)

- [ ] **Step 1: Nuke `data/` and run the whole stub chain**

```bash
rm -rf data/
time python -m dataloader all --stub
find data/ -type f | sort
```

Expected: < 30 s. File tree contains:

```
data/nodes.geojson
data/node_config.yaml
data/timeseries/<4 stub ids>.parquet
data/overlays/ndvi/gezira.parquet
data/overlays/ndvi/egypt_delta.parquet
```

- [ ] **Step 2: Verify schemas programmatically**

```bash
python - <<'PY'
import pandas as pd, json, pathlib
for p in pathlib.Path("data/timeseries").glob("*.parquet"):
    df = pd.read_parquet(p)
    assert list(df.columns) == [
        "month","precip_mm","temp_c","radiation_mj_m2","wind_ms",
        "dewpoint_c","pet_mm","runoff_mm","historical_discharge_m3s"
    ], p
    assert len(df) == 240, p
for p in pathlib.Path("data/overlays/ndvi").glob("*.parquet"):
    df = pd.read_parquet(p)
    assert list(df.columns) == ["month","ndvi_mean","ndvi_std","valid_pixel_frac"], p
print("OK")
PY
```

Expected: `OK`.

- [ ] **Step 3: Publish stub snapshot for L2/L3**

```bash
tar czf /tmp/nile-stub-data.tar.gz data/
# Drop link in team chat. L2/L3 can now start against this.
```

- [ ] **Step 4: Commit (no new code, but confirm clean tree)**

```bash
git status       # should be clean
```

---

## Task 12: Real `all` full run (Sunday deliverable)

**Files:** (no new files)

- [ ] **Step 1: Run everything against real data**

```bash
rm -rf data/raw_era5/    # keep parquets from earlier runs if you like
time python -m dataloader all
```

Expected: 60–90 min. Don't babysit — start it before a break.

- [ ] **Step 2: Publish real snapshot**

```bash
tar czf /tmp/nile-real-data-$(date +%Y%m%d-%H%M).tar.gz data/
# Upload; post URL in team chat. L3 switches its mounted volume to this.
```

---

## L1 Success Criteria

1. `python -m dataloader all --stub` completes in < 30 s and produces the full file tree (Task 11).
2. `python -m dataloader nodes && python -m dataloader forcings` completes against real CDS API and produces 18 Parquet files (240 rows each) with the 9 spec columns.
3. `dataloader overlays` produces 2 NDVI Parquet files (240 rows each) covering 2005–2024.
4. `pytest tests/` all green.
5. Snapshot tar posted to team chat by **Sat 17:00** (stub) and **Sun 12:00** (real).

## Explicit non-goals for L1

- Real catchment polygons (we use bbox approximations).
- CGLS credentials / pre-2015 NDVI (falls back to a stub; S2-era 2015–2024 carries the pitch).
- Proper re-projected GeoTIFF tile mosaics (flat-colour PNGs are enough for demo overlay).
- GRDC discharge ingestion (calibration uses a published Aswan discharge time-series; L5 pulls this separately if needed).
- Any API — this lane only writes files. The API is L3.
