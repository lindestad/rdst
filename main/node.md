# Node

A **node** represents a single catchment area with one reservoir. Nodes are the
fundamental building blocks of the simulation. They are defined in `config.yaml`
and wired together into a directed acyclic graph (DAG) via connections.

Each node independently manages its own water balance every timestep: it
receives inflow, releases water for hydropower, satisfies drinking-water and
food-production demands, stores whatever remains in the reservoir (up to the
reservoir's capacity), and routes excess water downstream.

---

## Properties

| Property | Unit | Description |
|---|---|---|
| `id` | — | Unique string identifier for the node |
| `reservoir.initial_level` | m³ | Starting reservoir volume |
| `reservoir.max_capacity` | m³ | Maximum reservoir volume; water above this level spills downstream |
| `max_production` | m³/day | Maximum water release rate available for hydropower |

---

## Modules

Each node has four pluggable modules that control time-varying behaviour.
In the yaml file, this can either be constant with a value, e.g. `contant: 20.0`,
or it can point to a csv file. The time series has daily resolution, and
one column for each scenario.

### Catchment Inflow

Natural water arriving from the local catchment into the reservoir, m^3/day.

### Evaporation

Water lost from the reservoir surface. Evaporation is deducted first, before
any other withdrawal or release.

```
evaporation = min(evaporation_rate(t, dt), available)
available  -= evaporation
```

### Drinking-Water Demand

Volume of water that must be withdrawn from the reservoir for human consumption.
The withdrawal is satisfied before food production and before hydropower release.

### Food Production

Converts available reservoir water into food units and reports the water
shortfall explicitly. Production is capped by both the water available after
drinking-water withdrawal and the module's maximum daily capacity.

```
food_water_demand = max_food_units × dt × water_coefficient
food_produced     = min(water_available / water_coefficient, max_food_units × dt)
food_water_met    = food_produced × water_coefficient
unmet_food_water  = food_water_demand − food_water_met
```

For the canonical hydmod MVP, the data gatherer supplies agricultural
`water_m3_day` values and sets `water_coefficient = 1.0`, so `food_produced` is
a water-equivalent compatibility value while `food_water_*` fields are the
primary agriculture accounting outputs.
### Energy Price

Price received per m³ of water released for hydropower. Multiplied by
`production_release` to give the monetary energy value each timestep.

---

## Connections

A node can route its water to zero or more downstream nodes via **connections**.
Each connection is a directed edge:

| Field | Type | Description |
|---|---|---|
| `node_id` | string | ID of the downstream node to receive water |
| `fraction` | float [0–1] | Share of `production_release + spill` routed to that node |
| `delay` | int (timesteps) | Travel time before water arrives; `0` means the same timestep |

The fractions across all outgoing connections must sum to ≤ 1. Any remainder
(1 − sum) is considered lost (evaporation, unmeasured discharge, etc.).

Both the **controlled production release** and any **uncontrolled spill** travel
through the same connections. Spill carries no energy value.

---

## Actions

Each timestep, the node receives exactly one action:

- **Production level fraction** — a float in `[0, 1]`. Values outside this range
  are clamped. The actual water released is `action × max_production × dt_days`,
  further capped by however much water is available in the reservoir.

---

## Per-Timestep Water Balance

Steps are executed in this fixed priority order:

1. **Inflow accumulation**  
   `available = reservoir_level + catchment_inflow(t, dt) + upstream_inflow`

2. **Evaporation**  
   `evaporation = min(evaporation_rate(t, dt), available)`  
   `available -= evaporation`

3. **Drinking-water withdrawal**  
   `drink_water_met = min(drink_water_demand(t, dt), available)`  
   `available -= drink_water_met`

4. **Food-production water allocation**  
   `food_water_demand = food_production.water_demand(t, dt)`  
   `food_produced, food_water_met = food_production.produce(available, dt)`  
   `unmet_food_water = food_water_demand − food_water_met`  
   `available -= food_water_met`

5. **Hydropower production release**  
   `production_release = min(action × max_production × dt, available)`  
   `available -= production_release`

6. **Reservoir update and spill**  
   `spill = max(0, available − max_capacity)`  
   `reservoir_level = clamp(available, 0, max_capacity)`

7. **Downstream routing**  
   For each connection:  
   `routed = (production_release + spill) × fraction`  
   — arrives at the downstream node immediately if `delay == 0`, otherwise
   placed in a FIFO buffer and delivered after `delay` timesteps.

---

## Step Result

After each timestep the node returns the following values:

| Field | Unit | Description |
|---|---|---|
| `action` | — | Production level fraction applied this timestep |
| `reservoir_level` | m³ | Reservoir volume at end of timestep |
| `production_release` | m³ | Water released for hydropower |
| `energy_value` | currency | `production_release × energy_price` |
| `food_water_demand` | m³ | Agricultural water demand this timestep |
| `food_water_met` | m³ | Agricultural water actually withdrawn this timestep |
| `unmet_food_water` | m³ | Agricultural water shortfall = `food_water_demand − food_water_met` |
| `evaporation` | m³ | Water lost to evaporation this timestep |
| `food_produced` | food units | Food units produced this timestep |
| `drink_water_met` | m³ | Actual drinking-water withdrawn (may be < demand) |
| `unmet_drink_water` | m³ | Unmet drinking-water demand = `demand − drink_water_met` |
| `spill` | m³ | Water that overflowed the reservoir |
| `downstream_release` | m³ | Total water dispatched downstream (`production_release + spill`, weighted by connection fractions) |
| `total_inflow` | m³ | Total water received this timestep (catchment + upstream) |

---

## Units

| Quantity | Unit |
|---|---|
| Water volumes / reservoir levels | m³ |
| Water rates (inflow, demand, max production) | m³/day |
| Food production capacity | food units/day |
| Energy value | currency (user-defined scale) |
| Energy price | currency / m³ |
| Time | days |

---

## YAML Configuration Format

A simulation is fully described by a single `config.yaml` file. It has two
top-level keys: `settings` (optional global parameters) and `nodes` (the list
of catchment nodes). Each module value is either **constant** — a fixed scalar
— or **csv** — a path to a CSV file whose rows correspond to timesteps and
whose columns represent scenarios.

### Schema

```yaml
settings:
  timestep_days: 1.0          # optional, default 1.0

nodes:
  - id: <string>              # unique identifier

    reservoir:
      initial_level: <float>  # m³ — starting volume
      max_capacity:  <float>  # m³ — water above this spills downstream

    max_production: <float>   # m³/day — maximum hydropower release rate

    catchment_inflow:
      type: constant          # — or — csv
      rate: <float>           # constant: m³/day
      filepath: <path>        # csv: path to file

    connections:              # list of downstream edges; may be empty
      - node_id:  <string>    # ID of the downstream node
        fraction: <float>     # share of (production_release + spill) routed there; 0–1
        delay:    <int>       # travel time in timesteps (default 0)
                              # fractions across all connections must sum to ≤ 1

    modules:
      evaporation:
        rate: <float>               # m³/day (constant)
        # or: type: csv, filepath: <path>

      drink_water:
        daily_demand: <float>       # m³/day (constant)
        # or: type: csv, filepath: <path>

      food_production:
        water_coefficient: <float>  # m³ consumed per food unit produced
        max_food_units: <float>     # food units/day (constant)
        # or: type: csv, filepath: <path>  (CSV supplies max_food_units per timestep)

      energy:
        price_per_unit: <float>     # currency/m³ (constant)
        # or: type: csv, filepath: <path>

    actions:
      production_level:
        value: <float>              # constant fraction in [0, 1]
        # or: type: csv, filepath: <path>, column: <scenario_N>
```

### Example — two-node cascade

Headwater node `upper` feeds all of its release into `lower` with a one-day
delay. `upper` uses CSV-driven inflow (e.g. a seasonal scenario); `lower` has
a small constant baseflow.

```yaml
settings:
  timestep_days: 1.0

nodes:
  - id: upper
    reservoir:
      initial_level: 1200.0
      max_capacity:  3000.0
    max_production: 200.0
    catchment_inflow:
      type: csv
      filepath: data/upper_inflow.csv
    connections:
      - node_id: lower
        fraction: 1.0
        delay: 1
    modules:
      drink_water:
        daily_demand: 40.0
      food_production:
        water_coefficient: 0.9
        max_food_units: 60.0
      energy:
        price_per_unit: 0.15

  - id: lower
    reservoir:
      initial_level: 500.0
      max_capacity:  1500.0
    max_production: 120.0
    catchment_inflow:
      type: constant
      rate: 60.0
    connections: []
    modules:
      drink_water:
        daily_demand: 20.0
      food_production:
        water_coefficient: 0.7
        max_food_units: 35.0
      energy:
        price_per_unit: 0.11
```

---
