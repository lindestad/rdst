# Simulator

The simulator orchestrates a network of [nodes](node.md) over a time horizon,
stepping forward one timestep at a time. Each node independently manages its
own water balance (inflow, evaporation, drinking water, food production,
hydropower release, and spill) and routes surplus water downstream through a
directed acyclic graph (DAG). External time-varying inputs — inflow, evaporation
rates, demand, food capacity, and energy prices — are supplied by
[modules](modules.md) that write their data to CSV files before the simulation
starts.

---

## Input

| Parameter | Required | Description |
|---|---|---|
| `start_date` | ✓ | First day of the simulation (ISO 8601, e.g. `2020-01-01`) |
| `end_date` | ✓ | Last day of the simulation (inclusive) |
| `config` | ✓ | Path to the `config.yaml` file describing nodes and connections |
| `timestep_days` | — | Simulation timestep in days (default `1.0`; overrides `settings.timestep_days` in the YAML) |
| `scenario` | — | Scenario column name to use from every module CSV (default `scenario_1`) |
| `initial_levels` | — | Per-node override of starting reservoir volume in m³; any node not listed uses the value from `config.yaml` |

Generated simulator inputs should live at:

```text
horizon/nrsm/data/generated/config.yaml
```

Hand-authored examples may live under `horizon/nrsm/scenarios/<name>/`. Relative
module file paths are resolved from the directory containing the selected config.

Current Rust CLI:

```powershell
cargo run -p nrsm-cli -- data\generated\config.yaml --json --pretty
```

Planned Rust CLI:

```powershell
nrsm-cli data\generated\config.yaml --start-date 2020-01-01 --end-date 2020-12-31 --scenario scenario_2 --actions actions.csv --output-dir runs\scenario_2
```

---

## Initialisation

Before the main loop runs, the simulator performs the following steps:

1. **Parse config** — load and validate `config.yaml`. Every `id` must be
   unique; connection `node_id` values must reference existing nodes; all
   connection fractions for a node must sum to ≤ 1.

2. **Build the DAG** — derive a topological ordering of nodes from the
   `connections` graph. This ordering is used in every timestep so that
   upstream nodes always step before their downstream neighbours.

3. **Load module data** — for each node, load every CSV-backed module. The
   CSV must contain a `date` column and a column matching the requested
   `scenario`. Target behavior is to validate coverage for
   `[start_date, end_date]`; current Rust behavior consumes rows in file order.
   Constant-valued modules require no file.

4. **Apply initial levels** — set each node's `reservoir_level` to
   `initial_levels[node_id]` if provided, otherwise to
   `reservoir.initial_level` from the YAML.

5. **Initialise delay buffers** — for each connection with `delay > 0`,
   create a FIFO buffer of the appropriate length pre-filled with `0.0`.

---

## Simulation Loop

The simulator iterates over each day `t` in `[start_date, end_date]`:

```
for t in timesteps:
    for node in topological_order:
        1. collect upstream water arriving this timestep (delay buffers)
        2. query each module for its value at t
        3. apply the action for this node at t
        4. run the node water balance (see node.md § Per-Timestep Water Balance)
        5. push routed water into downstream delay buffers
        6. record the step result
```

### Actions

Each timestep every node receives a **production level fraction** — a float in
`[0, 1]` that scales `max_production`. Actions are provided as an
`(T × N)` matrix (T timesteps, N nodes) indexed by `[t, node_id]`. Values
outside `[0, 1]` are clamped. If no action matrix is supplied (simulation-only
mode) all nodes default to `action = 1.0` (full production).

Current Rust support uses `settings.production_level_fraction` as one global
action value for every node and timestep. This is enough for a baseline run, but
scenario work such as GERD filling should move to action CSVs.

### Action CSV

Planned shape:

```csv
date,gerd,aswan,merowe
2020-01-01,0.65,1.00,1.00
2020-01-02,0.65,1.00,1.00
```

Missing node columns default to `1.0`. Values outside `[0, 1]` are clamped.

### Upstream inflow

Water dispatched from node `u` to node `v` with `delay = d` arrives exactly
`d` timesteps later. At `t = 0` the buffers are empty, so no delayed inflow
arrives in the first `d` steps.

---

## Scenarios

All CSV-backed modules for a run share the same `scenario` column selection.
To compare multiple scenarios, run the simulator once per scenario (or in
parallel). Each run produces an independent set of output CSVs.

---

## Optimisation

In optimisation mode the simulator is called repeatedly by an outer optimiser
that searches for the action matrix (one production-level fraction per node per
timestep) that maximises a configurable objective — typically total `energy_value`
over the horizon minus penalties for unmet drinking-water demand and unmet
minimum food production. The simulator itself is stateless between calls; the
optimiser is responsible for managing the search.

Optimization is out of scope for the simulator binary itself. The simulator
should expose stable inputs and deterministic outputs so an optimizer can call
it repeatedly.

---

## Results

Target behavior: the simulator writes one CSV file per node named `<node_id>.csv`. Each file
contains one row per timestep:

| Column | Unit | Description |
|---|---|---|
| `date` | — | Calendar date (`YYYY-MM-DD`) |
| `reservoir_level` | m³ | Reservoir volume at the end of the timestep |
| `total_inflow` | m³ | Water received this timestep (catchment + upstream) |
| `evaporation` | m³ | Water lost to evaporation |
| `drink_water_met` | m³ | Drinking water actually supplied |
| `unmet_drink_water` | m³ | Unmet drinking-water demand |
| `food_produced` | food units | Food units produced |
| `production_release` | m³ | Water released for hydropower |
| `energy_value` | currency | `production_release × energy_price` |
| `spill` | m³ | Water that overflowed the reservoir |
| `downstream_release` | m³ | Total water routed downstream |
| `action` | — | Production level fraction applied this timestep |

Current Rust behavior: results are returned as structured JSON or YAML with
periods and node results. CSV result writing is the next compatibility step for
the markdown contract.

### Aggregated summary

In addition to the per-node CSVs, the simulator writes a `summary.csv` with
one row per timestep containing the network-wide totals:

| Column | Description |
|---|---|
| `date` | Calendar date |
| `total_energy_value` | Sum of `energy_value` across all nodes |
| `total_drink_water_met` | Sum of `drink_water_met` across all nodes |
| `total_unmet_drink_water` | Sum of `unmet_drink_water` across all nodes |
| `total_food_produced` | Sum of `food_produced` across all nodes |
| `total_spill` | Sum of `spill` across all nodes |
