# Electricity Price Estimator — Method Description

## Overview

This tool estimates daily mean electricity prices (EUR/kWh) for 13 Nile-basin
nodes from **1950-01-01 to today**, using observed ERA5 solar radiation data
from Copernicus and country-level retail price anchors.

---

## Input Data

### Node geometry — `nile.yaml`
Each node provides:
- Geographic centroid (`latitude`, `longitude`)
- Catchment drainage `area` (km²) — used to define the spatial averaging box

### ERA5 clear-sky data — Copernicus Climate Data Store
- **Dataset:** `reanalysis-era5-single-levels`  
- **Variable:** `sunshine_duration` (seconds of sunshine per hour)  
- **Native resolution:** 0.25° (~28 km); downloaded at 0.5° to reduce file size  
- **Time range downloaded:** 2015-01-01 → 2024-12-31 (~9 years)  
- **Access:** via the official `cdsapi` Python client  
  Credentials: register free at <https://cds.climate.copernicus.eu>

> Hersbach, H., et al. (2023). *ERA5 hourly data on single levels from 1940
> to present*. ECMWF. <https://doi.org/10.24381/cds.adbb2d47>

### Retail electricity prices — 2025 anchor values

| Country | Node(s) | USD/kWh | EUR/kWh | Source |
|---------|---------|--------:|--------:|--------|
| Uganda | victoria | 0.165 | 0.153 | GlobalPetrolPrices.com Sep-2025 |
| South Sudan | southwest | 0.350 | 0.326 | World Bank Africa Energy 2022 |
| Sudan | karthoum, merowe, singa, kashm, tsengh | 0.044 | 0.041 | GlobalPetrolPrices.com Sep-2025 |
| Ethiopia | gerd, roseires, tana, ozentari | 0.006 | 0.006 | GlobalPetrolPrices.com Sep-2025 |
| Egypt | aswand, cairo | 0.021 | 0.020 | GlobalPetrolPrices.com Sep-2025 |

Conversion: 1 USD = 0.93 EUR (2025 average).

---

## Spatial Averaging

For each node a **bounding box** is computed from the catchment area:

```
half_width_deg = sqrt(area_km² / π) / 111 km·deg⁻¹  +  1.0°  (padding)
```

All ERA5 grid cells whose centres fall inside the box are averaged to give a
single daily sunshine value for the node. This captures the spatial
heterogeneity of cloud cover across large catchments (up to ~580 000 km²
for the Sudd / White Nile node).

---

## Temporal Coverage — Cyclic Tiling

ERA5 data spans **2015–2024** (3 653 days). To extend back to 1950 the series
is **tiled cyclically**:

```
src_date = ERA5_start  +  (target_date − ERA5_start)  mod  ERA5_span
```

This preserves the realistic day-to-day and year-to-year variability of the
observed ERA5 record across the full 75-year simulation window. It is a
simplification — it cannot reproduce actual historical drought or flood years
before 2015 — but it provides physically plausible seasonal structure.

---

## Generation Source Types

Each node is assigned a **primary** and **secondary** generation source based
on national energy-mix data (EIA 2022):

| Source | Description | Regions |
|--------|-------------|---------|
| `hydro` | Run-of-river / reservoir hydropower | victoria, karthoum, merowe, singa, roseires, gerd, tana, kashm, tsengh, ozentari |
| `solar` | Grid-scale photovoltaics | aswand (Aswan), merowe (secondary) |
| `gas` | Pipeline natural gas / coal thermal | cairo (Egypt), karthoum (secondary) |
| `diesel` | Off-grid diesel generators | southwest (South Sudan) |

The final daily price is a **weighted blend**:
```
price = 0.75 × primary_price  +  0.25 × secondary_price
```

---

## Price Models

### Solar
Splits each day into solar-active hours (from ERA5 sunshine duration) and
non-solar hours:

```
price = f_sun × SOLAR_DAYTIME_PRICE  +  (1 − f_sun) × SOLAR_NIGHTTIME_PRICE
```

where `f_sun = sunshine_hours / 24`.  
Default values: daytime 0.020 €/kWh (abundant rooftop / utility solar),
nighttime 0.090 €/kWh (gas / regional import).

### Hydro
Cosine seasonal model aligned to the Nile flow cycle:

```
price = mid − A × cos(2π (DOY − peak_DOY) / 365)
```

- `mid = (wet_price + dry_price) / 2`  
- `A = (dry_price − wet_price) / 2 × HYDRO_SEASONALITY`  
- Peak flow (cheap): **day 213 ≈ 1 August** (monsoon-driven Nile high water)  
- Trough (expensive): **day 30 ≈ 30 January** (low reservoir, dry season)  
- Default range: 0.030 – 0.080 EUR/kWh before normalisation

### Gas (pipeline)
Near-constant rate with a small demand-driven swing:

```
price = GAS_BASE_PRICE  +  GAS_SEASONAL_AMP × cos(2π (DOY − 15) / 365)
```

Peaks in mid-January (space-heating demand in North African grid).

### Diesel (off-grid)
High flat rate reflecting costly fuel import logistics (South Sudan):

```
price = DIESEL_BASE_PRICE  +  DIESEL_SEASONAL_AMP × cos(2π (DOY − 30) / 365)
```

The seasonal swing reflects dry-season road-access constraints on fuel delivery.  
This is why **South Sudan is ~15× more expensive than Egypt**: Egypt has a
subsidised domestic gas grid, South Sudan has no national grid and generates
electricity from imported diesel fuel.

---

## Regional Normalisation

The raw model produces prices with realistic **shape** (seasonal variation,
day-length variation) but arbitrary **scale**. To anchor the absolute level
to observed 2025 retail prices, each node's series is rescaled:

```
scale = base_price / mean(raw_series)
price_final = price_raw × scale
```

This preserves the seasonal variability while ensuring the long-run mean
equals the country-level retail price.

---

## Output

| File | Contents |
|------|----------|
| `price_csv/<node_id>.csv` | Two-column CSV: `date` (ISO 8601), `price_eur_kwh` |
| `electricity_prices.png` | Four-panel time-series plot with seasonal insets |
| `method.png` | Methodology flowchart |
| `era5_cache/<node_id>_era5_sunshine.nc` | Raw ERA5 NetCDF (per node, auto-deleted on `--download`) |
| `era5_cache/<node_id>_sunshine.json` | Processed daily sunshine cache (hours/day) |

---

## Limitations and Caveats

1. **Tiling is not reanalysis.** The 1950–2014 segment repeats 2015–2024
   patterns; actual historical conditions (e.g. 1988 Nile flood, 2002
   Ethiopian drought) are not represented.
2. **Price models are simplified.** Real electricity markets involve
   capacity markets, fuel contracts, transmission costs, and policy subsidies
   that are not modelled here.
3. **One price level per country.** All nodes in the same country share the
   same 2025 retail price anchor; within-country variation is not captured.
4. **Astronomical fallback.** Without a `~/.cdsapirc` credentials file the
   script falls back to a latitude-based daylight model with an 80 % clear-sky
   fraction — reasonable for the arid/semi-arid Nile basin but less accurate
   for the Ethiopian highlands and Sudd wetlands.
