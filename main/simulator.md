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
   CSV must contain a `date` column covering at least `[start_date, end_date]`
   and a column matching the requested `scenario`. Constant-valued modules
   require no file.

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

In the YAML contract, each node supplies this matrix column as
`actions.production_level`. It accepts the same constant-or-CSV series shape as
modules:

```yaml
actions:
  production_level:
    type: csv
    filepath: modules/gerd.actions.csv
    column: scenario_1
```

The action CSV is daily and scenario-column based:

```csv
date,scenario_1,scenario_2
2005-01-01,1.0,0.75
2005-01-02,0.4,0.2
```

This action only controls the controlled hydropower/production release. It does
not directly reduce drinking-water withdrawal or food-production allocation,
which still run first in the node water balance.

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

---

## Results

The simulator writes one CSV file per node named `<node_id>.csv`. Each file
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
