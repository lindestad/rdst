# Evaporation Estimator — Method Description

## Overview

This tool estimates daily potential evaporation (m³/day) for 13 Nile-basin
reservoirs from **1950-01-01 to today**, using ERA5-Land temperature
data and a linear regression model derived from historical GRIB data.

---

## Input Data

### Node geometry — `nodes.yaml`
Each node provides:
- Geographic centroid (`latitude`, `longitude`)
- Reservoir surface area `reservoir_area_km2`
- Bounding box extent: `lat_min`, `lat_max`, `lon_min`, `lon_max` — used for spatial averaging

### ERA5-Land — Copernicus Climate Data Store
- **Dataset:** `reanalysis-era5-land-monthly-means`
- **Variables:**
  - `potential_evaporation` (parameter `pev`) — mm/day
  - `2m_temperature` (parameter `2t`) — K
- **Native resolution:** 0.1° × 0.1° (≈ 9 km)
- **Time range:** 1950 – present (cached locally)
- **Access:** via the official `cdsapi` Python client

> Hersbach, H., et al. (2023). *ERA5-Land hourly data from 1940
> to present*. ECMWF. <https://doi.org/10.24381/cds.adbb2d47>

### Land/Sea Mask — LSM
- **Source:** ERA5-Land static file
- **Purpose:** Filter out land pixels, retain only water pixels for evaporation calculation

---

## Linear Regression Model

### Training Data
From the test-emilio GRIB file, for each lake:
- Temperature: ERA5 `2t` (K) → °C
- Evaporation: ERA5 `e` (m water equivalent) → mm, negated (condensation = positive)
- Masked by land/sea (LSM < 0.5 = water)

### Regression
```
evaporation_mm = slope × temperature_celsius + intercept
```

Coefficients stored in `regression_coefficients.json` per lake.

---

## Per-Lake Extents

Bounding boxes defined in `nodes.yaml` for each reservoir:

| Node | lat_min | lat_max | lon_min | lon_max |
|------|---------|---------|---------|--------|
| victoria | -2.7 | 0.5 | 31.5 | 34.5 |
| southwest | 5.0 | 12.0 | 27.0 | 32.0 |
| karthoum | 15.0 | 16.0 | 32.0 | 34.0 |
| merowe | 18.5 | 19.5 | 31.5 | 33.5 |
| aswand | 22.82 | 24.0 | 32.4 | 33.1 |
| cairo | 29.5 | 31.5 | 30.5 | 32.5 |
| ... | ... | ... | ... | ... |

---

## Temporal Coverage — Cyclic Tiling

ERA5-Land monthly data spans **1950–2026**. The series is tiled cyclically:

```
src_date = ERA5_start + (target_date - ERA5_start) mod ERA5_span
```

Monthly values are interpolated to daily using PCHIP (Piecewise Cubic Hermite
Interpolating Polynomial), preserving monotonicity.

---

## Output

### Volume Calculation
```
evaporation_m3_day = evaporation_mm_day × reservoir_area_km2 × 1000
```

### Scenario Generation
For `n_scenarios`:
- Base: deterministic model using (slope, intercept)
- Scenario variations: ±σ perturbation from regression residuals

### Output Files

| File | Contents |
|------|----------|
| `evap_csv/<node_id>.csv` | `date`, `scenario_1`, ..., `scenario_N` (m³/day) |
| `evap_regression.png` | Scatter plot with regression line |
| `era5_cache/<node_id>_pev.json` | Cached potential evaporation (mm/day) |
| `era5_cache/<node_id>_2t.json` | Cached temperature (K) |

---

## CLI Usage

```bash
python evaporation.py --start-date 1950-01-01 --end-date 2026-12-31 --n-scenarios 3
```

### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--start-date` | First day (ISO 8601) | Required |
| `--end_date` | Last day (ISO 8601) | Required |
| `--n-scenarios` | Number of scenario columns | 1 |
| `--download` | Force re-download from CDS | False |

---

## Limitations and Caveats

1. **Tiling is not reanalysis.** The pre-ERA5 period (1950s-1970s) repeats
   later patterns; actual historical conditions are not captured.
2. **Linear model is simplified.** Real evaporation depends on humidity,
   wind, solar radiation, not just temperature.
3. **Land mask alignment.** The LSM and ERA5 grids must be aligned precisely;
   mis-registration causes errors.
4. **CDS credentials required.** Without `~/.cdsapirc`, script fails.
   Register free at <https://cds.climate.copernicus.eu>