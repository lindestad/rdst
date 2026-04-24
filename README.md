# Nile Digital Twin

A policy what-if sandbox for the Nile basin, built for the **CASSINI Hackathon — *Space for Water*** track. Move sliders, watch cascading impact on drinking water, food, and hydropower downstream. Grounded in historical ERA5 climate reanalysis and validated against Sentinel-2 NDVI.

> *"What if Ethiopia holds back more Blue Nile water for power? Here's what breaks in Egypt, month by month, in real units."*

## Architecture

Four-layer pipeline. Each layer has a hard interface so lanes can work in parallel.

```
┌──────────────────────────────────────────────────────────┐
│ L4  Dashboard  — React + Vite + MapLibre + Plotly        │
│                  map, sliders, KPI sparklines, compare   │
└──────────────────────────────────────────────────────────┘
                             ▼ HTTP (vite proxy → /api)
┌──────────────────────────────────────────────────────────┐
│ L3  API  — FastAPI, stateless + file-backed scenarios    │
│            /nodes /timeseries /overlays /scenarios/*     │
└──────────────────────────────────────────────────────────┘
                             ▼ imports
┌──────────────────────────────────────────────────────────┐
│ L2  Sim Engine  — pure Python, ~10 ms per run            │
│     8 node types · Muskingum routing · Penman evap       │
│     mass balance · HEP (spillway bypasses turbine)       │
│     KPIs (water/food/energy) · weighted scoring          │
└──────────────────────────────────────────────────────────┘
                             ▼ reads
┌──────────────────────────────────────────────────────────┐
│ L1  Dataloader  — CLI scripts, `--stub` for instant data │
│     ERA5 · Sentinel-2 NDVI · bbox crop · Penman PET      │
│     → Parquet per node + GeoJSON + YAML                  │
└──────────────────────────────────────────────────────────┘
```

The dataloader's `data/` tree is the canonical contract between layers:

```
data/
├── nodes.geojson               # geometry + topology
├── node_config.yaml            # static params per node
├── timeseries/<id>.parquet     # monthly forcings (precip, PET, runoff, ...)
├── overlays/ndvi/<zone>.parquet
└── scenarios/<uuid>.json       # saved scenarios with results
```

## Quick start

```bash
git clone <repo> && cd rdst && git checkout storm
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cd frontend && npm install && cd ..

# Produce stub data (0.6 s):
python -m dataloader all --stub

# Terminal 1 — API:
NILE_USE_REAL_SIM=1 python -m api

# Terminal 2 — dashboard:
cd frontend && npm run dev

# Open http://localhost:5173
```

Click **Run**, move sliders, watch KPIs update, **Save** a scenario, open **Compare** with a second scenario and see deltas.

## Project layout

```
dataloader/        L1 — Parquet + GeoJSON producer
  nodes.py           curated 19-node Nile graph
  penman.py          FAO-56 potential evap
  aggregate.py       bbox crop + monthly resample
  forcings.py        ERA5 → Parquet orchestrator
  overlays.py        NDVI Parquet per zone
  tiles.py           flat-colour raster tiles

simengine/         L2 — Pure-Python sim
  graph.py           YAML loader + topological sort
  nodes/             source · reservoir · reach · confluence
                     wetland · demand_irrigation · demand_municipal · sink
  engine.py          topo-sweep time stepper
  scenario.py        pydantic models + file IO
  kpi.py             aggregate timeseries → 3 KPIs
  scoring.py         weighted sum + delta penalty

api/               L3 — FastAPI wrapper
  routes/            health · nodes · overlays · scenarios
  stub_sim.py        fake results for offline dev (NILE_USE_REAL_SIM != 1)
  scenario_store.py  file-backed CRUD

frontend/          L4 — React + Vite SPA
  src/api/           TS client + types
  src/state/         Zustand store
  src/components/    Header · LeftRail (sliders) · RightRail (KPIs)
                     NileMap · NodeInspector · MonthScrubber
                     ScenarioTray · CompareView
  src/lib/           Plotly wrapper · NDVI tile overlay

tests/             55 Python tests
  test_engine_mass_balance.py    golden: mass conservation <0.1%
  test_integration_stub.py       L1 stub → L2 sim end-to-end
  …

frontend/tests/    7 TypeScript tests (vitest)

docs/superpowers/
  specs/           2026-04-24-nile-digital-twin-design.md
  plans/           L1–L5 implementation plans (hand-offable)
```

## Node physics (one paragraph)

Monthly time step. For each `t`, the engine sweeps nodes in topological order. **Sources** turn ERA5 runoff over a catchment into m³/s. **Reservoirs** do mass balance (`storage += inflow − release − evap`), clamp to `[min, capacity]`, compute HEP energy from turbined release only — spillway bypasses turbines — and report `spill_m3s` separately. **Reaches** apply Muskingum routing (lag + attenuation). **Wetlands** lose a configurable fraction (Sudd ≈ 50 %). **Demand nodes** take water up to their need and track served fraction; irrigation converts delivered volume to tonnes via FAO crop-water-productivity. **Sinks** accumulate outflow and flag environmental-flow shortfalls.

## The three KPIs

- **Water** — `% population served` at municipal demand nodes (Cairo, Khartoum).
- **Food** — tonnes/month from irrigation, using FAO productivity factors.
- **Energy** — GWh/month = `release_m3 × head × η × ρ × g / 3.6e12` at HEP dams.

A single weighted score (default 40/30/30) with a delta-flow penalty summarises each scenario.

## What works today

```bash
pytest                        # 55 passed (0.8 s)
cd frontend && npx vitest run # 7 passed
npx vite build                # build clean
```

- Full stack runs. Browser talks to API talks to real L2 sim. Numbers are real (score 0.7 on stub data, HEP output scales with head × release).
- The reservoir physics went through **one code-review round** that caught a real bug: spilled water was generating HEP energy. Now fixed, with a dedicated test locking the split.

## What's left

- **Real data.** Swap `--stub` for `python -m dataloader all` with CDS credentials (CDS account + `~/.cdsapirc`) for ERA5 and `pip install pystac-client stackstac` for Sentinel-2. `data/` layout is already correct.
- **Calibration (L5).** Tune `catchment_scale` on source nodes against GRDC observed Aswan discharge. Target: monthly RMSE < 20 %.
- **Canned demo scenarios.** `baseline`, `gerd_fast_fill`, `drought_2010` — scaffolded in the plan.
- **Docker compose.** `Dockerfile.api` + `docker-compose.yml` template lives in `docs/superpowers/plans/L3-api.md` Task 8.
- **Pitch.** 3-min script lives in `docs/superpowers/plans/L5-integration.md`.

## Design and plan documents

- **Spec:** [`docs/superpowers/specs/2026-04-24-nile-digital-twin-design.md`](docs/superpowers/specs/2026-04-24-nile-digital-twin-design.md)
- **Plans (one per lane, hand-offable):** [`docs/superpowers/plans/2026-04-24-nile-digital-twin/`](docs/superpowers/plans/2026-04-24-nile-digital-twin/)

## Environment variables

| Var | Purpose | Default |
|---|---|---|
| `NILE_DATA_DIR` | Where API reads data/ from | `./data` |
| `NILE_USE_REAL_SIM` | `1` routes `/scenarios/run` through L2; else returns canned stub | unset (stub) |
| `VITE_API_BASE` | Frontend API base URL | `/api` (via vite proxy) |

## Tech stack

**Backend:** Python 3.11 · FastAPI · pydantic · pandas · pyarrow · xarray · numpy · typer.
**Frontend:** React 18 · TypeScript · Vite · Tailwind · Zustand · MapLibre GL · Plotly.
**Tests:** pytest (55) · vitest (7).
