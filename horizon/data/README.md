# horizon/data

Consolidated datasets used across the horizon stack (nile-digital-twin, nrsm,
dataloader-viz). Files here are **copies** — the originals remain in place
because other code paths still load from them. Once those dependencies are
migrated, the originals can be removed and this becomes the single source.

## Layout

```
data/
├── topology/                 Network definition (nile-digital-twin model)
│   ├── catalog.csv
│   ├── nodes.csv
│   ├── edges.csv
│   ├── nodes.geojson
│   ├── node_config.yaml
│   └── node_config.calib.yaml
│
├── climate/
│   ├── era5_daily/           ERA5 daily, per digital-twin node
│   ├── era5_monthly/         ERA5 monthly, per digital-twin node
│   ├── era5_land_monthly/    ERA5-Land monthly, per digital-twin node
│   └── era5_legacy/          *_1950_2026.csv, older node naming
│                             (aswand, karthoum, kashm, ozentari, ...)
│
├── hydrology/
│   └── glofas/               GloFAS streamflow, per digital-twin node
│
├── hydmod/                   Canonical MVP hydrological model outputs
│   ├── catchments.csv        Hydmod catchment metadata and station centroids
│   ├── daily/                Normalized daily CSV per hydmod catchment node
│   └── raw/                  Original hydmod .txt files copied verbatim
│
├── evaporation/
│   └── direct/               Direct per-node daily evaporation, canonical MVP nodes
│
├── agriculture/
│   ├── water_usage/          nile_<node>_water.csv + nile_water_usage_all.csv
│   │                         (canonical MVP node naming)
│   ├── ndvi/                 NDVI timeseries CSVs (gezira, egypt_delta)
│   └── egypt_ndvi.tiff       NDVI raster
│
├── electricity_price/        Per-node daily electricity prices (`price_eur_kwh`)
│
└── examples/
    └── headwater_inflow.csv  Sample inflow used by main/example
```

## Node naming conventions

The canonical NRSM MVP now uses the **hydmod catchment nodes**:

`victoria`, `southwest`, `tana`, `gerd`, `roseires`, `singa`, `ozentari`,
`tsengh`, `kashm`, `karthoum`, `merowe`, `aswand`, `cairo`.

These nodes are defined in `topology/nodes.csv` and `topology/edges.csv`.
Their simulator catchment inflows come from `hydmod/daily/<node>.csv`.
Their simulator evaporation inputs prefer
`evaporation/direct/<node>.csv` when present. If a direct evaporation file or
date is missing, the NRSM assembler falls back to the older ERA5 daily
temperature regression over `surface_area_km2_at_full` when a fallback climate
date exists.
Their hydropower valuation uses `electricity_price/<node>.csv`; the NRSM
assembler takes the mean of the latest 365 daily price records for each node and
combines that with `topology/nodes.csv` `effective_head_m`.

For simulator evaporation, `evaporation/direct/<node>.csv` is expected to
contain:

```csv
date,evaporation_m3_day
2005-01-01,1000000.0
```

The current direct evaporation import is available for all canonical MVP nodes.
The original Cairo direct evaporation source contained no non-empty values, so
`main/modules/evaporation/evap_csv/cairo_1950_2026_direct.csv` has been filled
from the Aswand direct evaporation series as the MVP proxy. The direct files
cover `1950-01-01` through `2024-12-31`; the `2025-2026` blank tail in the root
source was intentionally not copied into `horizon/data`. Requests outside the
available direct and fallback date coverage should fail assembly rather than
treating missing evaporation as zero.

For simulator economics, `electricity_price/<node>.csv` is expected to contain:

```csv
date,price_eur_kwh
2005-01-01,0.01
```

The assembler does not copy the raw daily price series into the scenario. It
turns each file into a constant node price equal to the latest-365-record mean.
The simulator then combines that price with `effective_head_m` and turbine
efficiency to compute `water_value_eur_per_m3`, generated electricity, and
period `energy_value`.

When `horizon/nrsm` assembles this bundle into a simulator snapshot, it also
writes a default per-node action CSV named `<node_id>.actions.csv` in the
generated `modules/` directory. Those files are not source data; they are policy
placeholders with daily `scenario_N` columns of production-level fractions.
External optimizers or scenario tools can replace them to control hydropower
release per node per day.

Older data still exists in two historical naming conventions and should not be
mixed into a topology without an explicit mapping:

- **Digital-twin nodes** (used in `topology/`, `climate/era5_*` excluding
  `era5_legacy`, `hydrology/glofas/`, `agriculture/ndvi/` before the hydmod
  MVP switch):
  `lake_victoria_outlet`, `white_nile_to_sudd`, `sudd`, `malakal`,
  `lake_tana_outlet`, `blue_nile_to_gerd`, `gerd`, `blue_nile_to_khartoum`,
  `gezira_irr`, `khartoum`, `khartoum_muni`, `atbara_source`,
  `atbara_confluence`, `merowe`, `main_nile_to_aswan`, `aswan`, `egypt_ag`,
  `cairo_muni`, `delta`.

- **Legacy/canonical MVP nodes** (used in `climate/era5_legacy/`,
  `agriculture/water_usage/`, `electricity_price/`):
  `aswand`, `cairo`, `gerd`, `karthoum`, `kashm`, `merowe`, `ozentari`,
  `roseires`, `singa`, `southwest`, `tana`, `tsengh`, `victoria`.

## Source provenance

| Destination                          | Original location                                    |
|--------------------------------------|------------------------------------------------------|
| `topology/{catalog,nodes,edges}.csv` | `horizon/nile-digital-twin/data/csv/`                |
| `topology/nodes.geojson`             | `horizon/nile-digital-twin/data/`                    |
| `topology/node_config*.yaml`         | `horizon/nile-digital-twin/data/`                    |
| `hydmod/raw/`                        | `hydmod/*.txt`                                       |
| `hydmod/catchments.csv`              | Normalized from `hydmod/catchments.txt` and station centroids |
| `hydmod/daily/`                      | Normalized from `hydmod/hydro_*.txt`                 |
| `evaporation/direct/`                | Normalized from `main/modules/evaporation/evap_csv/*_direct.csv` |
| `climate/era5_daily/`                | `horizon/nile-digital-twin/data/csv/era5_daily/`     |
| `climate/era5_monthly/`              | `horizon/nile-digital-twin/data/csv/era5_monthly/`   |
| `climate/era5_land_monthly/`         | `horizon/nile-digital-twin/data/csv/era5_land_monthly/` |
| `climate/era5_legacy/`               | `agriculture/era5_cache/`                            |
| `hydrology/glofas/`                  | `horizon/nile-digital-twin/data/csv/glofas/`         |
| `agriculture/water_usage/`           | Normalized from `main/modules/food_production/final/*.csv`; `water_m3_s` converted to `water_m3_day` |
| `agriculture/ndvi/`                  | `horizon/nile-digital-twin/data/csv/ndvi/`           |
| `agriculture/egypt_ndvi.tiff`        | `agriculture/egypt_ndvi.tiff`                        |
| `electricity_price/`                 | `electricity_price/price_csv/`                       |
| `examples/headwater_inflow.csv`      | `main/example/data/headwater_inflow.csv`             |

`main/modules/food_production/final/` is the canonical agricultural demand split
for the MVP. The per-node files are stored in `water_m3_s`; `horizon/data`
retains that source column and adds `water_m3_day` for the simulator. The
aggregate `agriculture/water_usage/nile_water_demand.csv` is the sum of the
normalized per-node `water_m3_day` columns and is kept as a validation aid.
