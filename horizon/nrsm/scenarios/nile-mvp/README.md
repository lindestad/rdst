# Nile MVP Scenario Catalog

This folder contains period specs for the Nile MVP topology, plus simulator-ready
stress cases under `extremes/`. The period YAML files do not define node data,
topology, population, evaporation, inflow, agriculture, or energy prices. They
only select a date window, plus an optional node subset. The simulator-ready
files are generated from `horizon/data` by the dataloader.

The `extremes/` folder contains simulator-native stress cases used by the
visualizer preset buttons. The `few-nodes/` folder contains one deliberately
small Blue Nile period spec for quick smoke tests.

| File | Nodes | Window | Days | Shape |
| --- | ---: | --- | ---: | --- |
| `scenario.yaml` | 13 | 2020-01-01 to 2020-03-30 | 90 | default demo |
| `few-nodes/blue-nile-2030-30d.yaml` | 3 | 2030-02-01 to 2030-03-02 | 30 | quick Blue Nile smoke test |
| `past/1963-september-30d.yaml` | 13 | 1963-09-01 to 1963-09-30 | 30 | historic wet-season run |
| `past/2005-jan-7d-baseline.yaml` | 13 | 2005-01-01 to 2005-01-07 | 7 | short baseline |
| `past/2005-q1-90d-baseline.yaml` | 13 | 2005-01-01 to 2005-03-31 | 90 | quarterly baseline |
| `past/2010-dry-season-180d.yaml` | 13 | 2010-04-01 to 2010-09-27 | 180 | lower inflow, higher evaporation |
| `past/2012-wet-season-120d.yaml` | 13 | 2012-07-01 to 2012-10-28 | 120 | higher inflow |
| `past/2015-low-storage-30d.yaml` | 13 | 2015-02-01 to 2015-03-02 | 30 | lower starting storage |
| `past/2018-energy-prices-365d.yaml` | 13 | 2018-01-01 to 2018-12-31 | 365 | higher hydropower prices |
| `past/2020-full-year-balanced.yaml` | 13 | 2020-01-01 to 2020-12-30 | 365 | full-year balanced |
| `past/2024-hot-60d.yaml` | 13 | 2024-06-01 to 2024-07-30 | 60 | hot short run |
| `past/2026-spring-45d.yaml` | 13 | 2026-01-15 to 2026-02-28 | 45 | recent operations check |
| `future/2027-30d-operations-check.yaml` | 13 | 2027-01-01 to 2027-01-30 | 30 | near-term operations check |
| `future/2030-full-year-growth.yaml` | 13 | 2030-01-01 to 2030-12-31 | 365 | demand growth |
| `future/2030-flood-pulse-45d.yaml` | 13 | 2030-08-01 to 2030-09-14 | 45 | high inflow pulse |
| `future/2035-two-year-dry.yaml` | 13 | 2035-01-01 to 2036-12-30 | 730 | extended dry run |
| `future/2040-energy-transition-365d.yaml` | 13 | 2040-01-01 to 2040-12-30 | 365 | lower energy price |
| `future/2045-demand-growth-180d.yaml` | 13 | 2045-04-01 to 2045-09-27 | 180 | higher drinking and food demand |
| `future/2050-five-year-stress.yaml` | 13 | 2050-01-01 to 2054-12-31 | 1826 | long stress test |
| `future/2060-hot-low-inflow-90d.yaml` | 13 | 2060-06-01 to 2060-08-29 | 90 | hot and low inflow |
| `future/2075-short-emergency-14d.yaml` | 13 | 2075-07-01 to 2075-07-14 | 14 | emergency short run |
| `future/2100-long-range-365d.yaml` | 13 | 2100-01-01 to 2100-12-31 | 365 | long-range annual run |
| `extremes/upstream-holdback-90d.yaml` | 13 | 2030-01-01 to 2030-03-31 | 90 | GERD constrained release stress case |

Run a period from `horizon/nrsm` by assembling it from `horizon/data` first:

```powershell
cargo run -p nrsm-dataloader -- assemble --period scenarios\nile-mvp\past\1963-september-30d.yaml --input ..\data
cargo run -p nrsm-cli -- data\generated\1963-september-30d\config.yaml --json --pretty
```

## Run With Real Data

`--period` reads `settings.start_date`, `settings.end_date`, and optional
`settings.node_ids` from the YAML. All node values are read from the CSV-backed
data bundle under `horizon/data`.

```powershell
cargo run -p nrsm-dataloader -- assemble --period scenarios\nile-mvp\past\1963-september-30d.yaml --input ..\data
cargo run -p nrsm-cli -- data\generated\1963-september-30d\config.yaml --json --pretty
```

Without `--output`, the generated scenario is written to
`data/generated/<period-file-name>/`. Historical windows must be covered by the
source CSVs; future windows need extrapolated input data before this path can
assemble them.

## Create Your Own Scenario

Start by copying the closest existing YAML, then change the date window. Use
`past/` for historical windows, `future/` for planning windows, and
`few-nodes/` only for small smoke tests.

```powershell
Copy-Item scenarios\nile-mvp\past\2024-hot-60d.yaml scenarios\nile-mvp\future\2032-custom-90d.yaml
```

Each scenario needs:

- `settings.start_date`: first calendar day, written as `YYYY-MM-DD`.
- `settings.end_date`: last calendar day, written as `YYYY-MM-DD`.
- `settings.node_ids`, optionally: a list of topology node ids to assemble. Omit
  it to use all 13 Nile MVP nodes.

Minimal shape:

```yaml
settings:
  start_date: 2032-01-01
  end_date: 2032-01-30
```

Small subset shape:

```yaml
settings:
  start_date: 2032-01-01
  end_date: 2032-01-30
  node_ids:
    - tana
    - gerd
    - roseires
```

Run the period after editing:

```powershell
cargo run -p nrsm-dataloader -- assemble --period scenarios\nile-mvp\future\2032-custom-90d.yaml --input ..\data
cargo run -p nrsm-cli -- data\generated\2032-custom-90d\config.yaml --json --results-dir data\results\2032-custom-90d
```

Before committing a new catalog period, assemble at least one historical window
and preferably run the dataloader tests:

```powershell
cargo test -p nrsm-dataloader
```

Run simulator-native stress cases directly:

```powershell
cargo run -p nrsm-cli -- scenarios\nile-mvp\extremes\upstream-holdback-90d.yaml --json --results-dir data\results\extremes\upstream-holdback-90d
```

Refresh the packaged web visualizer catalog from `horizon/nrsm` after
assembling period specs:

```bash
for file in scenarios/nile-mvp/scenario.yaml scenarios/nile-mvp/past/*.yaml scenarios/nile-mvp/future/*.yaml scenarios/nile-mvp/few-nodes/*.yaml; do
  rel=${file#scenarios/nile-mvp/}
  id=${rel%.yaml}
  id=${id//\//__}
  out="data/generated/$id"
  cargo run -q -p nrsm-dataloader -- assemble --period "$file" --input ../data --output "$out"
  cargo run -q -p nrsm-cli -- "$out/config.yaml" --json --results-dir "../../nile-visualizer-app/src/data/results/scenarios/$id" > "/tmp/nrsm-${id//__/-}.json"
done

for file in scenarios/nile-mvp/extremes/*.yaml; do
  rel=${file#scenarios/nile-mvp/}
  id=${rel%.yaml}
  id=${id//\//__}
  cargo run -q -p nrsm-cli -- "$file" --json --results-dir "../../nile-visualizer-app/src/data/results/scenarios/$id" > "/tmp/nrsm-${id//__/-}.json"
done
```
