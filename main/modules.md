# Module

Each module provides a time-varying input to a node. Modules run as separate
programs and write their results to a CSV file, which the simulator reads at
load time. Because a single run can produce multiple plausible futures, each
CSV holds all scenarios side by side — one column per scenario.

## Contract Status

This is the simulator-ready module contract. Data gathering pipelines may keep
their own inspection CSVs, raw files, staging tables, or notebook-friendly
formats, but the handoff into NRSM should end with the CSV shape below.

The current Rust simulator reads one selected scenario column from each module
CSV. It does not currently use the `date` column for slicing; rows are consumed
in file order and the run length is inferred from the shortest loaded CSV unless
`settings.horizon_days` is set. Date-window validation is planned.

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

Each CSV should contain only simulator-ready numeric values. Provenance,
confidence, source URLs, and transform notes belong in adjacent staging files,
not in the module CSV consumed by the simulator.

The simulator selects which scenario column to use via the `column` field in
the node's YAML configuration.

Planned CLI support should allow one global scenario override such as
`--scenario scenario_2`, applying the selected column to every CSV-backed module
unless the config explicitly opts out.

### Module types and units

| Module | CSV value unit |
|---|---|
| Catchment inflow | m³/day |
| Evaporation | m³/day |
| Drinking-water demand | m³/day |
| Food production capacity | food units/day |
| Energy price | currency/m³ |

### Data Gatherer Mapping

The data gatherer should convert source-specific units before writing module
CSVs:

| Source output | Module target | Conversion |
|---|---|---|
| GloFAS discharge | Catchment inflow | `m³/s × 86400 = m³/day` |
| ERA5 runoff depth | Catchment inflow fallback | `runoff_mm × area_km2 × 1000 = m³/day` |
| ERA5/ERA5-Land PET or ET | Evaporation | `depth_mm × surface_area_km2 × 1000 = m³/day` |
| Population demand | Drinking-water demand | `population × liters/person/day / 1000 = m³/day` |
| Irrigated area and crop proxy | Food production capacity | data-derived `food units/day` |
| Hydropower valuation | Energy price | scenario-specific `currency/m³` |

If richer source columns are useful for analysis, write them under a data bundle
such as `data/csv/` or `data/staging/`, then have an assembler emit the simple
module CSVs used by NRSM.

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
