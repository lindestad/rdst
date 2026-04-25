"""
Nile Basin Agricultural Area — Daily Time Series, 2015–2019
============================================================
Estimates the agricultural (cropland) area for each zone defined in nile.yaml
using the Copernicus Global Land Service Land Cover 100 m Collection 3
(CGLS-LC100 v3, epochs 2015–2019).

Source
------
  Buchhorn et al. (2020). Copernicus Global Land Service: Land Cover 100m:
  Collection 3 Epochs 2015–2019.
  https://land.copernicus.eu/en/products/global-dynamic-land-cover/
    copernicus-global-land-service-land-cover-100m-collection-3-epoch-2015-2019-globe

  Five annual Crops-CoverFraction GeoTIFFs (PROBA-V, EPSG:4326, ~100 m,
  DEFLATE-compressed tiled GeoTIFF) hosted on Zenodo:
    2015 base  → https://zenodo.org/records/3939038
    2016 conso → https://zenodo.org/records/3518026
    2017 conso → https://zenodo.org/records/3518036
    2018 conso → https://zenodo.org/records/3518038
    2019 nrt   → https://zenodo.org/records/3939050

Method
------
  Each GeoTIFF pixel encodes the fractional cropland cover in percent (0–100).
  For every zone, the script extracts a bounding box centred on the node
  coordinates and computes:

      cropland_area_ha = Σ [ (pixel_fraction / 100) × pixel_area_ha(lat) ]

  where

      pixel_area_ha(lat) = cos(lat) × R_earth² × Δλ × Δφ × 1e-4   [ha]

  (R_earth = 6 378 137 m, Δλ = Δφ = pixel size in radians).

  This accounts for the varying area of geographic-coordinate pixels with
  latitude.  The nodata value (255) is excluded.

  The CGLS-LC100 product is **annual only** — one land cover map per year
  (2015–2019).  The five annual observations are plotted at their true
  temporal resolution; no sub-annual interpolation is applied.

  Downloaded windows (~16 GeoTIFF tiles per zone per year) are cached locally
  under  cgls_cache/  so subsequent runs skip the network requests.

Usage
-----
    python3 nile_agri_area.py

Output
------
    nile_agri_area.png   — plot of agricultural area (ha) vs time per zone
    cgls_cache/          — cached extracted windows (one .npy per zone/year)
"""

import math
import os
import pathlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yaml
import scipy  # noqa: F401  (kept for optional future use)

# ── GDAL / rasterio HTTP optimisations ────────────────────────────────────────
os.environ.setdefault("GDAL_HTTP_MERGE_CONSECUTIVE_RANGES", "YES")
os.environ.setdefault("GDAL_CACHEMAX", "512")           # 512 MB tile cache
os.environ.setdefault("CPL_VSIL_CURL_CACHE_SIZE", "128000000")  # 128 MB curl
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "120")       # 120 s read timeout
os.environ.setdefault("GDAL_HTTP_CONNECTTIMEOUT", "30") # 30 s connect timeout
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "4")

import rasterio
from rasterio.windows import from_bounds

# ── Constants ─────────────────────────────────────────────────────────────────
CACHE_DIR  = pathlib.Path(__file__).with_name("cgls_cache")
YAML_PATH  = pathlib.Path(__file__).with_name("nile.yaml")
OUT_PNG    = pathlib.Path(__file__).with_name("nile_agri_area.png")

# Half-width of the bounding box around each node (degrees).
# Chosen large enough to capture the irrigated corridor while remaining
# within ~55 km of the node centre.
BOX_DEG    = 0.5

# CGLS-LC100 v3 Crops-CoverFraction layers on Zenodo.
# File names follow three epoch labels: base / conso / nrt.
ZENODO_URLS = {
    2015: ("3939038", "2015-base"),
    2016: ("3518026", "2016-conso"),
    2017: ("3518036", "2017-conso"),
    2018: ("3518038", "2018-conso"),
    2019: ("3939050", "2019-nrt"),
}

R_EARTH = 6_378_137.0  # WGS-84 semi-major axis (m)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_nodes(yaml_path: pathlib.Path) -> list[dict]:
    with open(yaml_path) as fh:
        data = yaml.safe_load(fh)
    nodes = []
    for n in data.get("nodes", []):
        if "area_ha" not in n:
            continue
        nodes.append({
            "name": n["id"].capitalize(),
            "lat":  float(n["latitude"]),
            "lon":  float(n["longitude"]),
        })
    nodes.sort(key=lambda x: x["lat"])
    return nodes


def _zenodo_url(year: int) -> str:
    record_id, epoch_label = ZENODO_URLS[year]
    fname = (
        f"PROBAV_LC100_global_v3.0.1_{epoch_label}"
        f"_Crops-CoverFraction-layer_EPSG-4326.tif"
    )
    return f"/vsicurl/https://zenodo.org/records/{record_id}/files/{fname}?download=1"


def _pixel_area_ha(lat_deg: float, pixel_deg: float) -> float:
    """Area of one geographic pixel at *lat_deg* latitude (hectares)."""
    px_rad = math.radians(pixel_deg)
    cos_lat = math.cos(math.radians(lat_deg))
    area_m2 = (R_EARTH * px_rad) ** 2 * cos_lat
    return area_m2 * 1e-4   # m² → ha


def _cache_path(name: str, year: int) -> pathlib.Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{name.lower()}_{year}_crops_frac.npy"


def fetch_window(node: dict, year: int) -> np.ndarray:
    """
    Return the Crops-CoverFraction window (uint8, values 0–100, 255=nodata)
    centred on *node* for *year*, loading from cache if available.
    Retries up to MAX_TRIES times on transient network errors.
    """
    import time

    cache = _cache_path(node["name"], year)
    if cache.exists():
        return np.load(cache)

    lat, lon = node["lat"], node["lon"]
    url = _zenodo_url(year)
    print(f"  [{year}] Fetching {node['name']} window from Zenodo …", flush=True)

    MAX_TRIES = 4
    for attempt in range(1, MAX_TRIES + 1):
        try:
            with rasterio.open(url) as src:
                win = from_bounds(
                    left      = lon - BOX_DEG,
                    bottom    = lat - BOX_DEG,
                    right     = lon + BOX_DEG,
                    top       = lat + BOX_DEG,
                    transform = src.transform,
                )
                data      = src.read(1, window=win)
                pixel_deg = abs(src.transform.a)
            break   # success
        except Exception as exc:
            if attempt == MAX_TRIES:
                raise
            wait = 5 * attempt
            print(f"    attempt {attempt} failed ({exc!r}); retrying in {wait}s …",
                  flush=True)
            time.sleep(wait)

    result = data.astype(np.uint8)
    np.save(cache, result)
    np.save(cache.with_suffix(".meta.npy"), np.array([pixel_deg, lat]))
    return result


def crop_area_ha(node: dict, year: int) -> float:
    """
    Compute total cropland area (ha) within the bounding box of *node* for *year*.
    """
    cache = _cache_path(node["name"], year)
    meta_path = cache.with_suffix(".meta.npy")

    data = fetch_window(node, year)

    # Retrieve pixel_deg and centre lat from cache or re-open remote file
    if meta_path.exists():
        meta = np.load(meta_path)
        pixel_deg, centre_lat = float(meta[0]), float(meta[1])
    else:
        url = _zenodo_url(year)
        with rasterio.open(url) as src:
            pixel_deg = abs(src.transform.a)
        centre_lat = node["lat"]

    valid = data[data != 255]
    if valid.size == 0:
        return 0.0

    # Pixel area varies with latitude row.  For the (small) bounding box we use
    # the mean latitude of the window, which introduces < 0.1 % error for a 1°
    # window versus a per-row calculation.
    pa_ha = _pixel_area_ha(centre_lat, pixel_deg)
    return float((valid.astype(np.float64) / 100.0 * pa_ha).sum())


def annual_series(annual_areas: dict[int, float]) -> pd.Series:
    """Return a pd.Series of annual cropland areas indexed by 1 Jan of each year."""
    years  = sorted(annual_areas.keys())
    dates  = [pd.Timestamp(y, 1, 1) for y in years]
    values = [annual_areas[y] for y in years]
    return pd.Series(values, index=pd.DatetimeIndex(dates), name="agri_area_ha")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    nodes = _load_nodes(YAML_PATH)
    years = list(ZENODO_URLS.keys())

    print(f"Processing {len(nodes)} Nile basin zones for years {years[0]}–{years[-1]}")
    print(f"Source: CGLS-LC100 Collection 3 Crops-CoverFraction, Zenodo")

    all_series: dict[str, pd.Series] = {}

    for node in nodes:
        print(f"\n{node['name']}  (lat={node['lat']:.1f}, lon={node['lon']:.1f})")
        annual: dict[int, float] = {}
        for yr in years:
            area = crop_area_ha(node, yr)
            annual[yr] = area
            print(f"  {yr}: {area:,.0f} ha")
        all_series[node["name"]] = annual_series(annual)

    # ── Plot ──────────────────────────────────────────────────────────────────
    print("\nGenerating plot …")

    # Split zones into two groups for two-panel layout (avoids overplotting)
    names  = list(all_series.keys())
    half   = (len(names) + 1) // 2
    groups = [names[:half], names[half:]]

    fig, axes = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    cmap = plt.get_cmap("tab20", len(names))
    years_axis = [pd.Timestamp(y, 1, 1) for y in ZENODO_URLS]

    for ax, group in zip(axes, groups):
        for idx, name in enumerate(group):
            series = all_series[name]
            color  = cmap(names.index(name))
            vals_k = series.values / 1e3
            ax.plot(series.index, vals_k, "o-",
                    color=color, linewidth=1.5, markersize=6,
                    markeredgewidth=0.8, markeredgecolor="white",
                    label=f"{name}  ({vals_k.mean():,.0f} k ha avg)")

        ax.set_ylabel("Cropland area  (10³ ha)")
        ax.legend(ncol=2, fontsize=8.5, loc="upper left", framealpha=0.9)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(pd.Timestamp("2014-07-01"), pd.Timestamp("2020-06-01"))
        # Mark each epoch year
        for y in years_axis:
            ax.axvline(y, color="grey", linewidth=0.4, linestyle=":")

    axes[1].set_xlabel("Year")
    axes[1].xaxis.set_major_locator(mdates.YearLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    fig.suptitle(
        "CGLS-LC100 v3 Agricultural (Cropland) Area by Nile Basin Zone — Annual, 2015–2019\n"
        "Source: Copernicus Global Land Service, Crops Cover Fraction 100 m  •  "
        "Temporal resolution: annual (one epoch per year)",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()
