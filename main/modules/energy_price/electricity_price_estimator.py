#!/usr/bin/env python3
"""
electricity_price_estimator.py

Estimates daily mean electricity prices (EUR/kWh) for every Nile-basin node
defined in nile.yaml, from 1950-01-01 to today at daily resolution.

────────────────────────────────────────────────────────────────────────────
CLEAR-SKY DATA  (Copernicus CDS  –  ERA5)
────────────────────────────────────────────────────────────────────────────
  Sunshine duration (seconds/hour → hours/day) is fetched via the official
  Copernicus Climate Data Store (CDS) API using the `cdsapi` library:

      Hersbach et al. (2023). ERA5 hourly data on single levels from 1940
      to present. ECMWF. https://doi.org/10.24381/cds.adbb2d47

  To enable downloads you need a free CDS account and a ~/.cdsapirc file:
      https://cds.climate.copernicus.eu/api-how-to

  Each node's bounding box is derived from its catchment area (nile.yaml).
  All ERA5 grid cells inside the box are spatially averaged for that day.
  ERA5 data covers ERA5_START…ERA5_END (~9 years) and is then tiled
  cyclically to fill 1950→today.

  Cached per-node NetCDF files are stored in CACHE_DIR.  Use --download to
  force a fresh download.  If CDS credentials are absent the script falls
  back to a latitude-aware astronomical model.

────────────────────────────────────────────────────────────────────────────
GENERATION SOURCE TYPES & PRICE MODELS
────────────────────────────────────────────────────────────────────────────
  solar   – price is a daily-weighted blend of a cheap solar-production rate
            (sunshine hours from ERA5) and an expensive night/fallback rate.
  hydro   – cosine seasonal model following the Nile wet/dry flow cycle.
  gas     – flat pipeline-gas baseline with a small seasonal demand swing.
  diesel  – high flat rate for isolated off-grid diesel generation (South
            Sudan); small seasonal swing from fuel-import seasonality.

  Each region is assigned (primary, secondary) sources.  The final price is
  a linear blend (PRIMARY_FRACTION primary, 1−PRIMARY_FRACTION secondary).
  Raw model prices are normalised so the long-run mean equals the country-
  level retail price, providing accurate absolute levels while the model
  supplies the seasonal shape.

────────────────────────────────────────────────────────────────────────────
REGIONAL BASE PRICES  (EUR/kWh, 2025, converted at 0.93 EUR/USD)
────────────────────────────────────────────────────────────────────────────
  Uganda  (victoria)      0.165 USD → GlobalPetrolPrices.com Sep-2025
  S.Sudan (southwest)     0.350 USD → World Bank Africa Energy 2022
                                       (diesel-based isolated grid)
  Sudan   (karthoum …)    0.044 USD → GlobalPetrolPrices.com Sep-2025
  Ethiopia(gerd …)        0.006 USD → GlobalPetrolPrices.com Sep-2025
  Egypt   (aswand, cairo) 0.021 USD → GlobalPetrolPrices.com Sep-2025

Usage:
  python3 electricity_price_estimator.py            # cached ERA5 or fallback
  python3 electricity_price_estimator.py --download  # (re-)fetch from CDS
  python3 electricity_price_estimator.py --no-plot
"""

import argparse
import csv
import json
import math
import os
import time
from datetime import date, timedelta
from pathlib import Path

import yaml

# ============================================================
# SETTINGS  —  all model knobs live here
# ============================================================

# --- Simulation window (inclusive) --------------------------
START_DATE = date(1950, 1, 1)
END_DATE   = date.today()

# --- ERA5 / Copernicus CDS window ---------------------------
# CDS ERA5 covers 1940 to present.  We download ~9 years and tile the rest.
ERA5_START = date(2015, 1, 1)
ERA5_END   = date(2024, 12, 31)

# --- File paths ---------------------------------------------
YAML_FILE  = "nile.yaml"
OUTPUT_DIR = "price_csv"
CACHE_DIR  = "era5_cache"      # per-node NetCDF / JSON caches

# --- Spatial sampling ---------------------------------------
# The bounding box of each node (from catchment area) is downloaded as a
# single ERA5 tile.  BOX_PADDING_DEG adds extra margin on each side.
BOX_PADDING_DEG   = 1.0    # degrees added to the catchment radius
ERA5_GRID_DEG     = 0.5    # ERA5 download resolution (0.25 or 0.5 degrees)

# --- Solar price model --------------------------------------
SOLAR_DAYTIME_PRICE   = 0.020   # EUR/kWh – marginal cost during solar hours
SOLAR_NIGHTTIME_PRICE = 0.090   # EUR/kWh – gas / import fallback at night

# --- Hydro price model (Nile seasonal cycle) ----------------
HYDRO_WET_PRICE    = 0.030   # EUR/kWh – wet season / full reservoir
HYDRO_DRY_PRICE    = 0.080   # EUR/kWh – dry season / low reservoir
HYDRO_PEAK_DOY     = 213     # day-of-year of peak Nile flow (≈ 1 Aug)
HYDRO_SEASONALITY  = 0.85    # seasonal swing amplitude (1.0 = full range)

# --- Gas / pipeline price model -----------------------------
GAS_BASE_PRICE        = 0.075   # EUR/kWh – flat pipeline-gas baseline
GAS_SEASONAL_AMP      = 0.010   # EUR/kWh – ± demand-driven swing
GAS_SEASONAL_PEAK_DOY = 15      # peak-demand day-of-year (≈ 15 Jan)

# --- Diesel / isolated-grid price model ---------------------
# South Sudan: no national grid, electricity comes from diesel generators.
# ~10× more expensive than pipeline gas; small import-cost seasonal swing.
DIESEL_BASE_PRICE        = 0.320   # EUR/kWh – isolated diesel generation
DIESEL_SEASONAL_AMP      = 0.015   # EUR/kWh – fuel-import cost swing
DIESEL_SEASONAL_PEAK_DOY = 30      # peak-cost day-of-year (dry-season road access)

# --- Regional energy mix ------------------------------------
# (primary_source, secondary_source)
# Sources: 'solar', 'hydro', 'gas', 'diesel'
# Energy-mix fractions based on EIA 2022 national data.
REGION_ENERGY: dict[str, tuple[str, str]] = {
    "victoria":  ("hydro",  "gas"),     # Uganda – 96 % hydro (EIA 2022)
    "southwest": ("diesel", "solar"),   # South Sudan – off-grid diesel (~no dam)
    "karthoum":  ("hydro",  "gas"),     # Sudan – 62 % hydro / 38 % fossil
    "merowe":    ("hydro",  "solar"),   # Merowe Dam + Nubian desert solar
    "aswand":    ("solar",  "hydro"),   # Aswan – extreme sunshine + High Dam
    "cairo":     ("gas",    "solar"),   # Egypt – 89 % fossil fuels (EIA 2022)
    "singa":     ("hydro",  "gas"),     # Blue Nile run-of-river (Sudan)
    "roseires":  ("hydro",  "gas"),     # Roseires Dam (Sudan/Ethiopia border)
    "gerd":      ("hydro",  "gas"),     # GERD – 96 % hydro (Ethiopia)
    "tana":      ("hydro",  "gas"),     # Lake Tana / Upper Abay (Ethiopia)
    "kashm":     ("hydro",  "solar"),   # Atbara / Kashm el-Girba (Sudan)
    "tsengh":    ("hydro",  "solar"),   # Tekeze tributary (Ethiopia/Sudan)
    "ozentari":  ("hydro",  "gas"),     # Headwater tributary (Ethiopia)
}

PRIMARY_FRACTION = 0.75   # fraction of blended price from primary source

# --- Regional base prices (EUR/kWh, 2025, 0.93 USD→EUR) -----
USD_TO_EUR = 0.93
REGION_BASE_PRICES: dict[str, float] = {
    "victoria":  round(0.165 * USD_TO_EUR, 4),   # Uganda
    "southwest": round(0.350 * USD_TO_EUR, 4),   # South Sudan (diesel)
    "karthoum":  round(0.044 * USD_TO_EUR, 4),   # Sudan
    "merowe":    round(0.044 * USD_TO_EUR, 4),   # Sudan
    "singa":     round(0.044 * USD_TO_EUR, 4),   # Sudan
    "kashm":     round(0.044 * USD_TO_EUR, 4),   # Sudan
    "tsengh":    round(0.044 * USD_TO_EUR, 4),   # Sudan
    "gerd":      round(0.006 * USD_TO_EUR, 4),   # Ethiopia
    "roseires":  round(0.006 * USD_TO_EUR, 4),   # Ethiopia
    "tana":      round(0.006 * USD_TO_EUR, 4),   # Ethiopia
    "ozentari":  round(0.006 * USD_TO_EUR, 4),   # Ethiopia
    "aswand":    round(0.021 * USD_TO_EUR, 4),   # Egypt
    "cairo":     round(0.021 * USD_TO_EUR, 4),   # Egypt
}

# ============================================================
# COPERNICUS CDS  (ERA5)  —  DOWNLOAD
# ============================================================

def _bounding_box(lat: float, lon: float, area_km2: float) -> tuple[float, float, float, float]:
    """
    Return (lat_min, lat_max, lon_min, lon_max) for a node's catchment.
    Half-width = sqrt(area / π) / 111 km-per-degree + BOX_PADDING_DEG.
    """
    half_deg = math.sqrt(area_km2 / math.pi) / 111.0 + BOX_PADDING_DEG
    return lat - half_deg, lat + half_deg, lon - half_deg, lon + half_deg


def _has_cds_credentials() -> bool:
    """Return True if ~/.cdsapirc exists and cdsapi is importable."""
    try:
        import cdsapi  # noqa: F401
    except ImportError:
        return False
    return Path.home().joinpath(".cdsapirc").exists()


def _download_era5_netcdf(node_id: str, lat_min: float, lat_max: float,
                           lon_min: float, lon_max: float,
                           nc_path: Path) -> None:
    """
    Download ERA5 sunshine_duration for the given bounding box and the full
    ERA5_START…ERA5_END window to a NetCDF file via the Copernicus CDS API.

    ERA5 variable:
      sunshine_duration  [s]  – seconds of sunshine per hour, hourly.
      Summed to daily totals and converted to hours in the caller.

    CDS dataset: reanalysis-era5-single-levels
    """
    import cdsapi

    years  = [str(y) for y in range(ERA5_START.year, ERA5_END.year + 1)]
    months = [f"{m:02d}" for m in range(1, 13)]
    days   = [f"{d:02d}" for d in range(1, 32)]
    hours  = [f"{h:02d}:00" for h in range(24)]

    # CDS area format: [North, West, South, East]
    area   = [round(lat_max, 1), round(lon_min, 1),
               round(lat_min, 1), round(lon_max, 1)]

    print(f"    CDS request: area={area}  years={years[0]}–{years[-1]} …")
    c = cdsapi.Client(quiet=True)
    c.retrieve(
        "reanalysis-era5-single-levels",
        {
            "product_type": "reanalysis",
            "variable":     "sunshine_duration",
            "year":         years,
            "month":        months,
            "day":          days,
            "time":         hours,
            "area":         area,
            "format":       "netcdf",
            "grid":         [ERA5_GRID_DEG, ERA5_GRID_DEG],
        },
        str(nc_path),
    )


def _nc_to_daily_mean(nc_path: Path) -> dict[str, float]:
    """
    Load a NetCDF file containing ERA5 sunshine_duration (seconds/hour),
    sum to daily totals (hours/day), spatial-average over all grid cells,
    and return {ISO-date-string: float}.
    """
    import xarray as xr

    ds    = xr.open_dataset(nc_path)
    sd    = ds["sunshine_duration"]   # seconds / hour, dims (time, lat, lon)
    daily = sd.resample(time="1D").sum() / 3600.0   # → hours / day
    spat  = daily.mean(dim=[d for d in daily.dims if d != "time"])
    return {
        str(t.values)[:10]: float(v.values)
        for t, v in zip(spat.time, spat)
    }


def fetch_sunshine_series(
    node_id: str,
    lat: float,
    lon: float,
    area_km2: float,
    force: bool = False,
) -> dict[str, float]:
    """
    Return the spatial-mean daily sunshine series (hours/day) for a node,
    as {ISO-date-string: hours}.

    Download strategy:
    1. Load cached JSON if present (and not --download).
    2. Download ERA5 via Copernicus CDS API → cache as JSON.
    3. If CDS credentials missing → raise RuntimeError (caller uses fallback).
    """
    json_cache = Path(CACHE_DIR) / f"{node_id}_sunshine.json"
    nc_cache   = Path(CACHE_DIR) / f"{node_id}_era5_sunshine.nc"

    if not force and json_cache.exists():
        print(f"  [cache]    {node_id:12s}  ← {json_cache}")
        with open(json_cache) as fh:
            return json.load(fh)

    if not _has_cds_credentials():
        raise RuntimeError(
            "Copernicus CDS credentials not found (~/.cdsapirc).  "
            "Register at https://cds.climate.copernicus.eu and create the key file."
        )

    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
    lat_min, lat_max, lon_min, lon_max = _bounding_box(lat, lon, area_km2)
    print(
        f"  [CDS dl]   {node_id:12s}  "
        f"bbox=({lat_min:.1f},{lat_max:.1f},{lon_min:.1f},{lon_max:.1f})"
    )

    if not nc_cache.exists() or force:
        _download_era5_netcdf(node_id, lat_min, lat_max, lon_min, lon_max, nc_cache)
    else:
        print(f"    (reusing existing NetCDF: {nc_cache})")

    series = _nc_to_daily_mean(nc_cache)
    with open(json_cache, "w") as fh:
        json.dump(series, fh)
    print(f"    → {len(series)} daily values cached at {json_cache}")
    return series


# ============================================================
# TILING  —  repeat ERA5 window to fill 1950 → today
# ============================================================

def tile_sunshine(
    era5_series: dict[str, float],
) -> dict[date, float]:
    """
    Tile era5_series (ERA5_START…ERA5_END) cyclically to fill
    START_DATE…END_DATE.  Each target date maps to
      ERA5_START + ((d − ERA5_START) mod span).
    """
    span   = (ERA5_END - ERA5_START).days + 1
    result: dict[date, float] = {}
    d = START_DATE
    while d <= END_DATE:
        offset  = (d - ERA5_START).days % span
        src_key = (ERA5_START + timedelta(days=offset)).isoformat()
        result[d] = era5_series.get(src_key, float("nan"))
        d += timedelta(days=1)
    return result


# ============================================================
# ASTRONOMICAL FALLBACK (no CDS credentials)
# ============================================================

def _astronomical_sunshine(lat_deg: float, doy: int) -> float:
    """
    Approximate clear-sky sunshine hours from latitude and day-of-year.
    Uses the astronomical day-length formula with an 80 % clear-sky fraction,
    which is a reasonable estimate for the arid/semi-arid Nile basin.
    """
    lat   = math.radians(lat_deg)
    decl  = math.radians(23.45 * math.sin(math.radians(360 / 365 * (284 + doy))))
    cos_H = max(-1.0, min(1.0, -math.tan(lat) * math.tan(decl)))
    return 2.0 * math.acos(cos_H) * (12.0 / math.pi) * 0.80


# ============================================================
# PRICE MODELS  (raw, before regional normalisation)
# ============================================================

def _solar_price(sunshine_hours: float) -> float:
    """Cheap during solar hours, fallback rate otherwise."""
    f_sun = max(0.0, min(sunshine_hours / 24.0, 1.0))
    return f_sun * SOLAR_DAYTIME_PRICE + (1.0 - f_sun) * SOLAR_NIGHTTIME_PRICE


def _hydro_price(doy: int) -> float:
    """Nile wet/dry seasonal cosine. Cheap at peak flow (≈ 1 Aug)."""
    angle    = 2.0 * math.pi * (doy - HYDRO_PEAK_DOY) / 365.0
    mid      = (HYDRO_WET_PRICE + HYDRO_DRY_PRICE) / 2.0
    half_amp = (HYDRO_DRY_PRICE - HYDRO_WET_PRICE) / 2.0
    return mid - half_amp * HYDRO_SEASONALITY * math.cos(angle)


def _gas_price(doy: int) -> float:
    """Near-constant pipeline-gas price with a small demand-driven swing."""
    angle = 2.0 * math.pi * (doy - GAS_SEASONAL_PEAK_DOY) / 365.0
    return GAS_BASE_PRICE + GAS_SEASONAL_AMP * math.cos(angle)


def _diesel_price(doy: int) -> float:
    """
    High flat rate for off-grid diesel generation (South Sudan).
    Small seasonal swing reflects fuel-import cost variation.
    """
    angle = 2.0 * math.pi * (doy - DIESEL_SEASONAL_PEAK_DOY) / 365.0
    return DIESEL_BASE_PRICE + DIESEL_SEASONAL_AMP * math.cos(angle)


def _source_price(source: str, sunshine_h: float, doy: int) -> float:
    if source == "solar":   return _solar_price(sunshine_h)
    if source == "hydro":   return _hydro_price(doy)
    if source == "gas":     return _gas_price(doy)
    if source == "diesel":  return _diesel_price(doy)
    raise ValueError(f"Unknown energy source '{source}'")


def _raw_price(node_id: str, sunshine_h: float, doy: int) -> float:
    primary, secondary = REGION_ENERGY[node_id]
    p1 = _source_price(primary,   sunshine_h, doy)
    p2 = _source_price(secondary, sunshine_h, doy)
    return PRIMARY_FRACTION * p1 + (1.0 - PRIMARY_FRACTION) * p2


# ============================================================
# CSV GENERATION
# ============================================================

def generate_csvs(
    nodes: list[dict],
    sunshine_tiled: dict[str, dict[date, float]],
) -> dict[str, list[tuple[date, float]]]:
    """
    Write one CSV per node (START_DATE … END_DATE).

    Raw model prices are normalised so the series mean equals
    REGION_BASE_PRICES[node_id], anchoring absolute levels to 2025 data.

    Returns {node_id: [(date, price), …]}.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_dates: list[date] = []
    d = START_DATE
    while d <= END_DATE:
        all_dates.append(d)
        d += timedelta(days=1)

    results: dict[str, list[tuple[date, float]]] = {}

    for node in nodes:
        node_id = node["id"]
        if node_id not in REGION_ENERGY:
            print(f"  [skip] '{node_id}' – no REGION_ENERGY entry")
            continue

        sunshine_map = sunshine_tiled.get(node_id, {})
        lat          = node["latitude"]

        raw_series: list[tuple[date, float]] = []
        for day in all_dates:
            doy = day.timetuple().tm_yday
            sh  = sunshine_map.get(day)
            if sh is None or math.isnan(sh):
                sh = _astronomical_sunshine(lat, doy)
            raw_series.append((day, _raw_price(node_id, sh, doy)))

        base_price = REGION_BASE_PRICES.get(node_id, 0.050)
        valid_raw  = [p for _, p in raw_series if not math.isnan(p)]
        raw_mean   = sum(valid_raw) / len(valid_raw) if valid_raw else 1.0
        scale      = base_price / raw_mean

        series = [(day, p * scale) for day, p in raw_series]

        csv_path = os.path.join(OUTPUT_DIR, f"{node_id}.csv")
        with open(csv_path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["date", "price_eur_kwh"])
            for day, price in series:
                if math.isnan(price):
                    writer.writerow([day.isoformat(), ""])
                else:
                    writer.writerow([day.isoformat(), f"{price:.6f}"])

        primary_src = REGION_ENERGY[node_id][0]
        print(
            f"  {node_id:12s}  [{primary_src:6s}]  "
            f"base={base_price:.4f}  "
            f"min={min(p for _, p in series):.4f}  "
            f"max={max(p for _, p in series):.4f}  EUR/kWh"
        )
        results[node_id] = series

    return results


# ============================================================
# PLOT — price time series
# ============================================================

# All 4 source groups with their display properties
_SOURCE_ORDER  = ["hydro", "solar", "gas", "diesel"]
_SOURCE_LABELS = {
    "hydro":  "Hydro-dominant",
    "solar":  "Solar-dominant",
    "gas":    "Gas / Pipeline",
    "diesel": "Diesel / Off-grid",
}
# Distinct colour palettes, one per source group
_SOURCE_PALETTES = {
    "hydro":  ["#1f77b4", "#17becf", "#2ca02c", "#9467bd",
               "#8c564b", "#e377c2", "#bcbd22", "#d62728", "#aec7e8"],
    "solar":  ["#ff7f0e", "#ffbb78", "#d62728", "#f7b6d2"],
    "gas":    ["#2ca02c", "#98df8a", "#c5b0d5", "#7f7f7f"],
    "diesel": ["#8c564b", "#c49c94"],
}
_LINE_STYLES = ["-", "--", "-.", ":", (0, (3, 1, 1, 1))]


def plot_prices(
    results: dict[str, list[tuple[date, float]]],
    output_file: str | None = "electricity_prices.png",
) -> None:
    """
    Four-panel figure (one per source group) showing daily electricity prices.
    Each node gets a unique colour + line style so curves are distinguishable.
    A zoomed seasonal inset (last 2 ERA5 years) is added to each panel.

    Parameters
    ----------
    results     : dict returned by generate_csvs()
    output_file : save path; None → interactive display
    """
    try:
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed – skipping  (pip install matplotlib)")
        return

    # Group nodes by primary source
    by_source: dict[str, list[str]] = {s: [] for s in _SOURCE_ORDER}
    for nid in sorted(results):
        by_source[REGION_ENERGY[nid][0]].append(nid)

    # Drop empty panels
    active = [s for s in _SOURCE_ORDER if by_source[s]]
    n_panels = len(active)

    fig, axes = plt.subplots(
        n_panels, 1, figsize=(18, 4 * n_panels),
        sharex=True, gridspec_kw={"hspace": 0.45},
    )
    if n_panels == 1:
        axes = [axes]

    zoom_start = date(ERA5_END.year - 1, 1, 1)
    zoom_end   = ERA5_END

    for ax, source in zip(axes, active):
        node_ids = by_source[source]
        palette  = _SOURCE_PALETTES[source]
        for i, nid in enumerate(node_ids):
            series = results[nid]
            xs = [r[0] for r in series]
            ys = [r[1] for r in series]
            colour = palette[i % len(palette)]
            ls     = _LINE_STYLES[i % len(_LINE_STYLES)]
            ax.plot(xs, ys, label=nid, linewidth=0.7, alpha=0.85,
                    color=colour, linestyle=ls)

        ax.set_title(
            f"{_SOURCE_LABELS[source]} regions",
            fontsize=10, fontweight="bold",
        )
        ax.set_ylabel("EUR / kWh", fontsize=9)
        ax.legend(fontsize=8, ncol=4, loc="upper left",
                  framealpha=0.8, borderpad=0.4)
        ax.grid(True, alpha=0.20)
        ax.xaxis.set_major_locator(mdates.YearLocator(10))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

        # Seasonal inset
        ax_in = ax.inset_axes([0.70, 0.50, 0.28, 0.44])
        for i, nid in enumerate(node_ids):
            series = results[nid]
            xs_z = [r[0] for r in series if zoom_start <= r[0] <= zoom_end]
            ys_z = [r[1] for r in series if zoom_start <= r[0] <= zoom_end]
            colour = _SOURCE_PALETTES[source][i % len(_SOURCE_PALETTES[source])]
            ls     = _LINE_STYLES[i % len(_LINE_STYLES)]
            ax_in.plot(xs_z, ys_z, linewidth=1.0, alpha=0.85,
                       color=colour, linestyle=ls, label=nid)
        ax_in.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
        ax_in.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
        ax_in.tick_params(labelsize=6)
        ax_in.set_title(f"{zoom_start.year}–{zoom_end.year}", fontsize=7, pad=2)
        ax_in.grid(True, alpha=0.20)

    axes[-1].set_xlabel("Year", fontsize=9)
    fig.suptitle(
        f"Estimated daily electricity prices – Nile basin nodes  |  "
        f"{START_DATE} → {END_DATE}\n"
        f"ERA5 clear-sky data (Copernicus CDS): {ERA5_START} → {ERA5_END}, "
        f"tiled cyclically",
        fontsize=10,
    )

    if output_file:
        fig.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Plot saved → {output_file}")
    else:
        plt.show()
    plt.close(fig)


# ============================================================
# METHOD PLOT  —  methodology diagram
# ============================================================

def plot_method(output_file: str | None = "method.png") -> None:
    """
    Produce a methodology flowchart showing how inputs flow through the
    model to produce the output CSVs and plots.
    """
    try:
        import matplotlib.patches as mpatches
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch
    except ImportError:
        print("matplotlib not installed – skipping method plot")
        return

    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis("off")

    def box(x, y, w, h, label, sublabel="", color="#d0e8f8", fontsize=9):
        rect = mpatches.FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.12",
            facecolor=color, edgecolor="#444", linewidth=1.2,
        )
        ax.add_patch(rect)
        ax.text(x, y + (0.15 if sublabel else 0), label,
                ha="center", va="center", fontsize=fontsize, fontweight="bold")
        if sublabel:
            ax.text(x, y - 0.28, sublabel,
                    ha="center", va="center", fontsize=7, color="#444",
                    style="italic")

    def arrow(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color="#333",
                                   lw=1.4, mutation_scale=14))

    def label_arrow(x, y, text):
        ax.text(x, y, text, ha="center", va="center",
                fontsize=7, color="#555",
                bbox=dict(fc="white", ec="none", pad=1.5))

    # ── Input layer ───────────────────────────────────────────────────────
    box(2.5, 8.0, 3.2, 0.9, "nile.yaml",
        "node id, lat/lon, area (km²)", color="#fde8b0")
    box(8.5, 8.0, 3.8, 0.9, "Copernicus CDS  (ERA5)",
        "reanalysis-era5-single-levels\nsunshine_duration  [s/hr]  2015–2024",
        color="#c8e6c9")
    box(11.5, 8.0, 2.2, 0.9, "Real prices",
        "GlobalPetrolPrices 2025\nWorld Bank Africa 2022",
        color="#f8d7da")

    # ── Bounding box ──────────────────────────────────────────────────────
    box(5.2, 6.4, 3.8, 0.9,
        "Catchment bounding box",
        "radius = √(area/π)/111° + padding",
        color="#d0e8f8")
    arrow(2.5, 7.55, 4.0, 6.85)
    arrow(8.5, 7.55, 6.4, 6.85)

    # ── ERA5 download / spatial average ───────────────────────────────────
    box(8.5, 6.4, 3.8, 0.9,
        "ERA5 spatial average",
        "all grid cells in bbox → mean\nhourly → daily Σ / 3600  [hr/day]",
        color="#c8e6c9")
    arrow(6.1, 6.4, 6.6, 6.4)
    label_arrow(6.35, 6.65, "bbox")

    # ── Tiling ────────────────────────────────────────────────────────────
    box(8.5, 4.9, 3.8, 0.9,
        "Cyclic tiling  1950 → today",
        "(d − ERA5_start) mod ERA5_span",
        color="#c8e6c9")
    arrow(8.5, 5.95, 8.5, 5.35)

    # ── Price models ──────────────────────────────────────────────────────
    box(2.0, 4.9, 2.4, 0.8, "Solar model",
        "f_sun × daytime_price\n+ (1−f_sun) × night_price", color="#fff3cd")
    box(4.8, 4.9, 2.4, 0.8, "Hydro model",
        "cosine(Nile wet/dry)\nTpeak ≈ 1 Aug", color="#cfe2ff")
    box(7.3, 3.5, 2.2, 0.8, "Gas model",
        "flat pipeline rate\n± demand swing", color="#e2e3e5")
    box(9.8, 3.5, 2.2, 0.8, "Diesel model",
        "high off-grid rate\n(S. Sudan only)", color="#f8d7da")

    # Arrows from ERA5 → solar, ERA5 → hydro (sunshine to solar)
    arrow(6.6, 4.9, 5.5, 5.27)
    label_arrow(6.0, 5.15, "sunshine hrs")
    arrow(2.0, 5.3, 2.0, 5.8)   # solar upward placeholder (not needed)
    # Actually connect ERA5 to solar only
    arrow(6.6, 4.9, 3.2, 5.12)
    label_arrow(4.9, 5.25, "sunshine hrs")

    # ── Source blend ──────────────────────────────────────────────────────
    box(5.2, 2.9, 4.0, 0.9,
        "Source blend",
        "price = 0.75 × primary + 0.25 × secondary\n"
        "(REGION_ENERGY per node)",
        color="#e8d5f5")
    arrow(2.0, 4.5, 3.5, 3.35)
    arrow(4.8, 4.5, 5.0, 3.35)
    arrow(7.3, 3.1, 6.5, 3.25)
    arrow(9.8, 3.1, 7.2, 3.25)

    # ── Normalisation ─────────────────────────────────────────────────────
    box(5.2, 1.7, 4.0, 0.9,
        "Regional normalisation",
        "scale = base_price / raw_mean\n"
        "anchors long-run mean to 2025 retail price",
        color="#e8d5f5")
    arrow(5.2, 2.45, 5.2, 2.15)
    arrow(11.5, 7.55, 8.5, 2.1)   # real prices → normalisation

    # ── Outputs ───────────────────────────────────────────────────────────
    box(2.8, 0.6, 3.0, 0.8, "price_csv/<node>.csv",
        "date, price_eur_kwh\n1950-01-01 → today",
        color="#fde8b0")
    box(7.6, 0.6, 3.0, 0.8, "electricity_prices.png",
        "4-panel time-series plot\n+ seasonal inset",
        color="#fde8b0")
    arrow(4.0, 1.25, 3.4, 1.0)
    arrow(6.4, 1.25, 7.0, 1.0)

    fig.suptitle(
        "Electricity Price Estimator — Methodology Overview",
        fontsize=13, fontweight="bold", y=0.97,
    )

    if output_file:
        fig.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Method plot saved → {output_file}")
    else:
        plt.show()
    plt.close(fig)


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Estimate Nile-basin electricity prices using ERA5 clear-sky data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--download", dest="force_download", action="store_true",
        help="Force re-download of ERA5 data from Copernicus CDS.",
    )
    parser.add_argument(
        "--no-plot", action="store_true",
        help="Skip price and method plot generation.",
    )
    args = parser.parse_args()

    with open(YAML_FILE) as fh:
        nodes: list[dict] = yaml.safe_load(fh)["nodes"]

    print(f"Loaded {len(nodes)} nodes from '{YAML_FILE}'")
    print(
        f"Simulation : {START_DATE} → {END_DATE}  "
        f"({(END_DATE - START_DATE).days + 1:,} days)\n"
        f"ERA5 window: {ERA5_START} → {ERA5_END}  "
        f"({(ERA5_END - ERA5_START).days + 1} days, tiled)\n"
    )
    if not _has_cds_credentials():
        print(
            "  ⚠  No Copernicus CDS credentials found (~/.cdsapirc).\n"
            "     ERA5 download disabled — using astronomical clear-sky fallback.\n"
            "     Register free at https://cds.climate.copernicus.eu\n"
        )

    # ── 1. Fetch ERA5 sunshine ────────────────────────────────
    print("── ERA5 sunshine_duration (Copernicus CDS) ──")
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)

    sunshine_tiled: dict[str, dict[date, float]] = {}
    for node in nodes:
        nid = node["id"]
        if nid not in REGION_ENERGY:
            continue
        try:
            era5_series = fetch_sunshine_series(
                nid, node["latitude"], node["longitude"],
                node["area"], force=args.force_download,
            )
            sunshine_tiled[nid] = tile_sunshine(era5_series)
        except RuntimeError as exc:
            print(f"  [fallback] {nid}: {exc}")
            sunshine_tiled[nid] = {}

    # ── 2. Generate CSVs ──────────────────────────────────────
    print(f"\n── Generating price CSVs → '{OUTPUT_DIR}/' ──")
    results = generate_csvs(nodes, sunshine_tiled)
    print(f"\n{len(results)} CSV files written.")

    # ── 3. Plots ──────────────────────────────────────────────
    if not args.no_plot:
        print("\n── Generating price plot ──")
        plot_prices(results)
        print("\n── Generating method diagram ──")
        plot_method()


if __name__ == "__main__":
    main()
