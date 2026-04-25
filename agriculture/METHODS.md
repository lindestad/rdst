# Nile Basin Agricultural Water Usage — Methods

## What this script does

Estimates daily agricultural water demand (m³/day) for 13 nodes defined in
`nile.yaml`, covering the Nile basin from Lake Victoria (−1°N) to Cairo (30.8°N),
for the period 1950–2026.

---

## Input data

### ERA5-Land monthly means — primary backbone

| Property | Value |
|---|---|
| Source | Copernicus Climate Change Service (C3S), ECMWF |
| Dataset | `reanalysis-era5-land-monthly-means` |
| Variable | `potential_evaporation` (parameter `pev`) |
| Units | m water equivalent per day (monthly mean daily rate) |
| Period | 1950 – present |
| Native resolution | 0.1° × 0.1° (≈ 9 km) |
| Access | Copernicus CDS, `cdsapi`, cached in `era5_cache/` |

ERA5-Land is a reanalysis product: it combines a land-surface model with ERA5
atmospheric forcing to produce a physically consistent, globally complete
reconstruction of land-surface conditions. It is not direct measurement — it
is modelled output constrained by assimilated observations.

`potential_evaporation` represents the evapotranspiration that would occur from
a reference surface (short well-watered grass, equivalent to FAO-56 ET₀) under
the prevailing meteorological conditions. It captures real year-to-year climate
variability: drought years produce higher ET₀; cool or cloudy periods lower it.

### Sentinel-2 NDVI — optional Kc overlay (2017–present)

| Property | Value |
|---|---|
| Source | Copernicus Dataspace, Sentinel Hub Statistics API |
| Sensor | Sentinel-2 MSI L2A (10 m) |
| Variable | NDVI (B08 − B04) / (B08 + B04), SCL cloud-masked |
| Cadence | 5-day aggregation windows |
| Period | 2017 – present |
| Access | Sentinel Hub Statistics API, requires `ACCESS_TOKEN` |

Used only to derive a more realistic crop coefficient for the satellite era
(see Kc section below). Falls back to the seasonal table if unavailable.

---

## Point estimate or area mean?

**Single grid cell (point estimate).** The CDS request specifies a 0.1° bounding
box centred on the node's coordinates, which selects the single nearest ERA5-Land
grid cell. The resulting ET₀ value is therefore representative of one ≈ 9 km cell,
not an average over the agricultural zone.

This is a known limitation. The agricultural zones in `nile.yaml` span areas of
8 000–43 500 ha (up to ≈ 66 km across), so spatial variability within a zone is
not captured. For the Nile Valley — a narrow irrigated corridor in an otherwise
arid landscape — the single-cell approach is a reasonable first approximation,
but should be treated with caution for large zones such as Victoria and Southwest.

---

## Method

### 1. Monthly ET₀ to daily

Monthly ERA5-Land means are assigned to the 15th of each month and interpolated
to daily resolution using a PCHIP (Piecewise Cubic Hermite Interpolating
Polynomial) spline. This preserves monotonicity within each month and avoids
the overshoot that cubic splines can introduce. All values are clamped to ≥ 0.

### 2. Crop coefficient Kc

```
ET_crop [mm/day] = Kc × ET₀ [mm/day]
```

Two sources, in order of priority:

| Era | Kc source |
|---|---|
| 1950 – 2016 (or if no token) | Seasonal table from Nile crop calendar |
| 2017 – present (if `ACCESS_TOKEN` set) | NDVI-derived: `Kc = clamp(1.457 × NDVI − 0.1, 0.15, 1.25)` |

Seasonal Kc table (monthly, index 0 = January):

```
0.90 0.90 0.85 0.80 0.75 0.75 0.78 0.80 0.83 0.88 0.92 0.92
```

Values reflect the mixed Nile crop calendar: winter wheat and vegetables
(Oct–Apr, Kc ≈ 0.85–0.92) and summer rice / cotton and fallow (Jun–Sep,
Kc ≈ 0.75–0.80).

### 3. Water volume

```
Volume [m³/day] = ET_crop [mm/day] × 10 × area_ha
```

The factor of 10 converts mm over hectares to cubic metres
(1 mm × 1 ha = 0.001 m × 10 000 m² = 10 m³).

`area_ha` for each node is stored in `nile.yaml` and was estimated from the
node's `food_production` parameters (`water_coefficient × max_food_units / 60`),
representing the irrigated cropland associated with each basin segment.

---

## What the output tells us

The time series is an estimate of **agricultural water demand** — how much water
the crops in each zone would consume under the observed climate, assuming
continuous irrigation and a representative crop mix. It is not a measurement of
actual abstraction or conveyance losses.

Key uses:

- **Long-term trend**: whether ET₀ (and therefore demand) is increasing with
  warming, and where that signal is strongest in the basin.
- **Interannual variability**: identifying drought years (e.g. Sahel droughts of
  the 1980s) and their downstream demand implications.
- **Relative basin contribution**: which nodes drive total basin demand, and how
  that balance shifts seasonally.
- **Baseline for water balance modelling**: the `nile.yaml` network model can use
  these demand time series as `food_production` water withdrawals at each node.

---

## Does the script account for rainfall?

Yes — implicitly. The script estimates **total crop water consumption** (ET_crop),
which is the sum of all water a crop evapotranspires regardless of source — rain,
soil moisture, or Nile irrigation. This is exactly the right quantity when the
question is *how much water does agriculture consume*, not *how much must be pumped*.

ERA5-Land `potential_evaporation` is driven by real meteorological conditions
(temperature, humidity, radiation, wind) that already reflect local rainfall
patterns. In a wet year or a wet node, ET₀ is naturally lower (higher humidity,
less vapour pressure deficit), so the demand estimate already responds to the
wetter climate — there is no need to separately subtract rainfall.

The output should therefore be read as **total agricultural water demand**:
water withdrawn from the hydrological cycle by crops, whether supplied by
precipitation or by Nile abstractions.

---


