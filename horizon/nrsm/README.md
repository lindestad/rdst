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
| `action` | Production-level fraction applied to this node for the period. Daily rows show the exact action; 30-day rows show the average action across the period. |
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

## Actions

Each node can receive a per-day production action through
`actions.production_level`. The value is a fraction in `[0, 1]` that scales the
node's `max_production` release after drinking water and food production have
already been served. Values outside `[0, 1]` are clamped by the simulator.

Actions use the same constant-or-CSV `ModuleSeries` shape as the environmental
modules:

```yaml
actions:
  production_level:
    type: csv
    filepath: modules/victoria.actions.csv
    column: scenario_1
```

The CSV shape is:

```csv
date,scenario_1,scenario_2
2005-01-01,1.0,0.75
2005-01-02,0.6,0.25
```

If a node has no `actions` block, the simulator falls back to
`settings.production_level_fraction` for backward compatibility. The canonical
data assembler writes one default `<node_id>.actions.csv` per node with full
production (`1.0`) so policy and optimizer code can replace those time series
without changing the scenario structure.

External policy code can also pass an action directory at runtime:

```powershell
cargo run -p nrsm-cli -- data\generated\config.yaml --json --results-dir data\results\policy-a --actions-dir data\policy-a\actions --action-column scenario_1
```

`--actions-dir` expects one CSV for every node. Files are matched as either
`<node_id>.actions.csv` or `<node_id>.csv`; each file must have `date` plus the
selected action column. Runtime overrides replace the scenario's configured
`actions.production_level` series before the simulator loads CSV data.

## Optimizer API

The CLI and action CSVs are the reproducible file-based path. Optimizers should
use the in-memory API so the scenario is parsed, validated, CSV-loaded, and DAG
compiled once:

```rust
let mut scenario: Scenario = serde_yaml::from_str(&config_yaml)?;
scenario.load_module_csvs(config_dir)?;
let prepared = PreparedScenario::try_new(scenario)?;

let actions = vec![1.0; prepared.expected_action_len()];
let result = prepared.simulate_with_actions(&actions)?;
let summary = prepared.simulate_summary_with_actions(&actions)?;
```

The action matrix is a flat row-major `T x N` array:

```text
actions[day * node_count + node_index]
```

`prepared.node_ids()` returns the stable node order used for `node_index`.
Action values are clamped to `[0, 1]`. Matrix actions override any
`actions.production_level` series already present in the scenario.
Use `simulate_summary_with_actions` for optimizer/loss loops that do not need
per-node traces; it skips building the full result time series.

Python bindings live in `crates/nrsm-py` and expose the same prepared simulator:

```python
import json
import nrsm_py

sim = nrsm_py.PreparedScenario.from_yaml("data/generated/config.yaml")
actions = [1.0] * sim.expected_action_len()
summary = json.loads(sim.run_actions_summary_json(actions))
```

Build the Python extension with maturin from `horizon/nrsm/crates/nrsm-py`.

## Assemble Canonical Data

```powershell
cd horizon\nrsm
cargo run -p nrsm-dataloader -- assemble --input ..\data --output data\generated --start-date 2005-01-01 --end-date 2005-01-31
cargo run -p nrsm-cli -- data\generated\config.yaml --json --pretty
```

The `assemble` command reads the checked-in canonical data bundle under
`horizon/data` and writes simulator-ready files. The current MVP topology uses
the 13 hydmod catchment nodes in `horizon/data/topology/nodes.csv`; catchment
inflow and evaporation come from `horizon/data/hydmod/daily`, while food and
energy modules come from the agriculture and electricity-price folders.

The older deterministic seed path is still available for tests and demos:

```powershell
cargo run -p nrsm-dataloader -- seed --output data/generated --start-date 2020-01-01 --end-date 2020-01-31 --scenarios 3
```
