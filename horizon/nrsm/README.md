# NRSM

NRSM is a Nile-focused river systems simulator MVP implemented as a dedicated Rust
workspace under `horizon/` so it can grow cleanly inside a larger monorepo.

## Current Scope

- Daily simulation engine with monthly 30-day reporting support
- Directed acyclic river graph with edge losses
- Explicit reservoir nodes with minimal storage and release behavior
- Soft constraints for drinking water, irrigation, and hydropower
- Linear tagged food-production model for irrigated agriculture
- Delivery reliability metrics for drinking water and irrigation targets
- Stable serializable scenario and result types for future Python and ML usage
- Configurable consumptive-use allocation order for policy experiments

## Workspace Layout

- `crates/nrsm-sim-core`: public simulation API and domain model
- `crates/nrsm-cli`: command-line runner for YAML scenarios
- `crates/nrsm-dataloader`: assembler for canonical `horizon/data` CSVs into simulator configs, module CSVs, and staging metadata
- `contracts/scenario.schema.yaml`: machine-readable scenario contract
- `scenarios/nile-mvp`: small Nile-inspired demo scenario
- `docs/nile-dataloader-plan.md`: dataset research and visual loading plan
- `docs/dataloader-node-generation-plan.md`: plan for generating `main/node.md` / `main/modules.md` simulator inputs from sourced data

## MVP Assumptions

- The execution time step is always daily
- Monthly support is handled through 30-day aggregation and optional monthly input series
- Drinking water and irrigation are treated as consumptive uses in v1
- Food production is currently linear by delivered irrigation water
- Hydropower is modeled as a non-consumptive linear conversion on routed outflow
- Default sector allocation priority is drinking water first, then irrigation

Those choices keep the first implementation compact while leaving room for:

- head-based hydropower
- crop and region-specific agriculture modules
- explicit optimization layers on top of the simulator
- Python bindings and training workflows
- richer data loading and scenario assembly from Copernicus and supplemental datasets

## Run The Demo

```powershell
cargo run -p nrsm-cli -- scenarios/nile-mvp/scenario.yaml
```

Write visualization-ready time series CSVs while running a scenario:

```powershell
cargo run -p nrsm-cli -- scenarios/nile-mvp/scenario.yaml --json --results-dir data\results\nile-mvp
```

The results directory contains one CSV per node, named `<node_id>.csv`, plus a
network-wide `summary.csv`. Per-node CSV rows follow the simulator reporting
frequency (`daily` by default, or 30-day periods when `settings.reporting` is
`monthly30_day`).

Per-node columns:

| Column | Meaning |
| --- | --- |
| `period_index` | Zero-based output period index. |
| `start_day` / `end_day_exclusive` | Day offsets from the start of the run. |
| `duration_days` | Number of simulated days in the row. |
| `node_id` | Node id from the scenario. |
| `reservoir_level` | End-of-period storage volume in m3. |
| `total_inflow` | Local catchment plus upstream inflow volume over the period. |
| `evaporation` | Water lost to evaporation over the period. |
| `drink_water_met` / `unmet_drink_water` | Drinking-water demand served and shortfall. |
| `food_produced` | Food units produced by the node. |
| `production_release` | Controlled hydropower/production release volume. |
| `spill` | Uncontrolled reservoir overflow volume. |
| `release_for_routing` | `production_release + spill`, before edge fractions are applied. |
| `downstream_release` | Routed volume sent to downstream nodes after connection fractions. |
| `routing_loss` | `release_for_routing - downstream_release`, useful for plotting reach losses. |
| `energy_value` | Hydropower value proxy for the period. |

`summary.csv` uses the same period columns and aggregates the water, food, and
energy fields across all nodes. Calendar dates are not emitted yet; consumers
should treat `start_day` and `end_day_exclusive` as offsets from the scenario
start date used by the data assembler.

## Assemble Canonical Data

```powershell
cd horizon\nrsm
cargo run -p nrsm-dataloader -- assemble --input ..\data --output data\generated --start-date 2005-01-01 --end-date 2005-01-31
cargo run -p nrsm-cli -- data\generated\config.yaml --json --pretty
```

The `assemble` command reads the Python dataloader's checked-in CSV bundle under
`horizon/data` and writes simulator-ready files. The older deterministic seed
path is still available for tests and demos:

```powershell
cargo run -p nrsm-dataloader -- seed --output data/generated --start-date 2020-01-01 --end-date 2020-01-31 --scenarios 3
```
