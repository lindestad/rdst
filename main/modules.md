# Module

Each module provides a time-varying input to a node. Modules run as separate
programs and write their results to a CSV file, which the simulator reads at
load time. Because a single run can produce multiple plausible futures, each
CSV holds all scenarios side by side — one column per scenario.

## Input

A module is invoked with three arguments:

| Argument | Description |
|---|---|
| `start_date` | First day of the simulation (ISO 8601, e.g. `2020-01-01`) |
| `end_date` | Last day of the simulation (inclusive) |
| `n_scenarios` | Number of scenario columns to generate |

## Output

The module writes a CSV file with daily rows covering `[start_date, end_date]`.

| Column | Description |
|---|---|
| `date` | Calendar date (`YYYY-MM-DD`), one row per day |
| `scenario_1` … `scenario_N` | One column per scenario; units depend on the module type (see table below) |

The simulator selects which scenario column to use via the `column` field in
the node's YAML configuration.

### Module types and units

| Module | CSV value unit |
|---|---|
| Catchment inflow | m³/day |
| Evaporation | m³/day |
| Drinking-water demand | m³/day |
| Food production capacity | food units/day; with `water_coefficient: 1.0`, this is water-equivalent m³/day |
| Energy price | currency/m³ |

### Example CSV — catchment inflow, 3 scenarios

```
date,scenario_1,scenario_2,scenario_3
2020-01-01,142.3,198.7,105.1
2020-01-02,137.8,210.4,98.6
2020-01-03,155.0,224.1,112.3
2020-01-04,163.4,218.9,120.8
2020-01-05,149.7,205.3,109.4
```

Each value is the average inflow rate for that day in m³/day. The node YAML
references this file and picks one scenario column:

```yaml
catchment_inflow:
  type: csv
  filepath: data/upper_inflow.csv
```
