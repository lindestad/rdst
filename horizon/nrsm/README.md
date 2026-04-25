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
- `scenarios/nile-mvp`: Nile-inspired demo and dated past/future scenario catalog
- `docs/nile-dataloader-plan.md`: dataset research and visual loading plan
- `docs/dataloader-node-generation-plan.md`: plan for generating `main/node.md` / `main/modules.md` simulator inputs from sourced data

## MVP Assumptions

- The execution time step is always daily
- Monthly support is handled through 30-day aggregation and optional monthly input series
- Drinking water and irrigation are treated as consumptive uses in v1
- Food production is currently linear by delivered irrigation water
- Hydropower is modeled as a non-consumptive linear conversion on controlled
  turbine release using each node's effective head and turbine efficiency
- Default sector allocation priority is drinking water first, then irrigation

Those choices keep the first implementation compact while leaving room for:

- richer hydropower plant curves and tailwater effects
- crop and region-specific agriculture modules
- explicit optimization layers on top of the simulator
- Python bindings and training workflows
- richer data loading and scenario assembly from Copernicus and supplemental datasets

## Run The Demo

```powershell
cargo run -p nrsm-cli -- scenarios/nile-mvp/scenario.yaml
```

Additional ready-to-run variants live under `scenarios/nile-mvp/past`,
`scenarios/nile-mvp/future`, and `scenarios/nile-mvp/few-nodes`. The dated
variants use `settings.start_date`, `settings.end_date`, and `horizon_days`;
the simulator currently executes by day count while retaining the calendar
window as scenario metadata.

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
| `food_water_demand` | Agricultural water demand over the period. |
| `food_water_met` / `unmet_food_water` | Agricultural water demand served and shortfall. |
| `food_produced` | Food units produced by the node. In the canonical hydmod assembly this is water-equivalent because `water_coefficient` is `1.0`. |
| `production_release` | Controlled hydropower/production release volume. |
| `generated_electricity_kwh` / `generated_electricity_mwh` | Electricity generated from `production_release`, `energy.effective_head_m`, and `energy.turbine_efficiency`. |
| `water_value_eur_per_m3` | Marginal hydropower value of one m3 at this node, using the node's effective head and electricity price. |
| `spill` | Uncontrolled reservoir overflow volume. |
| `release_for_routing` | `production_release + spill`, before edge fractions are applied. |
| `downstream_release` | Routed volume sent to downstream nodes after connection fractions. |
| `routing_loss` | `release_for_routing - downstream_release`, useful for plotting reach losses. |
| `energy_value` | Hydropower value for the period in EUR. |

`summary.csv` uses the same period columns and aggregates the water, food, and
energy fields across all nodes, including total generated electricity. Calendar
dates are not emitted yet; consumers should treat `start_day` and
`end_day_exclusive` as offsets from the scenario start date used by the data
assembler.

## Hydropower And Water Value

Hydropower is computed after the node has already served evaporation, drinking
water, and food-water demand for the day. The action for the node controls the
maximum turbine release:

```text
production_release_m3 = min(available_water_m3, max_production_m3_day * action)
```

Only `production_release` generates electricity. `spill` is routed downstream
but is not treated as useful turbine flow in the MVP.

The simulator uses the standard potential-energy approximation for hydropower:

```text
joules = production_release_m3
       * 1000 kg/m3
       * 9.80665 m/s2
       * effective_head_m
       * turbine_efficiency

generated_electricity_kwh = joules / 3,600,000
generated_electricity_mwh = generated_electricity_kwh / 1,000
```

Equivalently, the per-volume conversion is:

```text
kwh_per_m3 = 1000 * 9.80665 * effective_head_m * turbine_efficiency / 3,600,000
generated_electricity_kwh = production_release_m3 * kwh_per_m3
```

`effective_head_m` lives on the node's energy module. The canonical assembler
copies it from `horizon/data/topology/nodes.csv`. `turbine_efficiency` defaults
to `0.9` when the scenario does not specify another value.

Economic value is then attributed to the water at the current node:

```text
water_value_eur_per_m3 = kwh_per_m3 * price_eur_kwh
energy_value = generated_electricity_kwh * price_eur_kwh
```

For canonical hydmod runs, `price_eur_kwh` is a node-level constant generated by
the dataloader. It reads `horizon/data/electricity_price/<node_id>.csv`, sorts
the records by date, and uses the mean of the latest 365 daily price records.
That means all days in an assembled simulator run use the same trailing-year
mean price for that region. This is deliberate for the MVP: it gives optimizers
a stable marginal water value per node without needing to model power-market
seasonality yet.

Current limitations:

- Reservoir head is fixed per node; it does not vary with storage elevation.
- There is no turbine capacity curve, minimum operating flow, outage schedule,
  or tailwater effect.
- Spill has no energy value, even if a real plant could route some spill through
  turbines.
- Electricity price is a regional mean, not an hourly or daily market dispatch
  model.

## Plot Simulator Outputs

`plotting/` contains a small uv-managed Python project that turns `--results-dir`
CSV output into validation and debugging figures:

```powershell
cd plotting
uv run nrsm-plots --results-dir ..\data\results\nile-mvp --output-dir ..\data\results\nile-mvp\plots
```

It writes network water-balance, reliability, energy, per-node comparison,
shortage heatmap, and per-node diagnostic plots, plus `node_metrics.csv` and a
machine-readable `plot_manifest.json`. The plotter reads CSV output directly so
it works with archived simulator runs and external visualization tools.

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

## Initial Levels

By default, each node starts from `reservoir.initial_level` in the scenario YAML.
To sweep starting storage without rewriting the generated scenario, pass a small
override YAML:

```yaml
initial_levels:
  gerd: 37000000000
  aswan: 81000000000
```

```powershell
cargo run -p nrsm-cli -- data\generated\config.yaml --json --initial-levels data\policy-a\initial-levels.yaml
```

Any node omitted from the override file keeps the scenario value. Unknown node
ids fail fast so policy runs do not silently misspell a reservoir.

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

sim = nrsm_py.PreparedScenario.from_period(
    "scenarios/nile-mvp/past/1963-september-30d.yaml"
)
actions = [1.0] * sim.expected_action_len()
summary = json.loads(sim.run_actions_summary_json(actions))
```

`from_period` is the default Python path for real-data runs: it reads only the
period dates from the YAML, assembles node inputs from `horizon/data`, and then
loads the generated CSV-backed config. `from_yaml("data/generated/.../config.yaml")`
loads an already assembled CSV-backed config. `from_yaml("scenarios/...yaml")`
runs that hand-written demo scenario as written. Build the Python extension with
maturin from `horizon/nrsm/crates/nrsm-py`.

## Assemble Canonical Data

```powershell
cd horizon\nrsm
cargo run -p nrsm-dataloader -- assemble --input ..\data --output data\generated --start-date 2005-01-01 --end-date 2005-01-31
cargo run -p nrsm-cli -- data\generated\config.yaml --json --pretty
```

You can also use an existing scenario YAML as a period spec while ignoring its
hand-written node data. The assembler reads `settings.start_date` and
`settings.end_date`, then loads all node inputs from `horizon/data`:

```powershell
cargo run -p nrsm-dataloader -- assemble --period scenarios\nile-mvp\past\1963-september-30d.yaml --input ..\data
cargo run -p nrsm-cli -- data\generated\1963-september-30d\config.yaml --json --pretty
```

The `assemble` command reads the checked-in canonical data bundle under
`horizon/data` and writes simulator-ready files. The current MVP topology uses
the 13 hydmod catchment nodes in `horizon/data/topology/nodes.csv`; catchment
inflow comes from `horizon/data/hydmod/daily`. Evaporation prefers the direct
per-node series in `horizon/data/evaporation/direct/<node_id>.csv` with column
`evaporation_m3_day`. If that file or a requested date is missing, the assembler
falls back to the older temperature regression using `temp_c` from
`horizon/data/climate/era5_daily` and each node's configured lake area when that
fallback date exists. The fallback formula is
`evap_mm_day = max(0, 0.2301 * temp_c - 3.0550)`, then `m3/day` is
`evap_mm_day * surface_area_km2_at_full * 1000`. ERA5 evaporation/PET fields are
still not used by the fallback. Food and energy modules come from the
agriculture and electricity-price folders. The assembler reads
`effective_head_m` from `topology/nodes.csv`, writes it into each node's energy
module, and uses the mean of the latest 365 daily records in
`horizon/data/electricity_price/<node_id>.csv` as the node electricity price for
hydropower valuation.
Agriculture files supply either `water_m3_day` or `water_m3_s`; when the source
uses `water_m3_s`, the assembler converts it with `water_m3_day = water_m3_s *
86400`. It writes the result as the food-production module with
`water_coefficient: 1.0`, so outputs expose the agricultural water balance
directly through `food_water_demand`, `food_water_met`, and `unmet_food_water`.
The assembled real-data path requires source data for the requested dates,
except for electricity price, which is currently collapsed to the latest
365-record mean. Future windows will need an explicit extrapolation policy
before they can assemble from historical CSVs.

The older deterministic seed path is still available for tests and demos:

```powershell
cargo run -p nrsm-dataloader -- seed --output data/generated --start-date 2020-01-01 --end-date 2020-01-31 --scenarios 3
```
