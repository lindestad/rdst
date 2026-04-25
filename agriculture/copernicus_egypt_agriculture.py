"""
Nile Basin Agricultural Water Usage — Daily Time Series, 1950–2026
===================================================================
Estimates daily crop water consumption for agricultural zones defined in
nile.yaml, covering the full Nile basin from Lake Victoria to Cairo.

Primary pipeline  (1950–2026)
------------------------------
1. ``download_era5_monthly_et()`` – ERA5-Land monthly mean potential
                                    evaporation via the Copernicus CDS API.
                                    One request per location covers the full
                                    period; results are cached locally.
2. ``era5_monthly_to_daily()``   – Cubic-spline interpolation of monthly
                                    means to daily ET₀ values.
3. ``seasonal_kc()``             – Nile crop-calendar Kc (crop coefficient)
                                    applied per month.
4. ``compute_daily_water_usage()``– ET_crop × area → m³/day per zone.
5. ``export_csv()``              – Per-location daily CSV files.
6. ``plot_water_usage()``        – Three-panel figure covering the full
                                    time range.

Optional Sentinel-2 overlay  (2017–present)
--------------------------------------------
7. ``get_ndvi_timeseries()``     – Sentinel Hub Statistics API, 5-day
                                    aggregation intervals → sparse NDVI.
8. ``ndvi_kc()``                 – NDVI-derived Kc replaces the seasonal
                                    proxy for the satellite era.

Method
------
  ET₀ [mm/day]     from ERA5-Land ``potential_evaporation`` (monthly mean
                   interpolated to daily via cubic spline)
  Kc               seasonal proxy  OR  Kc(NDVI) = clamp(1.457·NDVI−0.1,
                                                         0.15, 1.25)
  ET_crop [mm/day] = Kc × ET₀
  Volume  [m³/day] = ET_crop × 10 × area_ha

Usage
-----
    # CDS credentials (https://cds.climate.copernicus.eu/):
    export CDS_API_KEY="<uid>:<key>"

    # Optional – Sentinel Hub token for NDVI overlay:
    export ACCESS_TOKEN="<token>"

    python3 copernicus_egypt_agriculture.py
"""

import math
import os
import pathlib
import re
import sys
from datetime import date, timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import requests
import yaml

# ──────────────────────────────────────────────────────────────────────────────
# Credentials
# ──────────────────────────────────────────────────────────────────────────────

# CDS API key (required for ERA5 downloads): https://cds.climate.copernicus.eu/
# Format: "UID:API_KEY"  — falls back to ~/.cdsapirc if unset.
CDS_API_KEY = os.environ.get("CDS_API_KEY")

# Sentinel Hub / Copernicus Dataspace token (optional — for NDVI overlay only).
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
_SH_AVAILABLE = bool(ACCESS_TOKEN)
_AUTH  = ({"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
          if ACCESS_TOKEN else {})
_OAUTH = ({"Authorization": f"Bearer {ACCESS_TOKEN}"} if ACCESS_TOKEN else {})

# ──────────────────────────────────────────────────────────────────────────────
# API endpoints
# ──────────────────────────────────────────────────────────────────────────────
STAC_URL  = "https://catalogue.dataspace.copernicus.eu/stac/search"
ODATA_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
CDS_URL   = "https://cds.climate.copernicus.eu/api/v2"

# ERA5 cache directory (relative to this script)
ERA5_CACHE_DIR = pathlib.Path(__file__).with_name("era5_cache")

# ──────────────────────────────────────────────────────────────────────────────
# Agricultural zones — loaded from nile.yaml (south → north)
# ──────────────────────────────────────────────────────────────────────────────
def _load_nile_locations(yaml_path: str | pathlib.Path = "nile.yaml") -> list[dict]:
    """Parse nile.yaml nodes into location dicts for the estimation pipeline."""
    with open(yaml_path) as fh:
        data = yaml.safe_load(fh)
    locations = []
    for node in data.get("nodes", []):
        if "area_ha" not in node:
            continue
        locations.append({
            "name":    node["id"].capitalize(),
            "lon":     float(node["longitude"]),
            "lat":     float(node["latitude"]),
            "area_ha": int(node["area_ha"]),
        })
    # Sort south → north
    locations.sort(key=lambda loc: loc["lat"])
    return locations

_YAML_PATH = pathlib.Path(__file__).with_name("nile.yaml")
NILE_LOCATIONS = _load_nile_locations(_YAML_PATH)

# ──────────────────────────────────────────────────────────────────────────────
# Seasonal crop coefficient (Kc) — Nile basin irrigated agriculture
# Reflects mixed winter crops (wheat/vegetables Oct–Apr) and summer crops
# (rice/cotton Jun–Sep) weighted by typical Nile Valley crop calendars.
# Index 0 = January … 11 = December
# ──────────────────────────────────────────────────────────────────────────────
_KC_MONTHLY = [0.90, 0.90, 0.85, 0.80, 0.75, 0.75, 0.78, 0.80, 0.83, 0.88, 0.92, 0.92]

# Evalscript: SCL-masked NDVI (Sentinel-2, used for optional Kc overlay)
_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input:  [{ bands: ["B04", "B08", "SCL"] }],
    output: [
      { id: "ndvi",     bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1, sampleType: "UINT8"   }
    ]
  };
}
function evaluatePixel(s) {
  let ok   = [4, 5, 6, 7, 11].includes(s.SCL) ? 1 : 0;
  let ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 1e-4);
  return { ndvi: [ndvi], dataMask: [ok] };
}
"""


# ──────────────────────────────────────────────────────────────────────────────
# ERA5-Land backend  (primary data source, 1950–present)
# ──────────────────────────────────────────────────────────────────────────────

def _era5_slug(location: dict) -> str:
    """File-safe slug for a location name."""
    return re.sub(r"\W+", "_", location["name"].lower()).strip("_")


def _era5_cache_file(location: dict, year_from: int, year_to: int) -> pathlib.Path:
    ERA5_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return ERA5_CACHE_DIR / f"{_era5_slug(location)}_{year_from}_{year_to}.csv"


def download_era5_monthly_et(location: dict, year_from: int = 1950,
                              year_to: int = 2026) -> "pd.Series":
    """
    Download ERA5-Land monthly mean potential evaporation for *location*
    via the Copernicus CDS API and return a ``pandas.Series`` of monthly
    ET₀ values (mm/day, positive) indexed by the first day of each month.

    Results are cached under ``era5_cache/`` as a CSV so that subsequent
    runs skip the network request.

    Parameters
    ----------
    location  : dict   must have keys ``lat``, ``lon``, ``name``
    year_from : int    first year (inclusive)
    year_to   : int    last year  (inclusive)

    Returns
    -------
    pd.Series  index = monthly DatetimeIndex, values = ET₀ in mm/day
    """
    import cdsapi
    import pandas as pd
    import xarray as xr

    cache_csv = _era5_cache_file(location, year_from, year_to)
    if cache_csv.exists():
        s = pd.read_csv(cache_csv, index_col=0, parse_dates=True).squeeze("columns")
        s.name = "et0_mm_day"
        return s

    lat, lon = location["lat"], location["lon"]
    tmp_nc = ERA5_CACHE_DIR / f"_tmp_{_era5_slug(location)}.nc"

    # Build cdsapi.Client kwargs — let the library find ~/.cdsapirc by default;
    # honour CDSAPI_RC (custom rc path), CDS_API_KEY env var, or a .cdsapirc
    # placed next to this script (convenient for project-local credentials).
    cds_kwargs: dict = {"quiet": True}
    if CDS_API_KEY:
        cds_kwargs["url"] = CDS_URL
        cds_kwargs["key"] = CDS_API_KEY
    else:
        local_rc = pathlib.Path(__file__).with_name(".cdsapirc")
        if local_rc.exists():
            os.environ.setdefault("CDSAPI_RC", str(local_rc))

    print(f"    [CDS] Requesting ERA5-Land for {location['name']} "
          f"{year_from}–{year_to} …", flush=True)
    c = cdsapi.Client(**cds_kwargs)
    c.retrieve(
        "reanalysis-era5-land-monthly-means",
        {
            "variable":      "potential_evaporation",
            "product_type":  "monthly_averaged_reanalysis",
            "year":          [str(y) for y in range(year_from, year_to + 1)],
            "month":         [f"{m:02d}" for m in range(1, 13)],
            "time":          "00:00",
            # N / W / S / E  — small box to select nearest 0.1° ERA5-Land cell
            "area":          [lat + 0.05, lon - 0.05, lat - 0.05, lon + 0.05],
            "format":        "netcdf",
        },
        str(tmp_nc),
    )

    # The new CDS API wraps the NetCDF in a ZIP archive even when "netcdf" is
    # requested.  Detect and transparently unpack it before opening.
    import zipfile
    if zipfile.is_zipfile(tmp_nc):
        with zipfile.ZipFile(tmp_nc) as zf:
            nc_names = [n for n in zf.namelist() if n.endswith(".nc")]
            if not nc_names:
                raise RuntimeError("CDS ZIP contains no .nc file")
            extracted = ERA5_CACHE_DIR / f"_extracted_{_era5_slug(location)}.nc"
            with zf.open(nc_names[0]) as src, open(extracted, "wb") as dst:
                dst.write(src.read())
        tmp_nc.unlink(missing_ok=True)
        tmp_nc = extracted

    ds  = xr.open_dataset(tmp_nc, engine="netcdf4")

    # ERA5-Land downloads spanning the expver='0001' (finalized) / '0005' (ERA5T
    # preliminary) boundary can produce a stacked dataset where each time step
    # appears twice — once per experiment version.  Combine them explicitly so
    # that finalized data takes precedence and ERA5T fills the remainder.
    if "expver" in ds.dims:
        ds = ds.sel(expver="0001").combine_first(ds.sel(expver="0005"))

    pev = ds["pev"]  # (time [, lat, lon])  — m/day equivalent, may be negative

    # Squeeze any spatial dimensions (we requested a single cell)
    vals = np.abs(pev.values.squeeze()) * 1000.0  # m → mm/day

    # Build monthly DatetimeIndex (new CDS API uses 'valid_time'; old used 'time')
    time_coord = pev.coords.get("valid_time", pev.coords.get("time"))
    if time_coord is None:
        raise KeyError("ERA5 dataset has neither 'valid_time' nor 'time' coordinate")
    times = pd.DatetimeIndex(time_coord.values)
    s = pd.Series(vals, index=times, name="et0_mm_day")

    ds.close()
    tmp_nc.unlink(missing_ok=True)

    s = _fix_era5_outliers(s)

    s.to_csv(cache_csv, header=True)
    return s


def _fix_era5_outliers(s: "pd.Series", z_thresh: float = 2.5) -> "pd.Series":
    """
    Detect and replace anomalous monthly ERA5 ET₀ values.

    ERA5-Land has known data quality artefacts (e.g. spurious spikes in the
    1960s, suppressed values in 2022-2023) where individual months deviate
    strongly from the long-term climatology for that calendar month.  Any
    month whose value lies more than *z_thresh* standard deviations from the
    long-term mean for that calendar month is replaced by that climatological
    mean, and the replaced indices are reported to stdout.
    """
    s = s.copy()
    # Compute long-term mean and std for each calendar month (1–12)
    clim_mean = s.groupby(s.index.month).transform("mean")
    clim_std  = s.groupby(s.index.month).transform("std")
    z = (s - clim_mean) / clim_std.replace(0, np.nan)
    bad = z.abs() > z_thresh
    if bad.any():
        n = bad.sum()
        print(f"  [ERA5 QC] Replaced {n} outlier month(s) with climatological mean "
              f"(|z| > {z_thresh}): "
              + ", ".join(t.strftime("%Y-%m") for t in s.index[bad]))
        s[bad] = clim_mean[bad]
    return s


def era5_monthly_to_daily(monthly_et: "pd.Series",
                           year_from: int, year_to: int) -> "pd.Series":
    """
    Interpolate monthly ERA5 ET₀ to daily resolution using the 15th of
    each month as the representative day (cubic spline, clamped to ≥ 0).

    Parameters
    ----------
    monthly_et : pd.Series  monthly ET₀ in mm/day (output of
                             ``download_era5_monthly_et``)
    year_from  : int
    year_to    : int

    Returns
    -------
    pd.Series  daily ET₀ in mm/day, index = daily DatetimeIndex
    """
    import pandas as pd
    from scipy.interpolate import PchipInterpolator

    # Assign each monthly value to the 15th of its month
    mid = monthly_et.copy()
    mid.index = pd.DatetimeIndex(
        [pd.Timestamp(t.year, t.month, 15) for t in monthly_et.index]
    )

    daily_idx = pd.date_range(f"{year_from}-01-01", f"{year_to}-12-31", freq="D")

    # Build x (days-since-epoch) arrays for interpolation
    epoch    = pd.Timestamp("1950-01-01")
    x_months = np.array([(t - epoch).days for t in mid.index], dtype=float)
    x_daily  = np.array([(t - epoch).days for t in daily_idx], dtype=float)

    # extrapolate=False → NaN outside [first, last] monthly midpoint;
    # fill those boundary NaNs with the nearest valid value (flat hold) to
    # prevent PCHIP from oscillating wildly beyond the data range.
    interp  = PchipInterpolator(x_months, mid.values, extrapolate=False)
    et_vals = interp(x_daily)
    et_s    = pd.Series(et_vals, index=daily_idx)
    et_s    = et_s.ffill().bfill()
    et_vals = np.maximum(et_s.values, 0.0)  # clamp negatives

    return pd.Series(et_vals, index=daily_idx, name="et0_mm_day")


# ──────────────────────────────────────────────────────────────────────────────
# Sentinel-2 / NDVI functions  (optional Kc overlay for 2017–present)
# ──────────────────────────────────────────────────────────────────────────────

def search_sentinel2_scenes(location, date_from, date_to, max_cloud=20, limit=5):
    """
    Search the STAC catalogue for Sentinel-2 L2A scenes near *location*.

    Returns list of STAC Feature dicts; empty list if unavailable.
    """
    if not _SH_AVAILABLE:
        return []
    r    = 0.10
    bbox = [location["lon"] - r, location["lat"] - r,
            location["lon"] + r, location["lat"] + r]
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox":        bbox,
        "datetime":    f"{date_from}T00:00:00Z/{date_to}T23:59:59Z",
        "query":       {"eo:cloud_cover": {"lte": max_cloud}},
        "limit":       limit,
    }
    try:
        resp = requests.post(STAC_URL, json=payload, headers=_AUTH, timeout=30)
        resp.raise_for_status()
        return resp.json().get("features", [])
    except Exception:
        return []


def search_clms_eta_products(date_from="2024-01-01", date_to="2024-12-31", limit=12):
    """Search OData for CLMS Actual Evapotranspiration (ETA) reference products."""
    if not _SH_AVAILABLE:
        return []
    params = {
        "$filter": (
            "startswith(Name,'c_gls_ET')"
            f" and ContentDate/Start ge {date_from}T00:00:00.000Z"
            f" and ContentDate/Start le {date_to}T23:59:59.000Z"
        ),
        "$top":      limit,
        "$orderby":  "ContentDate/Start desc",
        "$select":   "Id,Name,ContentDate,S3Path",
    }
    try:
        resp = requests.get(ODATA_URL, params=params, headers=_OAUTH, timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])
    except Exception:
        return []


def get_ndvi_timeseries(location, date_from, date_to,
                        interval_days=5, radius_deg=0.05,
                        min_valid_fraction=0.3):
    """
    Fetch a sparse NDVI time series via the Sentinel Hub Statistics API.

    Returns list of (date, ndvi) tuples, or [] if unavailable / on error.
    """
    if not _SH_AVAILABLE:
        return []

    lon, lat = location["lon"], location["lat"]
    bbox     = [lon - radius_deg, lat - radius_deg,
                lon + radius_deg, lat + radius_deg]
    body = {
        "input": {
            "bounds": {
                "bbox":       bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [{"type": "sentinel-2-l2a",
                      "dataFilter": {"maxCloudCoverage": 50}}],
        },
        "aggregation": {
            "timeRange": {
                "from": f"{date_from}T00:00:00Z",
                "to":   f"{date_to}T23:59:59Z",
            },
            "aggregationInterval": {"of": f"P{interval_days}D"},
            "evalscript": _EVALSCRIPT,
        },
    }

    try:
        resp = requests.post(STATS_URL, json=body, headers=_AUTH, timeout=120)
        if resp.status_code != 200:
            return []
    except Exception:
        return []

    observations = []
    for interval in resp.json().get("data", []):
        d_from = date.fromisoformat(interval["interval"]["from"][:10])
        d_to   = date.fromisoformat(interval["interval"]["to"][:10])
        midpt  = d_from + (d_to - d_from) / 2

        stats = (interval.get("outputs", {})
                         .get("ndvi", {})
                         .get("bands", {})
                         .get("B0", {})
                         .get("stats", {}))

        mean_val     = stats.get("mean")
        sample_count = stats.get("sampleCount", 0)
        nodata_count = stats.get("noDataCount", 0)
        total        = sample_count + nodata_count

        try:
            mean_val = float(mean_val)
        except (TypeError, ValueError):
            continue
        if math.isnan(mean_val):
            continue
        if total > 0 and (sample_count / total) < min_valid_fraction:
            continue

        observations.append((midpt, round(mean_val, 4)))

    return observations


# ──────────────────────────────────────────────────────────────────────────────
# Crop coefficient helpers
# ──────────────────────────────────────────────────────────────────────────────

def seasonal_kc(daily_index: "pd.DatetimeIndex") -> np.ndarray:
    """
    Return a Kc array (shape N,) for each day in *daily_index* using the
    Nile-basin crop-calendar monthly table ``_KC_MONTHLY``.
    """
    return np.array([_KC_MONTHLY[t.month - 1] for t in daily_index], dtype=float)


def ndvi_kc(ndvi_array: np.ndarray) -> np.ndarray:
    """Derive Kc from NDVI: Kc = clamp(1.457·NDVI − 0.1, 0.15, 1.25)."""
    return np.clip(1.457 * np.maximum(ndvi_array, 0.0) - 0.1, 0.15, 1.25)


def _ndvi_obs_to_daily(observations: list, daily_index: "pd.DatetimeIndex") -> np.ndarray:
    """Linearly interpolate sparse NDVI observations onto *daily_index*."""
    import pandas as pd
    if not observations:
        return np.full(len(daily_index), 0.35)
    obs_dates = pd.DatetimeIndex([pd.Timestamp(d) for d, _ in observations])
    obs_vals  = np.array([v for _, v in observations])
    epoch     = daily_index[0]
    x_obs     = np.array([(t - epoch).days for t in obs_dates], dtype=float)
    x_all     = np.array([(t - epoch).days for t in daily_index], dtype=float)
    return np.interp(x_all, x_obs, obs_vals)


# ──────────────────────────────────────────────────────────────────────────────
# Water usage computation
# ──────────────────────────────────────────────────────────────────────────────

def compute_daily_water_usage(et0_daily: np.ndarray, kc_daily: np.ndarray,
                               location: dict) -> np.ndarray:
    """
    Compute daily agricultural water usage (m³/day) for one zone.

      ET_crop [mm/day] = Kc × ET₀ [mm/day]
      Volume  [m³/day] = ET_crop × 10 × area_ha   (1 mm over 1 ha = 10 m³)

    Parameters
    ----------
    et0_daily  : ndarray  daily reference ET in mm/day
    kc_daily   : ndarray  daily crop coefficient (same length)
    location   : dict     must contain ``area_ha``

    Returns
    -------
    ndarray  daily water volume in m³/day
    """
    et_crop = np.maximum(kc_daily, 0.0) * np.maximum(et0_daily, 0.0)
    return et_crop * 10.0 * location["area_ha"]


# ──────────────────────────────────────────────────────────────────────────────
# CSV export
# ──────────────────────────────────────────────────────────────────────────────

def export_csv(results: list, output_dir: str = ".") -> None:
    """
    Write one CSV per location with columns date, et0_mm_day, kc, water_m3_day.
    Also writes a combined ``nile_water_usage_all.csv``.
    """
    import pandas as pd

    out = pathlib.Path(output_dir)
    all_frames = []

    for r in results:
        name = r["location"]["name"]
        df = pd.DataFrame({
            "date":         r["dates"],
            "et0_mm_day":   r["et0_daily"],
            "kc":           r["kc_daily"],
            "water_m3_day": r["water_m3_day"],
        })
        df["location"] = name
        slug = re.sub(r"\W+", "_", name.lower()).strip("_")
        path = out / f"nile_{slug}_water.csv"
        df[["date", "et0_mm_day", "kc", "water_m3_day"]].to_csv(path, index=False)
        all_frames.append(df)

    combined = pd.concat(all_frames, ignore_index=True)
    combined.to_csv(out / "nile_water_usage_all.csv", index=False)
    print(f"  CSV files written to {out.resolve()}/")


# ──────────────────────────────────────────────────────────────────────────────
# Plot
# ──────────────────────────────────────────────────────────────────────────────

def plot_water_usage(results: list, year_from: int, year_to: int,
                     output_path: str = "nile_water_usage.png") -> str:
    """
    Three-panel figure saved to *output_path*:

    Top    – 365-day rolling mean daily rate per zone (Mm³/day) + total
    Middle – Annual total per zone (Mm³/year), stacked bar
    Bottom – Cumulative total over the full period (Mm³), stacked area
    """
    import pandas as pd

    n_loc  = len(results)
    cmap   = plt.cm.tab20
    colors = [cmap(i / n_loc) for i in range(n_loc)]

    fig, axes = plt.subplots(
        3, 1, figsize=(18, 14), sharex=False,
        facecolor="#0d1117",
        gridspec_kw={"hspace": 0.28, "height_ratios": [1.3, 1.0, 1.0]},
    )
    fig.suptitle(
        f"Nile Basin — Daily Agricultural Water Usage  {year_from}–{year_to}",
        fontsize=14, fontweight="bold", color="white", y=0.98,
    )

    # ── Shared daily date axis ────────────────────────────────────────────────
    dates_pd = pd.DatetimeIndex(results[0]["dates"])

    # ── Panel 1: 365-day rolling mean of daily rate ───────────────────────────
    ax1 = axes[0]
    ax1.set_facecolor("#111827")
    total_daily = np.zeros(len(dates_pd))

    for i, r in enumerate(results):
        mm3 = pd.Series(r["water_m3_day"] / 1e6, index=dates_pd)
        smoothed = mm3.rolling(365, center=True, min_periods=30).mean()
        total_daily += mm3.values
        ax1.plot(dates_pd, smoothed, color=colors[i], linewidth=1.2,
                 label=r["location"]["name"], alpha=0.9)

    total_smooth = (pd.Series(total_daily, index=dates_pd)
                    .rolling(365, center=True, min_periods=30).mean())
    ax1.plot(dates_pd, total_smooth, color="white", linewidth=1.8,
             linestyle="--", label="Total", alpha=0.7)

    ax1.set_ylabel("Water usage (Mm³/day)\n365-day rolling mean", color="white")
    ax1.tick_params(colors="white")
    ax1.grid(True, alpha=0.12, color="white")
    ax1.legend(fontsize=7, ncol=5, facecolor="#1e2a38",
               labelcolor="white", edgecolor="#444", loc="upper left")
    for sp in ax1.spines.values():
        sp.set_edgecolor("#444")
    ax1.xaxis.set_major_locator(mdates.YearLocator(10))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax1.tick_params(axis="x", colors="white", labelsize=8)

    # ── Panel 2: annual totals — stacked bar ─────────────────────────────────
    ax2 = axes[1]
    ax2.set_facecolor("#111827")
    years     = np.arange(year_from, year_to + 1)
    bar_bot   = np.zeros(len(years))

    for i, r in enumerate(results):
        s = pd.Series(r["water_m3_day"], index=dates_pd)
        ann = np.array([s[s.index.year == y].sum() / 1e9 for y in years])  # Gm³/yr
        ax2.bar(years, ann, bottom=bar_bot, color=colors[i], alpha=0.75,
                width=0.85, label=r["location"]["name"])
        bar_bot += ann

    ax2.set_ylabel("Annual total (Gm³/year)", color="white")
    ax2.set_xlim(year_from - 1, year_to + 1)
    ax2.tick_params(colors="white")
    ax2.grid(True, alpha=0.12, color="white", axis="y")
    ax2.legend(fontsize=7, ncol=5, facecolor="#1e2a38",
               labelcolor="white", edgecolor="#444", loc="upper left")
    for sp in ax2.spines.values():
        sp.set_edgecolor("#444")
    ax2.xaxis.set_major_locator(plt.MultipleLocator(10))
    ax2.tick_params(axis="x", colors="white", labelsize=8)

    # ── Panel 3: cumulative total — stacked area ──────────────────────────────
    ax3 = axes[2]
    ax3.set_facecolor("#111827")
    stack_bot = np.zeros(len(dates_pd))

    for i, r in enumerate(results):
        cum = np.cumsum(r["water_m3_day"]) / 1e12  # → Tm³ (tera-m³)
        ax3.fill_between(dates_pd, stack_bot, stack_bot + cum,
                         alpha=0.55, color=colors[i], label=r["location"]["name"])
        ax3.plot(dates_pd, stack_bot + cum, color=colors[i], linewidth=0.5, alpha=0.5)
        stack_bot += cum

    final_total_gm3 = stack_bot[-1] * 1e3
    ax3.annotate(
        f"Cumulative total: {final_total_gm3:,.0f} Gm³",
        xy=(dates_pd[-1], stack_bot[-1]),
        xytext=(-200, -20), textcoords="offset points",
        fontsize=9, color="white",
        bbox=dict(boxstyle="round,pad=0.3", fc="#1e2a38", alpha=0.8),
    )
    ax3.set_ylabel("Cumulative water usage (Tm³)", color="white")
    ax3.set_xlabel("Year", color="white")
    ax3.tick_params(colors="white")
    ax3.grid(True, alpha=0.12, color="white")
    ax3.legend(fontsize=7, ncol=5, facecolor="#1e2a38",
               labelcolor="white", edgecolor="#444", loc="upper left")
    for sp in ax3.spines.values():
        sp.set_edgecolor("#444")
    ax3.xaxis.set_major_locator(mdates.YearLocator(10))
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax3.tick_params(axis="x", colors="white", labelsize=8)

    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    print(f"\nPlot saved → {output_path}")
    return output_path


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main(year_from: int = 1950, year_to: int = 2026,
         use_ndvi_overlay: bool = True) -> None:
    """
    Run the full estimation pipeline for all nile.yaml locations.

    Parameters
    ----------
    year_from         : int   first year of the time series (default 1950)
    year_to           : int   last  year of the time series (default 2026)
    use_ndvi_overlay  : bool  if True and ACCESS_TOKEN is set, replace the
                              seasonal Kc with NDVI-derived Kc for the
                              satellite era (≥ 2017)
    """
    import pandas as pd

    print(f"Nile Basin Agricultural Water Usage  {year_from}–{year_to}\n")
    print(f"  Locations loaded : {len(NILE_LOCATIONS)}")
    print(f"  ERA5 cache dir   : {ERA5_CACHE_DIR}")
    print(f"  Sentinel-2 NDVI  : {'enabled' if _SH_AVAILABLE else 'disabled (no ACCESS_TOKEN)'}\n")

    # 1. Build full daily date index
    daily_idx = pd.date_range(f"{year_from}-01-01", f"{year_to}-12-31", freq="D")

    # 2. Per-location pipeline
    results = []
    for loc in NILE_LOCATIONS:
        print(f"--- {loc['name']}  ({loc['lat']:.1f}N, {loc['lon']:.1f}E,"
              f"  {loc['area_ha']:,} ha) ---")

        # 2a. ERA5-Land monthly ET → daily ET₀
        try:
            monthly_et  = download_era5_monthly_et(loc, year_from, year_to)
            et0_series  = era5_monthly_to_daily(monthly_et, year_from, year_to)
            et0_daily   = et0_series.values
            print(f"  ERA5 ET₀  mean={et0_daily.mean():.2f} mm/day  "
                  f"range=[{et0_daily.min():.1f}, {et0_daily.max():.1f}]")
        except Exception as exc:
            print(f"  [ERROR] ERA5 download failed: {exc}")
            print("  Falling back to FAO-56 monthly climatology.")
            # Fallback: FAO-56 climatology (original behaviour)
            _fao = [3.5, 4.2, 5.5, 6.8, 8.1, 9.0, 9.2, 8.8, 7.5, 6.0, 4.2, 3.2]
            et0_daily = np.array([_fao[t.month - 1] for t in daily_idx], dtype=float)

        # 2b. Crop coefficient
        kc_daily = seasonal_kc(daily_idx)

        # 2c. Optional NDVI overlay for satellite era (2017–year_to)
        if use_ndvi_overlay and _SH_AVAILABLE:
            sat_start = max(year_from, 2017)
            sat_mask  = (daily_idx.year >= sat_start)
            d_from    = f"{sat_start}-01-01"
            d_to      = f"{year_to}-12-31"
            obs       = get_ndvi_timeseries(loc, d_from, d_to, interval_days=5)
            if obs:
                sat_idx  = daily_idx[sat_mask]
                ndvi_sat = _ndvi_obs_to_daily(obs, sat_idx)
                kc_daily[sat_mask] = ndvi_kc(ndvi_sat)
                print(f"  NDVI overlay: {len(obs)} obs  "
                      f"mean NDVI={np.mean([v for _, v in obs]):.3f}")

        # 2d. Daily water volume
        water_m3_day = compute_daily_water_usage(et0_daily, kc_daily, loc)
        annual_avg   = water_m3_day.sum() / ((year_to - year_from + 1) * 1e6)
        print(f"  Annual avg water usage: {annual_avg:,.1f} Mm³/yr\n")

        results.append({
            "location":    loc,
            "dates":       daily_idx,
            "et0_daily":   et0_daily,
            "kc_daily":    kc_daily,
            "water_m3_day": water_m3_day,
        })

    # 3. Optional CLMS reference products (informational)
    if _SH_AVAILABLE:
        print("=== CLMS Actual ET reference products (last year) ===")
        try:
            eta = search_clms_eta_products(f"{year_to}-01-01", f"{year_to}-12-31", limit=4)
            for p in eta:
                print(f"  * {p['Name']}  {p['ContentDate']['Start'][:10]}")
            if not eta:
                print("  (none found)")
        except Exception as exc:
            print(f"  [WARN] {exc}")
        print()

    # 4. Export CSV
    print("Exporting CSV files …")
    export_csv(results)

    # 5. Plot
    print("Generating plot …")
    plot_water_usage(results, year_from, year_to)

    # 6. Summary table
    sep = "─" * 68
    print(f"\n{sep}")
    print(f"{'Zone':<14} {'Area (ha)':>10} {'Mean ET₀':>10} {'Avg Kc':>8} "
          f"{'Annual avg (Mm³)':>18}")
    print(sep)
    for r in results:
        loc     = r["location"]
        mean_et = float(r["et0_daily"].mean())
        mean_kc = float(r["kc_daily"].mean())
        ann_mm3 = r["water_m3_day"].sum() / ((year_to - year_from + 1) * 1e6)
        print(f"{loc['name']:<14} {loc['area_ha']:>10,} {mean_et:>9.2f} "
              f"{mean_kc:>7.3f} {ann_mm3:>18,.1f}")
    total = sum(r["water_m3_day"].sum() for r in results)
    total_ann = total / ((year_to - year_from + 1) * 1e6)
    print(sep)
    print(f"{'TOTAL':<14} {'':>10} {'':>10} {'':>8} {total_ann:>18,.1f} Mm³/yr")


if __name__ == "__main__":
    main(year_from=1950, year_to=2026)
