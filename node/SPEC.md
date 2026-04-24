# Water Resource Simulator — Project Specification

This document fully specifies the simulator so that it can be reproduced from scratch.

---

## 1. Purpose

The simulator models a network of water catchments for the joint optimization of:

- **Hydropower production** (water released through turbines)
- **Drinking water supply** (withdrawal from reservoirs)
- **Food production** (crop/irrigation water use)

The network is defined in a YAML file.  A `Simulator` object reads that file, builds the node graph, and exposes a single `step()` method: given actions for all nodes at one point in time, it advances the simulation by one timestep and returns the resulting state.

---

## 2. Project Structure

```
project/
├── config.yaml            # Network definition (edit this to configure your system)
├── modules/
│   ├── __init__.py        # Re-exports all module classes
│   ├── catchment_inflow.py
│   ├── drink_water.py
│   ├── food_production.py
│   └── energy_price.py
├── node.py                # Node and NodeConnection dataclasses
├── loader.py              # Parses YAML → returns Simulator
└── simulator.py           # Simulator class with step()
```

**Dependencies:** Python ≥ 3.10, `pyyaml`.

---

## 3. Core Concepts

### 3.1 Timestep

All simulation time is discrete.  One **timestep** has a duration of `dt_days` days (default `1.0`).  All rate values in the YAML (inflow, demand, max production) are expressed **per day**; the simulator multiplies them by `dt_days` to get the actual volume per timestep.

`dt_days` is set in the YAML (`settings.timestep_days`) and can also be overridden per call in `Simulator.step()`.

### 3.2 Units

| Quantity | Unit |
|---|---|
| Water volumes | m³ |
| Water rates (inflow, demand, production) | m³/day |
| Food production | food units/day (user-defined scale) |
| Energy value | currency (user-defined) |
| Time | days |

---

## 4. The Node

A **node** is the fundamental building block.  It represents one catchment area with a single reservoir.  Each node:

- Receives **natural inflow** from its local catchment (via the `CatchmentInflow` module)
- May receive **routed inflow** from one or more upstream nodes (with a travel-time delay)
- Releases a controllable fraction of water for **hydropower production**
- Satisfies **drinking-water demand** and **food-production water demand** from its reservoir
- Stores remaining water in its reservoir (capped at `max_capacity`; excess is spill)
- Routes its production release to zero or more downstream nodes

### 4.1 Node Settings (YAML fields)

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique node identifier |
| `catchment_inflow` | module | Natural daily inflow — see §5.1 |
| `reservoir.initial_level` | float (m³) | Starting reservoir volume |
| `reservoir.max_capacity` | float (m³) | Maximum reservoir volume |
| `max_production` | float (m³/day) | Maximum water release rate for hydropower |
| `connections` | list | Downstream edges — see §4.2 |
| `modules.drink_water` | module | Drinking-water demand — see §5.2 |
| `modules.food_production` | module | Food-production module — see §5.3 |
| `modules.energy` | module | Energy price module — see §5.4 |

### 4.2 Connections

Each connection is a directed edge to a downstream node:

| Field | Type | Description |
|---|---|---|
| `node_id` | string | ID of the downstream node |
| `fraction` | float [0–1] | Share of the production release routed to that node |
| `delay` | int (timesteps) | Travel time before water arrives (0 = same timestep) |

The fractions across all connections from one node must sum to ≤ 1.  Any remainder (1 − sum) is considered lost (evaporation, unmeasured discharge, etc.).

### 4.3 Per-Timestep Water Balance

The node evaluates the following steps **in priority order**:

1. **Inflow accumulation**  
   `total_inflow = catchment_inflow.inflow(t, dt) + external_inflow`  
   `available = reservoir_level + total_inflow`

2. **Hydropower production release** *(highest priority)*  
   `desired = action × max_production × dt`  
   `production_release = min(desired, available)`  
   `available -= production_release`

3. **Drinking-water withdrawal**  
   `dw_demand = drink_water.demand(t, dt)`  
   `drink_water_met = min(dw_demand, available)`  
   `available -= drink_water_met`

4. **Food-production water allocation**  
   `fp = food_production.produce(available, dt)`  
   `available -= fp["water_consumed"]`

5. **Reservoir update**  
   `new_level = available` (what is left after all withdrawals)  
   `spill = max(0, new_level − max_capacity)`  
   `reservoir_level = clamp(new_level, 0, max_capacity)`

6. **Downstream routing**  
   Both the controlled production release **and** any spill travel downstream through the same channels.  Spill carries no energy value.  
   For each connection: `routed = (production_release + spill) × fraction`  
   If `delay == 0`: added to downstream node's inflow this step.  
   If `delay > 0`: placed in a FIFO buffer; arrives at the downstream node after `delay` steps.

### 4.4 Node Step Result (`NodeStepResult`)

The `step()` method returns a dataclass with:

| Field | Description |
|---|---|
| `reservoir_level` | Reservoir volume at end of timestep (m³) |
| `production_release` | Water released for hydropower (m³) |
| `energy_value` | `production_release × energy_price` (currency) |
| `food_produced` | Food units produced |
| `drink_water_met` | Actual drinking-water withdrawn (m³); may be < demand if reservoir ran dry |
| `unmet_drink_water` | Unmet demand (m³) = `demand − drink_water_met` |
| `spill` | Water that overflowed the reservoir (m³) |
| `downstream_release` | Total water dispatched to downstream nodes (m³); includes both production release and spill |
| `total_inflow` | Total water received this timestep (catchment + upstream) (m³) |

---

## 5. Modules

Each module lives in its own file under `modules/`.  Modules are **stateless** (except for holding their parameters); all time-varying behaviour is expressed through the `timestep` and `dt_days` arguments.  New implementations can be added by subclassing.

### 5.1 `CatchmentInflow` (`modules/catchment_inflow.py`)

Provides natural inflow into the reservoir.

**Interface:**
```python
def inflow(self, timestep: int, dt_days: float) -> float
# Returns: volume in m³ for this timestep
```

**Implementations:**

| Class | YAML `type` | Parameters | Behaviour |
|---|---|---|---|
| `ConstantInflow` | `constant` | `rate` (m³/day) | Returns `rate × dt_days` every step |
| `TimeSeriesInflow` | `timeseries` | `values` (list of m³/day) | Returns `values[t % len(values)] × dt_days`; wraps around automatically |
| `CSVInflow` | `csv` | `filepath`, `column` | Reads rates from a named column in a CSV file; wraps around automatically |

**YAML example:**
```yaml
catchment_inflow:
  type: timeseries
  values: [180, 200, 220, 210, 190, 160, 150]   # m3/day, one per timestep

# or load from a CSV file:
catchment_inflow:
  type: csv
  filepath: data/inflow_reservoir_a.csv   # path relative to working directory
  column: inflow_m3_per_day              # header name of the column to use
```

The CSV must have a header row; all other columns are ignored.  Example:
```
date,inflow_m3_per_day,temperature
2024-01-01,175.3,4.1
2024-01-02,198.7,3.8
...
```

---

### 5.2 `DrinkWaterDemand` (`modules/drink_water.py`)

Daily drinking-water demand.  Supports constant, timeseries, and CSV variants.

**Interface:** `demand(timestep, dt_days) -> float` — returns m³ to withdraw.

| Class | YAML `type` | Parameters | Behaviour |
|---|---|---|---|
| `DrinkWaterDemand` | `constant` (default) | `daily_demand` (m³/day) | Returns `daily_demand × dt_days` |
| `TimeSeriesDrinkWater` | `timeseries` | `values` (list of m³/day) | Wraps around list |
| `CSVDrinkWater` | `csv` | `filepath`, `column` | Reads from CSV column |

**YAML:**
```yaml
modules:
  drink_water:
    daily_demand: 30.0        # constant (type field optional)

  # or timeseries:
  drink_water:
    type: timeseries
    values: [25, 28, 30, 32, 30, 27, 24]   # m3/day

  # or CSV:
  drink_water:
    type: csv
    filepath: data/demand.csv
    column: drink_water_m3_per_day
```

---

### 5.3 `FoodProduction` (`modules/food_production.py`)

Food output is a function of water available and daily production capacity.  Supports constant, timeseries, and CSV capacity variants.

**Logic:**
```
food_produced  = min(water_available / water_coefficient, max_food_units × dt_days)
water_consumed = food_produced × water_coefficient
```

| Class | YAML `type` | Parameters | Behaviour |
|---|---|---|---|
| `FoodProduction` | `constant` (default) | `water_coefficient`, `max_food_units` | Fixed daily capacity |
| `TimeSeriesFoodProduction` | `timeseries` | `water_coefficient`, `values` | Capacity varies per timestep |
| `CSVFoodProduction` | `csv` | `water_coefficient`, `filepath`, `column` | Capacity from CSV column |

**YAML:**
```yaml
modules:
  food_production:
    water_coefficient: 0.8   # m3 per food unit
    max_food_units: 50.0     # food units/day  (constant)

  # or timeseries capacity:
  food_production:
    type: timeseries
    water_coefficient: 0.8
    values: [40, 45, 50, 50, 45, 40, 35]   # food units/day

  # or CSV capacity:
  food_production:
    type: csv
    water_coefficient: 0.8
    filepath: data/capacity.csv
    column: max_food_units_per_day
```

---

### 5.4 `EnergyPrice` (`modules/energy_price.py`)

Price per m³ of water released for hydropower.  Supports constant, timeseries, and CSV variants (e.g. for spot-price electricity markets).

**Interface:** `price(timestep) -> float` — returns currency/m³.

| Class | YAML `type` | Parameters | Behaviour |
|---|---|---|---|
| `EnergyPrice` | `constant` (default) | `price_per_unit` | Fixed price every step |
| `TimeSeriesEnergyPrice` | `timeseries` | `values` (list of currency/m³) | Wraps around list |
| `CSVEnergyPrice` | `csv` | `filepath`, `column` | Reads from CSV column |

**YAML:**
```yaml
modules:
  energy:
    price_per_unit: 0.12      # constant

  # or timeseries:
  energy:
    type: timeseries
    values: [0.10, 0.11, 0.15, 0.18, 0.14, 0.10, 0.09]

  # or CSV:
  energy:
    type: csv
    filepath: data/spot_prices.csv
    column: price_eur_per_m3
```

---

## 6. The Simulator (`simulator.py`)

### 6.1 Construction

`Simulator` is not instantiated directly; use `load_simulator()` (see §7).

Fields:

| Field | Description |
|---|---|
| `nodes` | `dict[str, Node]` — all nodes keyed by ID |
| `dt_days` | Default timestep length in days (from YAML `settings.timestep_days`) |

Internal state:
- `_topo_order` — node IDs sorted topologically (upstream-first) via Kahn's algorithm
- `_buffers` — `dict[(source_id, target_id), deque[float]]` holding in-transit water for each delayed connection

### 6.2 `reset()` Method

```python
def reset() -> None
```

Restores every node's reservoir level to its original `initial_level` and clears all in-transit water from delay buffers.  Use this to re-run scenarios from scratch without reloading the YAML.

### 6.3 `step()` Method

```python
def step(
    actions: dict[str, float],    # node_id → production fraction [0, 1]
    timestep: int = 0,            # current timestep index
    dt_days: float | None = None, # override default dt; None uses self.dt_days
    debug: bool = False,          # enable per-node water balance check
) -> dict[str, NodeStepResult]
```

Unknown node IDs in `actions` are logged as warnings and ignored.  If `debug=True`, each node checks its water balance and logs a warning if it does not close to within 1e-6 m³.

**Algorithm:**
1. Resolve `dt` (use `dt_days` override or `self.dt_days`).
2. Warn about unrecognised keys in `actions`.
3. Initialise `pending_inflow[node_id] = 0` for all nodes.
4. Iterate nodes in topological order (upstream first):
   a. Call `node.step(action, external_inflow=pending_inflow[node_id], timestep, dt, debug)`.
   b. For each downstream connection:
      - If `delay == 0`: add `(production_release + spill) × fraction` to `pending_inflow[downstream]`.
      - If `delay > 0`: pop the front of the connection's buffer (= water that arrives now), add to `pending_inflow[downstream]`; append new release to the back of the buffer.
5. Return `dict[node_id → NodeStepResult]`.

### 6.4 `run()` Method

```python
def run(
    actions_sequence: list[dict[str, float]],  # one actions dict per timestep
    start_timestep: int = 0,
    dt_days: float | None = None,
    debug: bool = False,
) -> list[dict[str, NodeStepResult]]
```

Runs `step()` for every entry in `actions_sequence` and returns the full history as a list.

### 6.5 Topological Sort & Cycles

Nodes are sorted with **Kahn's BFS algorithm**.  A `ValueError` is raised if the graph contains a cycle.  Connections with `delay > 0` do not create same-timestep dependencies (their water arrives in a future step), but they still participate in the graph structure for sorting purposes.

---

## 7. The Loader (`loader.py`)

```python
from loader import load_simulator
sim = load_simulator("config.yaml")
```

`load_simulator(yaml_path)`:
1. Reads and parses the YAML file.
2. Extracts `settings.timestep_days` (default `1.0`).
3. For each node entry: instantiates the `CatchmentInflow` module, `DrinkWaterDemand`, `FoodProduction`, `EnergyPrice`, and all `NodeConnection` objects.
4. Validates that connection fractions sum to ≤ 1 and that all referenced node IDs exist.
5. Returns `Simulator(nodes=..., dt_days=...)`.

---

## 8. Full YAML Schema

```yaml
settings:
  timestep_days: 1.0          # float, optional, default 1.0

nodes:
  - id: <string>              # unique node identifier

    catchment_inflow:
      type: constant          # "constant", "timeseries", or "csv"
      rate: <float>           # m3/day  (constant only)
      values: [<float>, ...]  # m3/day per timestep (timeseries only); wraps around
      filepath: <string>      # path to CSV file (csv only)
      column: <string>        # CSV column name containing m3/day rates (csv only)

    reservoir:
      initial_level: <float>  # m3, starting volume
      max_capacity: <float>   # m3, maximum capacity

    max_production: <float>   # m3/day, maximum hydropower release rate

    connections:              # list; omit or use [] for outlet nodes
      - node_id: <string>     # downstream node ID
        fraction: <float>     # share of production release routed here [0–1]
        delay: <int>          # travel-time in timesteps, default 0

    modules:
      drink_water:
        daily_demand: <float>       # m3/day

      food_production:
        water_coefficient: <float>  # m3 per food unit
        max_food_units: <float>     # food units/day

      energy:
        price_per_unit: <float>     # currency per m3 of production release
```

---

## 9. Usage Example

```python
from loader import load_simulator

sim = load_simulator("config.yaml")

# --- Single step ---
actions = {"reservoir_a": 0.7, "reservoir_b": 0.5, "reservoir_c": 0.6}
state = sim.step(actions, timestep=0)
for node_id, result in state.items():
    print(f"{node_id}: level={result.reservoir_level:.1f}  unmet_demand={result.unmet_drink_water:.1f}")

# --- Full run over a sequence ---
actions_seq = [actions] * 30
history = sim.run(actions_seq)  # list of 30 state dicts

# --- Reset and re-run (e.g. for optimisation) ---
sim.reset()
history2 = sim.run(actions_seq)

# --- Enable water balance debug checks ---
sim.reset()
history3 = sim.run(actions_seq, debug=True)

# --- Change timestep length ---
sim.dt_days = 0.5              # 12-hour steps globally
sim.reset()
state_half = sim.step(actions, timestep=0)

# --- Per-step override ---
state_2day = sim.step(actions, timestep=0, dt_days=2.0)
```

---

## 10. Extension Points

| What to extend | How |
|---|---|
| Time-varying inflow | Subclass `CatchmentInflow`, implement `inflow(t, dt)` |
| Time-varying demand | Subclass `DrinkWaterDemand`, implement `demand(t, dt)` |
| Time-varying energy price | Subclass `EnergyPrice`, implement `price(t)` |
| New module type on a node | Add field to `Node`, wire it in `node.step()` and `loader.py` |
| Different routing logic | Subclass or modify `Simulator.step()` |
| Stochastic inflow | Override `CatchmentInflow.inflow()` to draw from a distribution |
