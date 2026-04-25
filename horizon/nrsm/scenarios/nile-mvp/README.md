# Nile MVP Scenario Catalog

This folder contains runnable NRSM YAML scenarios for the Nile MVP topology.
`scenario.yaml` remains the small default demo. The `past/` and `future/`
folders contain dated variants with all 13 Nile MVP nodes. The `few-nodes/`
folder contains one deliberately small Blue Nile scenario for quick smoke tests.

The simulator currently executes by `settings.horizon_days`; `start_date` and
`end_date` are calendar labels for scenario selection, reporting, and future
calendar-aware outputs.

| File | Nodes | Window | Days | Shape |
| --- | ---: | --- | ---: | --- |
| `scenario.yaml` | 13 | 2020-01-01 to 2020-03-30 | 90 | default demo |
| `few-nodes/blue-nile-2030-30d.yaml` | 3 | 2030-02-01 to 2030-03-02 | 30 | quick Blue Nile smoke test |
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

Run any scenario from `horizon/nrsm`:

```powershell
cargo run -p nrsm-cli -- scenarios/nile-mvp/future/2030-full-year-growth.yaml --json --pretty
```
