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
├── agriculture/
│   ├── water_usage/          nile_<node>_water.csv + nile_water_usage_all.csv
│   │                         (legacy node naming)
│   ├── ndvi/                 NDVI timeseries CSVs (gezira, egypt_delta)
│   └── egypt_ndvi.tiff       NDVI raster
│
├── electricity_price/        Per-node price CSVs (legacy node naming)
│
└── examples/
    └── headwater_inflow.csv  Sample inflow used by main/example
```

## Two node naming conventions

The data here comes from two different topology models — they are **not
interchangeable**:

- **Digital-twin nodes** (used in `topology/`, `climate/era5_*` excluding
  `era5_legacy`, `hydrology/glofas/`, `agriculture/ndvi/`):
  `lake_victoria_outlet`, `white_nile_to_sudd`, `sudd`, `malakal`,
  `lake_tana_outlet`, `blue_nile_to_gerd`, `gerd`, `blue_nile_to_khartoum`,
  `gezira_irr`, `khartoum`, `khartoum_muni`, `atbara_source`,
  `atbara_confluence`, `merowe`, `main_nile_to_aswan`, `aswan`, `egypt_ag`,
  `cairo_muni`, `delta`.

- **Legacy nodes** (used in `climate/era5_legacy/`, `agriculture/water_usage/`,
  `electricity_price/`):
  `aswand`, `cairo`, `gerd`, `karthoum`, `kashm`, `merowe`, `ozentari`,
  `roseires`, `singa`, `southwest`, `tana`, `tsengh`, `victoria`.

## Source provenance

| Destination                          | Original location                                    |
|--------------------------------------|------------------------------------------------------|
| `topology/{catalog,nodes,edges}.csv` | `horizon/nile-digital-twin/data/csv/`                |
| `topology/nodes.geojson`             | `horizon/nile-digital-twin/data/`                    |
| `topology/node_config*.yaml`         | `horizon/nile-digital-twin/data/`                    |
| `climate/era5_daily/`                | `horizon/nile-digital-twin/data/csv/era5_daily/`     |
| `climate/era5_monthly/`              | `horizon/nile-digital-twin/data/csv/era5_monthly/`   |
| `climate/era5_land_monthly/`         | `horizon/nile-digital-twin/data/csv/era5_land_monthly/` |
| `climate/era5_legacy/`               | `agriculture/era5_cache/`                            |
| `hydrology/glofas/`                  | `horizon/nile-digital-twin/data/csv/glofas/`         |
| `agriculture/water_usage/`           | `agriculture/nile_*_water.csv`                       |
| `agriculture/ndvi/`                  | `horizon/nile-digital-twin/data/csv/ndvi/`           |
| `agriculture/egypt_ndvi.tiff`        | `agriculture/egypt_ndvi.tiff`                        |
| `electricity_price/`                 | `electricity_price/price_csv/`                       |
| `examples/headwater_inflow.csv`      | `main/example/data/headwater_inflow.csv`             |

`main/modules/food_production/` and `main/modules/energy_price/price_csv/` were
verified to be byte-identical duplicates of `agriculture/` and
`electricity_price/price_csv/` respectively, so they were not copied separately.
