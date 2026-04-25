# Data sources

Every number the twin shows traces back to one of the datasets below. This page explains what each source is, how we fetch it, where it lands in the pipeline, and the gotchas you'll hit in practice.

Everything is free-tier Copernicus or public hydrology, with sane fallbacks so the demo still runs offline.

---

## 1. ERA5 reanalysis (climate forcings)

**What it is.** Global reanalysis of the atmosphere and land from 1940 to ~5 days ago, produced by ECMWF for the Copernicus Climate Change Service (C3S). "Reanalysis" = a single consistent physics model re-run over decades, assimilating every available observation (satellite, radiosonde, surface) into a gridded estimate.

**Resolution.** 0.25° × 0.25° (~27 km at the equator). Daily means via the `derived-era5-single-levels-daily-statistics` product — dramatically faster to fetch than hourly.

**Variables we use** (CDS names → our Parquet column):

| CDS variable | Column | Role |
|---|---|---|
| `total_precipitation` | `precip_mm` | Catchment input |
| `2m_temperature` | `temp_c` | Penman PET |
| `2m_dewpoint_temperature` | `dewpoint_c` | Penman PET (humidity) |
| `surface_solar_radiation_downwards` | `radiation_mj_m2` | Penman PET |
| `10m_u/v_component_of_wind` | `wind_ms` | Penman PET |
| `runoff` | `runoff_mm` | Source-node inflow |

**How to fetch.**
1. Register a free account at <https://cds.climate.copernicus.eu/>.
2. Accept the licence for the `derived-era5-single-levels-daily-statistics` dataset.
3. Put your API key in `~/.cdsapirc` (two lines: `url:` + `key:`).
4. `python -m dataloader forcings` (no `--stub`).

**Gotchas.**
- The CDS API queues requests; expect 10–60 min wall clock for the 19-node catchment sweep.
- First-time dataset usage requires clicking an "I agree" licence link — not automated.
- Rate-limiting kicks in at ~20 simultaneous requests; the dataloader serialises per-node.
- Files download as NetCDF — install `netcdf4` or `h5netcdf` before running the real fetch (both are optional deps).

**Licence.** CC-BY 4.0 — cite Copernicus / ECMWF.

**Documentation.** <https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics>

---

## 2. Sentinel-2 L2A (NDVI overlay, 2015–present)

**What it is.** Optical satellite imagery from ESA's Sentinel-2 constellation. Level-2A = atmospherically-corrected surface reflectance at 10, 20, and 60 m resolution. We use B04 (red) and B08 (NIR) to compute NDVI, and the SCL (scene classification) layer to mask clouds / shadow / water.

**Resolution.** 10 m native; we downsample to 60 m for zone-mean aggregation. 5-day revisit globally (higher near equator with cloud-adjusted effective revisit).

**Where it goes.** `data/overlays/ndvi/<zone>.parquet` — monthly mean, std, and valid-pixel fraction per irrigation zone. Zones defined in `dataloader/nodes.py::NDVI_ZONES` (currently Gezira + Egyptian Delta).

**How to fetch.**
1. Free account at the Copernicus Data Space Ecosystem: <https://dataspace.copernicus.eu/>.
2. No credentials needed for STAC read — the public catalog endpoint is `https://stac.dataspace.copernicus.eu/v1/`.
3. `pip install pystac-client stackstac rioxarray` (optional deps — not in base requirements because they're heavy).
4. `python -m dataloader overlays` (no `--stub`).

**Gotchas.**
- Cloud cover over the Nile Delta in winter can drop `valid_pixel_frac` below 0.3; filter the series before using it for feedback into the food KPI.
- `stackstac` is memory-hungry on long time ranges; the dataloader chunks by year.
- Sentinel-2 starts July 2015 — pre-2015 NDVI comes from CGLS (below).

**Licence.** Free, open, no restrictions on redistribution. Attribute as "Contains modified Copernicus Sentinel data 2015–2024."

**Documentation.** <https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel2.html>

---

## 3. CGLS NDVI (NDVI overlay, 2005–2014)

**What it is.** Copernicus Global Land Service harmonised NDVI product, ~1 km global, decadal then monthly. Built from PROBA-V (2014–2020) and Sentinel-3 OLCI (2016+), with SPOT-VGT back to 1999. Used as the pre-Sentinel-2 gap-filler so the dashboard's month scrubber has tiles across the full 2005–2024 window.

**Resolution.** 1 km, monthly.

**Where it goes.** Same `data/overlays/ndvi/<zone>.parquet` — prepended to the Sentinel-2 series with a `source` attribute in the Parquet metadata so you can tell them apart if needed.

**How to fetch.**
- Requires a VITO Terrascope account: <https://terrascope.be/>.
- Products under the `CGLS_NDVI_V3_Global` collection via OpenEO or direct HTTP.
- The dataloader stubs this out by default and emits a warning; 2015+ Sentinel-2 is enough for the pitch, and the pre-2015 NDVI story can be told from a static chart if time is short.

**Gotchas.**
- Registration is the biggest blocker; can take a day for approval.
- If you're on a deadline and can't get credentials, leave `_cgls_ndvi_monthly` in stub mode and note "pre-2015 climatology" in the caption.

**Documentation.** <https://land.copernicus.eu/en/products/vegetation/normalised-difference-vegetation-index-v3-0-1km>

---

## 4. GRDC river discharge (calibration target)

**What it is.** Global Runoff Data Centre — the world's authoritative river-gauge archive, run by BfG (Germany) under WMO auspices. Monthly mean discharge at hundreds of Nile-basin stations, including Aswan (station 1362100) and Dongola (1363100).

**Where it goes.** `data/observed/aswan_discharge.parquet` — two columns, `month` and `discharge_m3s`. Only read by the calibration loop (`calibration/calibrate.py`).

**How to fetch.**
- Request data at <https://grdc.bafg.de/> (email-based process, usually returns within a day).
- Save the monthly discharge CSV on a shared team drive.
- Export its URL as `GRDC_ASWAN_CSV_URL=https://...` and run `python -m calibration.grdc_fetch`.

**Fallback.**
- Without `GRDC_ASWAN_CSV_URL`, the fetcher falls back to a climatology derived from Sutcliffe & Parks (1999, "The Hydrology of the Nile") — a single repeating year. Good enough to smoke-test the calibration loop, not good enough to actually calibrate against.

**Gotchas.**
- GRDC licensing forbids bulk redistribution of the raw time-series; the fallback climatology sidesteps this by being a literature-derived summary, not the raw dataset.

**Documentation.** <https://grdc.bafg.de/> — "Datasets / River Discharge Time Series".

---

## 5. Static metadata (reservoirs, crops, population)

Not fetched — hand-curated inside `dataloader/nodes.py`. Sources per field:

| Field | Source |
|---|---|
| Reservoir `storage_capacity_mcm`, `storage_min_mcm`, `surface_area_km2_at_full` | ICOLD World Register of Dams + Wikipedia infoboxes cross-checked. GERD: 74 000 / 14 800 / 1 874. Aswan: 162 000 / 31 600 / 5 250. |
| HEP `nameplate_mw`, `head_m`, `efficiency` | Dam operator factsheets. GERD: 6 450 MW / 133 m / 0.9. Aswan: 2 100 MW / 70 m / 0.88. Merowe: 1 250 MW / 67 m / 0.88. |
| `crop_water_productivity_kg_per_m3` | FAO AquaStat country profiles. Gezira (Sudan cotton/wheat rotation) = 1.2. Egypt-ag (rice/maize/wheat) = 1.5. |
| `per_capita_l_day` | WHO guideline 150–200 L/day for urban Africa. Cairo = 200, Khartoum = 150. |
| `population_baseline` | UN World Urbanization Prospects 2022. Cairo metro 20 M, Khartoum 5.5 M. |
| `evap_loss_fraction_baseline` (Sudd) | 0.5, cited across hydrology literature from Sutcliffe & Parks onwards. |
| `catchment_area_km2` | HydroSHEDS / basin atlases. Lake Victoria catchment ~195 000 km². Lake Tana ~15 000 km². Atbara ~112 000 km². |
| Node lat/lon | Hand-picked at the dam centroid, lake outlet, or irrigation scheme centre. |

**Gotcha.** Every number here is approximate. Calibration (L5) tunes `catchment_scale` at each source to correct for both runoff-to-catchment-area uncertainty AND other structural errors in the model. The static numbers above are the honest defaults; `catchment_scale` is the knob.

---

## 6. Basemap + map tiles

- **Dashboard basemap** — CARTO "light_all" raster, served from `a/b/c.basemaps.cartocdn.com`. Free for moderate use; <https://carto.com/attribution/>. The MapLibre style is committed at `frontend/public/nile-style.json`.
- **NDVI overlay tiles** — pre-rendered by `dataloader tiles` into `data/tiles/ndvi/<zone>/<YYYY-MM>/{z}/{x}/{y}.png`, served statically from the API's `/tiles` mount. Currently only zoom 7 is pre-rendered; the raster source clamps `minzoom=maxzoom=7` so MapLibre doesn't 404 at other zooms. Swap for `rio-tiler` if you want a full pyramid.

---

## Data directory layout

What ends up on disk once the real pipeline has run:

```
data/
├── nodes.geojson                        # L1 Task 2
├── node_config.yaml                     # L1 Task 2 (+ updated by L5 calibrate)
├── timeseries/
│   ├── lake_victoria_outlet.parquet     # ERA5 forcings
│   ├── gerd.parquet
│   └── … (19 files, one per node)
├── overlays/
│   └── ndvi/
│       ├── gezira.parquet               # Sentinel-2 + CGLS
│       └── egypt_delta.parquet
├── tiles/
│   └── ndvi/
│       └── gezira/
│           └── 2020-07/7/0/0.png        # one PNG per (zone, month)
├── observed/
│   └── aswan_discharge.parquet          # GRDC (calibration target)
├── scenarios/
│   └── <uuid>.json                      # each saved scenario
└── raw_era5/
    └── gerd.nc                          # ERA5 NetCDF cache (can be purged)
```

## License summary

| Layer | Licence |
|---|---|
| ERA5 | CC-BY 4.0 (Copernicus) |
| Sentinel-2 | Free, open (modified Copernicus Sentinel data) |
| CGLS NDVI | CC-BY 4.0 (Copernicus) |
| GRDC | Non-redistribution for bulk data; attribution for derived works |
| CARTO basemap | Free tier, requires attribution |
| Static metadata | Public sources (FAO, UN, ICOLD, WHO) — all citeable |
