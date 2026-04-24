# Nile Digital Twin — Design

**Event:** CASSINI Hackathon, *Space for Water* track
**Team:** 5 people, one weekend
**Date:** 2026-04-24
**Status:** Design — approved, ready to plan

## Purpose

A policy what-if sandbox for the Nile basin, grounded in historical ERA5 climate reanalysis and Copernicus satellite observations. Users move policy sliders (reservoir release schedules, irrigation area, environmental-flow constraints) and see cascading effects on three KPIs computed in real units: drinking-water reliability (% population served), food production (tonnes/yr), and hydropower output (GWh/yr). Scenarios are scored and comparable. A stretch-goal optimizer searches a policy space to suggest Pareto-better schedules.

The pitch hook: "What if Ethiopia holds back more Blue Nile water for power generation? Watch the cascade from GERD to the Egyptian Delta — in real units, validated against satellite-observed crop NDVI."

## Scope and explicit non-goals

**In scope:**
- ~15–20 curated nodes along the main stem, both source branches (Blue & White Nile), the Sudd wetland, major dams (GERD, Roseires, Merowe, Aswan/Nasser), confluence at Khartoum, Atbara tributary, two aggregate irrigation zones (Gezira, Egypt-ag), two municipal demands (Cairo, Khartoum), Mediterranean sink.
- Monthly time step, 2005–2024 (240 steps).
- Historical forcings from ERA5 (precipitation, temperature, radiation, wind, runoff, evapotranspiration).
- Satellite overlay: Sentinel-2 NDVI (2015+) and CGLS NDVI (pre-2015) over irrigation zones.
- Mass-balance simulator with Penman-style reservoir evaporation and Muskingum reach routing.
- Fixed-coefficient KPI coupling (no NDVI-to-productivity feedback in committed scope).
- Scenario save / load / weighted scoring / side-by-side compare.
- Map-first React dashboard with policy sliders, KPI charts, month scrubber, NDVI overlay.
- Local `docker compose` demo.

**Explicitly out of scope (YAGNI):**
- User auth, multi-tenant, versioned scenario history, real-time collaboration.
- 3D visualization, mobile UI, i18n, a11y beyond basic keyboard nav.
- Groundwater modeling, country political simulation, forecasting beyond historical replay.
- Any sub-monthly dynamics (no flood-pulse routing, no hourly HEP dispatch).

**Stretch goals (only if Sunday 12:00 hard-stop allows):**
- **Scope-C optimizer:** grid search over a parameterized policy space, given user weights, returns Pareto-better policies.
- **NDVI-modulated food KPI:** Sentinel-2 NDVI modulates the crop-water-productivity coefficient, closing the space-data loop.

## System architecture

Four layers, each with a hard interface so lanes can work in parallel.

```
┌─────────────────────────────────────────────────────────────┐
│  DATALOADER  (Python CLI scripts)                           │
│  ─ fetch_era5.py         → Parquet per node                 │
│  ─ fetch_sentinel2.py    → NDVI Parquet per irrigation zone │
│  ─ fetch_reservoir.py    → static reservoir metadata        │
│  ─ build_nodes.py        → nodes.geojson + node_config.yaml │
└─────────────────────────────────────────────────────────────┘
                              │ writes
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  CANONICAL STORE  (data/ directory, gitignored)             │
│  ─ data/nodes.geojson                   (geometry)          │
│  ─ data/node_config.yaml                (params per node)   │
│  ─ data/timeseries/<node_id>.parquet    (monthly forcings)  │
│  ─ data/static/reservoirs.yaml          (head, turbines)    │
│  ─ data/overlays/ndvi/<zone_id>.parquet (sat observations)  │
└─────────────────────────────────────────────────────────────┘
                              │ read by
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  SIM ENGINE  (Python package, no web deps)                  │
│  ─ Graph loader • Node types • Time-stepper • KPI calc      │
│  ─ Callable directly (CLI) OR via API                       │
└─────────────────────────────────────────────────────────────┘
                              │ wrapped by
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  API  (FastAPI, stateless + JSON scenario store)            │
│  ─ /nodes • /nodes/{id} • /nodes/{id}/timeseries            │
│  ─ /overlays/ndvi/{zone_id}                                 │
│  ─ /scenarios/run • /scenarios • /scenarios/compare         │
│  ─ /optimize                           (stretch)            │
└─────────────────────────────────────────────────────────────┘
                              │ consumed by
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  DASHBOARD  (React + Vite + MapLibre GL + Plotly)           │
│  ─ Map-first, left-rail policy sliders, right-rail KPIs     │
│  ─ Compare view for two scenarios                           │
└─────────────────────────────────────────────────────────────┘
```

**Rejected alternatives:**
- **Monolithic Streamlit app.** Shippable in a day but dashboard polish is a ceiling, and "dataloader in a known format" becomes awkward.
- **Files-only, no API.** Parquet + static file server can't trigger parameterized sim runs.

## Data contract

The dataloader's output is the most reusable artifact of the weekend. The schema below is the contract between L1 and everything downstream.

### `data/nodes.geojson`

One `Feature` per node. Properties define topology (`upstream`, `downstream`) and type.

```json
{ "type": "Feature",
  "geometry": { "type": "Point", "coordinates": [lon, lat] },
  "properties": {
    "id": "gerd",
    "name": "Grand Ethiopian Renaissance Dam",
    "type": "reservoir",
    "country": "ET",
    "upstream": ["lake_tana_outlet"],
    "downstream": ["blue_nile_roseires"]
  }
}
```

### `data/node_config.yaml`

Static per-node parameters. One block per node; reach params under `reaches:`.

```yaml
nodes:
  gerd:
    type: reservoir
    storage_capacity_mcm: 74000
    storage_min_mcm: 14800
    surface_area_km2_at_full: 1874
    hep:
      nameplate_mw: 6450
      head_m: 133
      efficiency: 0.9
    initial_storage_mcm: 14800
  gezira_irr:
    type: demand_irrigation
    area_ha_baseline: 900000
    crop_water_productivity_kg_per_m3: 1.2
  sudd:
    type: wetland
    evap_loss_fraction_baseline: 0.5
  cairo_muni:
    type: demand_municipal
    population_baseline: 20000000
    per_capita_l_day: 200
  lake_victoria_outlet:
    type: source
    catchment_area_km2: 195000          # used to convert mm runoff to m³/s
    catchment_scale: 1.0                # calibration knob, tuned against GRDC
  # ... ~15–20 nodes total

reaches:
  gerd_to_roseires:
    travel_time_months: 0.5
    muskingum_k: 0.5
    muskingum_x: 0.2
  # ...
```

### `data/timeseries/<node_id>.parquet`

Monthly forcings at each node. Columns:

| column | unit | source |
|---|---|---|
| `month` | `YYYY-MM-01` (timestamp) | — |
| `precip_mm` | mm/month | ERA5 `tp` |
| `temp_c` | °C | ERA5 `t2m` |
| `radiation_mj_m2` | MJ/m²/month | ERA5 `ssrd` |
| `wind_ms` | m/s | ERA5 `si10` |
| `dewpoint_c` | °C | ERA5 `d2m` (for humidity in Penman) |
| `pet_mm` | mm/month | derived (Penman, computed by dataloader) |
| `runoff_mm` | mm/month | ERA5 `ro` (basin-area-weighted for headwaters) |
| `historical_discharge_m3s` | m³/s | GRDC (optional, calibration only) |

### `data/overlays/ndvi/<zone_id>.parquet`

Satellite observation, separate from forcings so a satellite-data outage doesn't block sim development.

| column | unit | source |
|---|---|---|
| `month` | `YYYY-MM-01` | — |
| `ndvi_mean` | dimensionless | Sentinel-2 L2A (2015+) / CGLS (pre-2015) |
| `ndvi_std` | dimensionless | same |
| `valid_pixel_frac` | 0–1 | cloud-mask quality indicator |

### `data/static/reservoirs.yaml`

Supplementary reservoir metadata (head curves, turbine counts) referenced from `node_config.yaml`.

### `data/scenarios/<uuid>.json`

Written by the API on save. Format defined in the sim engine section.

## Sim engine

**Time stepping:** monthly, Jan-2005 → Dec-2024 (240 steps). For each step, the engine sweeps the node graph in topological order (upstream → downstream) and computes each node's balance. One full sim run is ≈10 ms.

### Node taxonomy

| Type | Behavior |
|---|---|
| `source` | Headwater boundary. Inflow = `runoff_mm × catchment_area_km2 × catchment_scale`, converted to m³/s. No storage. `catchment_scale` is a per-node calibration knob. |
| `reservoir` | `storage_t = storage_{t-1} + inflow − evap − release`. Evap: Penman PET × surface-area(storage) × coefficient. Release: driven by policy lever. Clamped to `[storage_min, storage_capacity]`. Optional `hep`: `energy_gwh = release_m3 × head_m × efficiency × ρ × g / 3.6e12`, with constant `head_m` per reservoir (head-vs-storage rating curves are out of scope). |
| `reach` | Muskingum routing: output at `t` depends on input at `t` and `t-1` via `(K, x)`. |
| `confluence` | Pure sum of upstream flows. Zero storage, zero loss. |
| `wetland` | Configurable evap loss fraction (Sudd default 0.5), optionally PET-modulated. Outflow = inflow × (1 − loss). |
| `demand_municipal` | Pulls `population × per_capita_l_day × days_in_month / 1000` m³ upstream. Shortfall tracked. KPI: served fraction. |
| `demand_irrigation` | Pulls `area_ha × monthly_crop_water_req(month)` upstream (FAO seasonal curve). KPI: delivered fraction → tonnes via productivity coefficient. |
| `sink` | Records outflow. Minimum-environmental-flow constraint applied as a scoring penalty, not a hard clamp. |

### Policy levers (slider-driven)

- Per-reservoir release schedule: `"historical"` | `"rule_curve"` | `"manual"` (user-set monthly m³/s).
- Per-demand scale factor on baseline area / population.
- Global minimum delta flow target (scoring penalty if violated).
- Global scoring weights `(w_water, w_food, w_energy)`, normalized to sum to 1.

### Scenario object

```python
Scenario = {
  id, name, created_at,
  period: (start, end),
  policy: { reservoirs: {...}, demands: {...}, constraints: {...}, weights: {...} },
  results: {                                   # filled after run
    timeseries_per_node: { node_id → DataFrame(month, storage, release, evap, ...) },
    kpi_monthly: DataFrame(month, water_served_pct, food_tonnes, energy_gwh),
    score: float,
    score_breakdown: { water, food, energy, delta_penalty }
  }
}
```

### KPI definitions (real-world units)

- **Drinking water:** `served_pct = min(1, delivered / (population × per_capita_l_day × days))` per municipal node; aggregate via population-weighted mean. Reported as `%` and `m³/person/day`.
- **Food:** `tonnes = sum over irrigation nodes of (delivered_m3 × productivity_kg_per_m3) / 1000`. Reported as tonnes wheat-equiv/year.
- **Energy:** `GWh = sum over HEP reservoirs of (release_m3 × head_m × efficiency × ρ × g / 3.6e12)` with ρ = 1000 kg/m³, g = 9.81 m/s². Reported as GWh/month and TWh/year.

Crop-water-productivity coefficients come from published FAO AquaStat tables for Gezira (cotton/wheat rotation) and Egyptian Delta (rice/maize/wheat). Reservoir head, nameplate capacity, and efficiency come from public dam databases.

### Calibration

Baseline scenario = "historical" release policies, baseline irrigation areas. Compare simulated Aswan discharge to GRDC observed discharge over 2005–2024. Target: monthly RMSE < 20%. Tune source-catchment scaling factors and Sudd evap fraction until met, or accept a larger error and be transparent in the pitch.

## API surface

FastAPI, stateless except for an on-disk JSON scenario store.

```
GET    /health
GET    /nodes                            → nodes.geojson
GET    /nodes/{id}                       → static config for one node
GET    /nodes/{id}/timeseries
       ?start=2005-01&end=2024-12
       &vars=precip_mm,pet_mm,...        → monthly forcings as column-oriented JSON
GET    /overlays/ndvi/{zone_id}
       ?start=...&end=...                → NDVI time-series for validation overlay

POST   /scenarios/run                    → runs sim synchronously (~ms), returns full result
GET    /scenarios                        → list (metadata only)
GET    /scenarios/{id}                   → one scenario, results included
POST   /scenarios/{id}/save              → promote run to saved
DELETE /scenarios/{id}
POST   /scenarios/compare
       body: { scenario_ids: [a, b] }    → structured diff of KPIs + per-node deltas

POST   /optimize                         → STRETCH. Grid search over policy space.
GET    /optimize/{job_id}                → poll
```

**Conventions:**
- Timestamps: ISO 8601 month (`YYYY-MM`).
- Time-series: column-oriented `{ "month": [...], "values": { var: [...] } }`.
- Scenario policy has a default for every field so partial POSTs work.
- All runs are synchronous except `/optimize` (background task).

**Persistence:** `data/scenarios/<uuid>.json`. Loaded on startup. Gitignored. A team member can copy a scenario file across laptops for demo rehearsal without DB faff.

## Dashboard UI

React + Vite + TypeScript + MapLibre GL JS + Plotly. SPA. No SSR/SSG.

### Top-level state

```
activeScenarioId           # editing in left rail
runningScenarioResults     # last sim response; drives right rail + map styling
savedScenarios[]           # loaded from /scenarios on mount
compareMode                # bool
compareScenarioIds         # [a, b] when in compare mode
overlayToggle              # { ndvi, flow, storage }
```

### Layout (map-first)

```
┌─────────────────────────────────────────────────────────────────────┐
│  HEADER:  Nile Digital Twin  │  [ Run ]  [ Save ]  [ Compare ]     │
├──────────────────┬──────────────────────────────┬───────────────────┤
│ LEFT RAIL        │  MAP (MapLibre)              │  RIGHT RAIL       │
│ Policy levers    │  - Nile basemap              │  KPI panel:       │
│                  │  - Node layer (circles sized │                   │
│ Period:          │    by storage/flow; colored  │  Water 94%        │
│  2005 - 2024     │    by served% or release)    │  ─── chart ───    │
│                  │  - Reach layer (flow-stroke) │                   │
│ GERD release     │  - NDVI overlay toggle       │  Food  12.4 Mt    │
│ Aswan release    │  - Click node → side popover │  ─── chart ───    │
│ Gezira irr ha    │    with node's monthly plot  │                   │
│ Egypt irr ha     │                              │  Energy 38 TWh    │
│ Min delta flow   │                              │  ─── chart ───    │
│                  │                              │                   │
│ Weights          │                              │  Score: 72        │
│  Water / Food /  │                              │  Breakdown ...    │
│  Energy          │                              │                   │
├──────────────────┴──────────────────────────────┴───────────────────┤
│ BOTTOM TRAY: saved scenarios (collapsible; tap one → loads it)      │
└─────────────────────────────────────────────────────────────────────┘
```

### Map styling (the "wow" moments)

- Node radius ∝ `sqrt(storage)` for reservoirs, ∝ `sqrt(flow)` for reach/confluence nodes.
- Node fill color: demand nodes by served fraction (red→green); reservoirs by release (blue scale).
- Reach line stroke width ∝ monthly flow — the user *sees* the cascade when they drop GERD release.
- Month scrubber at the bottom animates the whole map through the sim period.
- NDVI overlay: pre-rendered per-month raster tile source (produced by the dataloader); fades with the month scrubber.

### Compare view

When Compare is toggled, the map area splits to two side-by-side maps driven by their respective scenarios. Right rail shows **diff** chips (`Food −2.3 Mt`, `Energy +6 TWh`). Sliders disabled in compare mode.

## Team swim lanes and weekend timeline

5 people × 2 days ≈ 60 person-hours after sleep/food.

| Lane | Owner | Saturday | Sunday |
|---|---|---|---|
| **L1 — Dataloader** | 1 | ERA5 monthly fetch via `cdsapi` for node catchments; Parquet writer; `nodes.geojson` + `node_config.yaml` curated. Reservoir metadata from public sources. | Sentinel-2 NDVI via STAC + `stackstac` for Gezira + Delta; CGLS for pre-2015; pre-render NDVI tile sets. |
| **L2 — Sim engine** | 1 | Graph loader; node-type classes; topological sweep; mass balance for reservoir / reach / confluence / sink / source. Unit tests with synthetic graphs. | Penman evap; Muskingum routing; demand nodes; KPI calculator; scenario save/load. |
| **L3 — API** | 1 | FastAPI skeleton; `/nodes`, `/nodes/{id}`, `/nodes/{id}/timeseries`. Sim stub returning fixtures — *unblocks L4 early*. | Wire real sim; `/scenarios/run`, `/scenarios`, `/scenarios/compare`. Dockerfile + compose. |
| **L4 — Dashboard** | 2 | Vite + React scaffold; MapLibre basemap; node layer from fixtures; left-rail sliders; right-rail KPIs. Stubbed API. | Wire real API; scenario save/load; Compare view; month scrubber; NDVI overlay; demo polish. |
| **L5 — Floater** | 1 | Calibration run (simulated vs GRDC at Aswan); tune source scaling + Sudd loss until <20% RMSE. Seed 3 canned demo scenarios. | **If ahead:** optimizer stretch (Scope C). **Else:** pitch deck, QR code, rehearsals. |

### Integration moments

- **Saturday 17:00** — L3 publishes stub API contract; L4 wires against the stub so Sunday's "real API" switch is a one-line env change.
- **Sunday 12:00** — Feature freeze. Everyone on polish, bugs, rehearsals.
- **Sunday 15:00** — Demo freeze. No more code. Pitch rehearsal.

### Parallelization guardrails

- L1 produces a stub `node_config.yaml` with 3–4 nodes Saturday morning so L2/L3 aren't blocked by the full curation.
- L4 never touches the sim — only consumes API responses. Stubbed API makes this safe.
- Early-finishing lanes join L4 (dashboard polish scales best with hands).

### Risks, ranked

1. **ERA5 fetch queuing.** CDS API is rate-limited. *Mitigation:* L1 fires all fetches Saturday first thing; fall back to pre-downloaded monthly aggregates if slow.
2. **Cloud cover on Sentinel-2 over the Delta.** NDVI patchy. *Mitigation:* filter via `valid_pixel_frac`; fall back to CGLS across the full period if needed.
3. **Calibration worse than 20%.** *Mitigation:* accept and be transparent in the pitch.
4. **Optimizer stretch eats Sunday.** *Mitigation:* hard 12:00 stop; drop if not clearly shippable.

## Testing, success criteria, what we don't test

### Testing

| Component | Test | Why |
|---|---|---|
| Sim engine | Unit: 3-node synthetic graph. Mass conservation (`inflow = outflow + Δstorage + evap`). Storage bounded. | Physics must be right — wrong mass balance poisons every demo number. |
| Sim engine | Golden file: baseline 2005–2024 → simulated Aswan discharge within 20% monthly RMSE of GRDC. CI fails on drift. | Calibration guard against silent regressions. |
| Dataloader | Fixture-based schema tests: every required column, correct dtypes. | The data contract is the most reusable artifact — schema must not drift. |
| API | One happy-path integration test per endpoint with `TestClient` + tiny fixture `data/`. No sim mocking. | Catches sim+API integration bugs. |
| Dashboard | No automated tests. Manual smoke checklist pre-demo: load → move each slider → run → save → compare → toggle NDVI → scrub months. | Playwright setup eats more time than it saves at this scale. |

### Success criteria

1. **Baseline runs.** Default policy → three KPI charts for 2005–2024, animated map. Simulated Aswan discharge within 20% monthly RMSE of GRDC.
2. **What-if demonstrated.** Move GERD release slider (e.g., 3-year vs 7-year fill). Re-run. Downstream energy at Aswan drops; food tonnage in Egypt-ag drops. Save scenario.
3. **Compare works.** Two scenarios side-by-side with KPI diffs.
4. **Space data is visible.** NDVI overlay toggles; Sentinel-2 / CGLS tiles over Gezira + Delta animate with the month scrubber.
5. **Three canned demo scenarios** load cleanly. Rehearsal runs without crashes.
6. **`docker compose up`** from fresh checkout produces a working app in < 5 min.

### What we are deliberately *not* testing

- UI accessibility, performance, cross-browser.
- Load / concurrency (demo is single-user).
- Long-horizon numerical stability (we only run 240 steps).
- Anything not touched by the 6 success criteria above.

## Open questions (for the implementation-plan phase, not this design)

- Exact node ID naming scheme (snake_case confirmed; prefix conventions TBD by L1 on Saturday).
- Whether to use MapLibre with a free raster basemap or MapTiler/Mapbox (requires API key) — L4's call Saturday.
- Optimizer algorithm for Scope-C stretch (grid search vs. random search vs. simple LP over release schedules) — L5's call Sunday.
