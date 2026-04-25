#!/usr/bin/env python3
"""
Nile Basin Evaporation Module
=========================
Downloads ERA5-Land data for each reservoir and computes evaporation using 
temperature-regression with water-only masking.

Usage:
    python evaporation.py --start-date 1950-01-01 --end-date 2026-12-31 --n-scenarios 3
"""

import argparse
import json
import math
import os
import pathlib
import sys
from datetime import date, timedelta
from typing import Any

import numpy as np
import yaml

try:
    import cdsapi
    _CDS_AVAILABLE = True
except ImportError:
    _CDS_AVAILABLE = False


YAML_FILE = pathlib.Path(__file__).with_name("nodes.yaml")
ERA5_CACHE_DIR = pathlib.Path(__file__).with_name("era5_cache")
OUTPUT_DIR = pathlib.Path(__file__).with_name("evap_csv")

def _coeff_file_path(month: int = None) -> pathlib.Path:
    """Get coefficient file path, optionally month-specific."""
    if month is not None:
        return pathlib.Path(__file__).with_name(f"regression_coefficients_{month:02d}.json")
    return pathlib.Path(__file__).with_name("regression_coefficients.json")

CDS_URL = "https://cds.climate.copernicus.eu/api/v2"

START_DATE = date(1950, 1, 1)
END_DATE = date(2026, 12, 31)
ERA5_START = date(1950, 1, 1)
ERA5_END = date(2024, 12, 31)

# Water detection thresholds
PEV_THRESHOLD = -0.006  # Not used, but kept for reference


def load_nodes(yaml_path: str | pathlib.Path = YAML_FILE) -> list[dict]:
    """Load node definitions from nodes.yaml."""
    with open(yaml_path) as fh:
        data = yaml.safe_load(fh)
    return data.get("nodes", [])


def _has_cds_credentials() -> bool:
    """Check for CDS API credentials."""
    return pathlib.Path.home().joinpath(".cdsapirc").exists()


def _bounding_box(extent: dict) -> tuple[float, float, float, float]:
    """Extract bounding box from extent dict."""
    return (extent["lat_min"], extent["lat_max"],
            extent["lon_min"], extent["lon_max"])


def _ensure_cache_dir() -> pathlib.Path:
    """Ensure cache directory exists."""
    ERA5_CACHE_DIR.mkdir(exist_ok=True)
    return ERA5_CACHE_DIR


def _ensure_output_dir() -> pathlib.Path:
    """Ensure output directory exists."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    return OUTPUT_DIR


def _get_lsm_path() -> pathlib.Path | None:
    """Find LSM file for the given region."""
    lsm_dir = pathlib.Path(__file__).parent
    for f in lsm_dir.glob("lsm_*.nc"):
        return f
    lsm_global = pathlib.Path("data_dl_test/lsm_0.area-subset.35.38.-5.28.nc")
    if lsm_global.exists():
        return lsm_global
    return None


def compute_regression_coefficients(node: dict, month: int = None) -> tuple[float, float]:
    """
    Compute linear regression coefficients (slope, intercept) for a node.
    
    Uses the single shared Nile basin ERA5 data.
    
    Args:
        node: Node dictionary with extent and interior coordinates
        month: If specified (1-12), only use data from that month each year
    
    Returns:
        (slope, intercept): regression coefficients
    """
    import pandas as pd
    
    extent = node.get("extent", {})
    lat_min, lat_max, lon_min, lon_max = _bounding_box(extent)
    node_id = node["id"]

    data_path = _get_nile_basin_data()
    
    if data_path is None:
        print(f"  No ERA5 data for {node_id}, using fallback coefficients")
        slope, intercept = _fallback_coefficients(node)
        print(f"  Coefficient: evap = {slope:.4f} × temp + {intercept:.4f}")
        return slope, intercept
    
    print(f"  Using shared basin data for {node_id}")

    try:
        import xarray as xr
    except ImportError:
        print("  ERROR: xarray required for regression")
        return _fallback_coefficients(node)

    try:
        ds = xr.open_dataset(str(data_path), engine="netcdf4")
        
        if "t2m" in ds:
            temp_arr = ds["t2m"].values
        elif "2t" in ds:
            temp_arr = ds["2t"].values
        else:
            print(f"  No temperature var found")
            return _fallback_coefficients(node)
            
        if "pev" in ds:
            evap_arr = -ds["pev"].values  # ERA5 pev is negative (flux downward)
        elif "potential_evaporation" in ds:
            evap_arr = -ds["potential_evaporation"].values
        elif "e" in ds:
            evap_arr = -ds["e"].values
        else:
            print(f"  No evaporation var found")
            return _fallback_coefficients(node)
            
        grib_lats = ds.coords["latitude"].values
        grib_lons = ds.coords["longitude"].values
        time_coords = ds.coords["valid_time"].values
    except Exception as e:
        print(f"  Warning could not open data: {e}")
        return _fallback_coefficients(node)

    grib_lat_mask = (grib_lats >= lat_min) & (grib_lats <= lat_max)
    grib_lon_mask = (grib_lons >= lon_min) & (grib_lons <= lon_max)

    lat_indices = np.where(grib_lat_mask)[0]
    lon_indices = np.where(grib_lon_mask)[0]

    if len(lat_indices) == 0 or len(lon_indices) == 0:
        print(f"  WARNING: No GRIB data in extent, using fallback")
        return _fallback_coefficients(node)

    temp_sub = temp_arr[:, lat_indices, :][:, :, lon_indices]
    evap_sub = evap_arr[:, lat_indices, :][:, :, lon_indices]
    
    if month is not None:
        time_series = pd.to_datetime(time_coords)
        month_mask = time_series.month == month
        
        temp_sub = temp_sub[month_mask]
        evap_sub = evap_sub[month_mask]
        print(f"  Filtering to month {month}: {temp_sub.shape[0]} time steps")
        
        if temp_sub.shape[0] == 0:
            print(f"  WARNING: No data for month {month}, using fallback")
            return _fallback_coefficients(node)

    lsm_path = _get_lsm_path()
    # Try new lake_cover first, fall back to old LSM
    lake_cover_path = _get_lake_cover()
    water_mask = None
    
    if lake_cover_path:
        try:
            ds_lc = xr.open_dataset(str(lake_cover_path), engine="netcdf4")
            lc_data = ds_lc["cl"].squeeze().values  # squeeze time dimension
            lc_lats = ds_lc.coords["latitude"].values
            lc_lons = ds_lc.coords["longitude"].values
            
            # Find indices in lake_cover matching GRIB coordinates via nearest-neighbor
            lc_lats_unique = np.unique(lc_lats)
            lc_lons_unique = np.unique(lc_lons)
            
            lc_lat_indices = []
            for glat in grib_lats[lat_indices]:
                matches = np.where(np.abs(lc_lats_unique - glat) < 0.05)[0]
                if len(matches) > 0:
                    lc_lat_indices.append(matches[0])
            lc_lat_indices = sorted(set(lc_lat_indices))
            
            lc_lon_indices = []
            for glon in grib_lons[lon_indices]:
                matches = np.where(np.abs(lc_lons_unique - glon) < 0.05)[0]
                if len(matches) > 0:
                    lc_lon_indices.append(matches[0])
            lc_lon_indices = sorted(set(lc_lon_indices))
            
            if len(lc_lat_indices) > 0 and len(lc_lon_indices) > 0:
                lc_sub = lc_data[np.ix_(lc_lat_indices, lc_lon_indices)]
                water_mask = (lc_sub > 0.5).astype(bool)
                print(f"  Using lake_cover mask: {water_mask.sum()} water cells")
        except Exception as e:
            print(f"  lake_cover skip: {e}")
    
    # If no lake_cover water, use interior point
    if water_mask is None or water_mask.sum() == 0:
        interior_lat = node.get("interior_lat")
        interior_lon = node.get("interior_lon")
        
        if interior_lat is not None and interior_lon is not None:
            # Find nearest grid cell to interior point
            lat_dist = np.abs(grib_lats[lat_indices] - interior_lat)
            lon_dist = np.abs(grib_lons[lon_indices] - interior_lon)
            
            if len(lat_dist) > 0 and len(lon_dist) > 0:
                interior_lat_idx = np.argmin(lat_dist)
                interior_lon_idx = np.argmin(lon_dist)
                
                # Create single-point mask
                water_mask = np.zeros((temp_sub.shape[1], temp_sub.shape[2]), dtype=bool)
                water_mask[interior_lat_idx, interior_lon_idx] = True
                print(f"  Using interior point mask: {water_mask.sum()} cell at ({interior_lat}, {interior_lon})")
    
    if water_mask is None:
# No mask available - use all valid points
        pass
    
    n_time = temp_sub.shape[0]
    
    if water_mask is not None:
        water_mask_expanded = np.broadcast_to(water_mask, (n_time, water_mask.shape[0], water_mask.shape[1]))
    else:
        water_mask_expanded = np.ones((temp_sub.shape[0], temp_sub.shape[1], temp_sub.shape[2]), dtype=bool)
        print(f"  No LSM water data, using all valid points")

    temp_flat = temp_sub.flatten()
    evap_flat = evap_sub.flatten()
    mask_flat = water_mask_expanded.flatten()

    valid_mask = (~np.isnan(temp_flat)) & (~np.isnan(evap_flat)) & mask_flat

    temp_celsius = temp_flat[valid_mask] - 273.15
    evap_mm = evap_flat[valid_mask] * 1000

    if len(temp_celsius) < 10:
        print(f"  WARNING: Insufficient valid data ({len(temp_celsius)} points), using fallback")
        return _fallback_coefficients(node)

    coeffs = np.polyfit(temp_celsius, evap_mm, 1)
    slope, intercept = coeffs

    print(f"  Regression: evap = {slope:.4f} × temp + {intercept:.4f}")
    print(f"  Data: {len(temp_celsius)} points, temp range {temp_celsius.min():.1f} to {temp_celsius.max():.1f} °C")

    return float(slope), float(intercept)


def _fallback_coefficients(node: dict) -> tuple[float, float]:
    """Generate fallback coefficients based on latitude."""
    lat = node.get("latitude", 0)
    if lat > 20:
        return 0.20, 0.0
    elif lat > 10:
        return 0.15, 0.3
    elif lat > 0:
        return 0.10, 0.5
    else:
        return 0.05, 0.9


def _download_era5_nile_basin() -> pathlib.Path:
    """Download ERA5 data for the full Nile basin once.
    
    Returns path to cached file.
    """
    if not _has_cds_credentials():
        print(f"  WARNING: No CDS credentials")
        return None

    cache_path = ERA5_CACHE_DIR / "era5_raw.nc"
    zip_path = ERA5_CACHE_DIR / "era5_raw.zip"
    
    if cache_path.exists():
        print(f"  Using cached: {cache_path.name}")
        return cache_path
    
    _ensure_cache_dir()
    
    print(f"  Downloading ERA5 data for Nile basin...")
    c = cdsapi.Client()

    try:
        c.retrieve(
            "reanalysis-era5-land-monthly-means",
            {
                "product_type": "monthly_averaged_reanalysis",
                "variable": [
                    "potential_evaporation",
                    "2m_temperature",
                ],
                "year": [str(y) for y in range(ERA5_START.year, ERA5_END.year + 1)],
                "month": [f"{m:02d}" for m in range(1, 13)],
                "time": "00:00",
                "area": [35, 25, -5, 40],  # Nile basin: lat -5 to 35, lon 25 to 40
                "format": "netcdf",
            },
            str(zip_path),
        )
        
        import zipfile
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(ERA5_CACHE_DIR)
        
        zip_path.unlink()
        
    except Exception as e:
        print(f"  ERROR downloading: {e}")
        return None
    
    extracted = ERA5_CACHE_DIR / "era5_raw.nc"
    if extracted.exists():
        print(f"  Downloaded and extracted: {extracted.name}")
        return extracted
    
    for f in ERA5_CACHE_DIR.glob("*.nc"):
        if f != zip_path:
            print(f"  Using extracted: {f.name}")
            return f
    
    return None


def _get_nile_basin_data() -> pathlib.Path | None:
    """Get the Nile basin ERA5 data file, downloading if needed."""
    cache_path = ERA5_CACHE_DIR / "era5_raw.nc"
    
    if cache_path.exists():
        print(f"  Using cached: {cache_path.name}")
        return cache_path
    
    return _download_era5_nile_basin()


def _download_lake_cover() -> pathlib.Path:
    """Download ERA5 static lake cover field.
    
    Returns path to cached file.
    """
    if not _has_cds_credentials():
        print(f"  WARNING: No CDS credentials")
        return None

    cache_path = ERA5_CACHE_DIR / "lake_cover.nc"
    
    if cache_path.exists():
        print(f"  Using cached: {cache_path.name}")
        return cache_path
    
    _ensure_cache_dir()
    
    print(f"  Downloading ERA5 lake cover...")
    c = cdsapi.Client()

    try:
        c.retrieve(
            "reanalysis-era5-land",
            {
                "variable": ["lake_cover"],
                "data_format": "netcdf",
                "download_format": "unarchived"
            },
            str(cache_path),
        )
        print(f"  Downloaded: {cache_path.name}")
        return cache_path
    except Exception as e:
        print(f"  ERROR downloading: {e}")
        return None


def _get_lake_cover() -> pathlib.Path | None:
    """Get the lake cover file, downloading if needed."""
    cache_path = ERA5_CACHE_DIR / "lake_cover.nc"
    
    if cache_path.exists():
        print(f"  Using cached: {cache_path.name}")
        return cache_path
    
    return _download_lake_cover()


def _fallback_data(node: dict) -> dict:
    """Generate fallback data when CDS is unavailable."""
    days = (END_DATE - START_DATE).days + 1
    lat = node.get("latitude", 0)

    base_temp = 25.0 - abs(lat) * 0.5
    base_pev = 4.0 + lat * 0.1

    temps = []
    pevs = []
    d = START_DATE
    for _ in range(days):
        doy = d.timetuple().tm_yday
        temp = base_temp + 7 * math.cos(2 * math.pi * (doy - 180) / 365)
        pev = base_pev + 1.5 * math.cos(2 * math.pi * (doy - 180) / 365)
        temps.append(temp)
        pevs.append(max(0, pev))
        d += timedelta(days=1)

    return {"pev": pevs, "temperature": temps}


def _load_era5_from_cache(node_id: str) -> dict | None:
    """Load ERA5 data from JSON cache."""
    pev_cache = ERA5_CACHE_DIR / f"{node_id}_pev.json"
    temp_cache = ERA5_CACHE_DIR / f"{node_id}_2t.json"

    if pev_cache.exists() and temp_cache.exists():
        with open(pev_cache) as f:
            pev_data = json.load(f)
        with open(temp_cache) as f:
            temp_data = json.load(f)
        return {"pev": pev_data, "temperature": temp_data}
    return None


def _extract_node_pev_series(node: dict, data_path: pathlib.Path) -> dict | None:
    """Extract monthly PEV time series for a node from the basin file.
    
    Returns dict with:
        - time: list of datetime objects
        - pev: list of PEV values (kg m⁻² s⁻¹), aggregated over the node extent
    """
    import pandas as pd
    
    extent = node.get("extent", {})
    lat_min, lat_max, lon_min, lon_max = _bounding_box(extent)
    interior_lat = node.get("interior_lat")
    interior_lon = node.get("interior_lon")
    
    try:
        import xarray as xr
    except ImportError:
        return None
    
    try:
        ds = xr.open_dataset(str(data_path), engine="netcdf4")
        
        if "pev" in ds:
            pev_arr = ds["pev"].values
        elif "potential_evaporation" in ds:
            pev_arr = ds["potential_evaporation"].values
        elif "e" in ds:
            pev_arr = ds["e"].values
        else:
            return None
        
        lats = ds.coords["latitude"].values
        lons = ds.coords["longitude"].values
        time_coords = pd.to_datetime(ds.coords["valid_time"].values)
        
        lat_mask = (lats >= lat_min) & (lats <= lat_max)
        lon_mask = (lons >= lon_min) & (lons <= lon_max)
        
        lat_indices = np.where(lat_mask)[0]
        lon_indices = np.where(lon_mask)[0]
        
        if len(lat_indices) == 0 or len(lon_indices) == 0:
            return None
        
        pev_sub = pev_arr[:, lat_indices, :][:, :, lon_indices]
        
        lake_cover_path = _get_lake_cover()
        water_mask = None
        
        if lake_cover_path:
            try:
                ds_lc = xr.open_dataset(str(lake_cover_path), engine="netcdf4")
                lc_data = ds_lc["cl"].squeeze().values
                lc_lats = np.unique(ds_lc.coords["latitude"].values)
                lc_lons = np.unique(ds_lc.coords["longitude"].values)
                
                lc_lat_indices = []
                for glat in lats[lat_indices]:
                    matches = np.where(np.abs(lc_lats - glat) < 0.05)[0]
                    if len(matches) > 0:
                        lc_lat_indices.append(matches[0])
                lc_lat_indices = sorted(set(lc_lat_indices))
                
                lc_lon_indices = []
                for glon in lons[lon_indices]:
                    matches = np.where(np.abs(lc_lons - glon) < 0.05)[0]
                    if len(matches) > 0:
                        lc_lon_indices.append(matches[0])
                lc_lon_indices = sorted(set(lc_lon_indices))
                
                if len(lc_lat_indices) > 0 and len(lc_lon_indices) > 0:
                    lc_sub = lc_data[np.ix_(lc_lat_indices, lc_lon_indices)]
                    water_mask = (lc_sub > 0.5).astype(bool)
            except:
                pass
        
        if water_mask is None or water_mask.sum() == 0:
            if interior_lat is not None and interior_lon is not None:
                lat_dist = np.abs(lats[lat_indices] - interior_lat)
                lon_dist = np.abs(lons[lon_indices] - interior_lon)
                
                if len(lat_dist) > 0 and len(lon_dist) > 0:
                    interior_lat_idx = np.argmin(lat_dist)
                    interior_lon_idx = np.argmin(lon_dist)
                    
                    water_mask = np.zeros((pev_sub.shape[1], pev_sub.shape[2]), dtype=bool)
                    water_mask[interior_lat_idx, interior_lon_idx] = True
        
        if water_mask is not None:
            n_time = pev_sub.shape[0]
            water_mask_expanded = np.broadcast_to(water_mask, (n_time, water_mask.shape[0], water_mask.shape[1]))
        else:
            water_mask_expanded = np.ones(pev_sub.shape, dtype=bool)
        
        pev_flat = pev_sub.flatten()
        mask_flat = water_mask_expanded.flatten()
        
        valid_mask = (~np.isnan(pev_flat)) & mask_flat
        
        if valid_mask.sum() < 10:
            return None
        
        pev_mean = pev_sub.mean(axis=(1, 2))
        valid_pev = pev_mean[~np.isnan(pev_mean)]
        valid_time = time_coords[~np.isnan(pev_mean)]
        
        return {
            "time": valid_time.tolist(),
            "pev": valid_pev.tolist(),
        }
        
    except Exception as e:
        print(f"  Error extracting PEV: {e}")
        return None


def generate_direct_pev_series(node: dict, start_date: date = START_DATE, end_date: date = END_DATE) -> list[dict]:
    """Generate daily evaporation time series using direct PEV from ERA5.
    
    - Get monthly PEV from ERA5
    - Convert to mm/month: PEV (kg m⁻² s⁻¹) × seconds_in_month
    - Convert to m³/day: mm/month / days_in_month × area_km² × 1000
    - For missing months (2025-2026), leave blank
    """
    import calendar
    
    node_id = node["id"]
    reservoir_area_km2 = node.get("reservoir_area_km2", 1000)
    
    data_path = _get_nile_basin_data()
    
    if data_path is None:
        print(f"  No ERA5 data, using fallback")
        return _generate_fallback_daily_series(node, start_date, end_date)
    
    era5_data = _extract_node_pev_series(node, data_path)
    
    if era5_data is None:
        print(f"  Could not extract PEV, using fallback")
        return _generate_fallback_daily_series(node, start_date, end_date)
    
    times = era5_data["time"]
    pev_values = era5_data["pev"]
    
    pev_by_month = {}
    for t, pev in zip(times, pev_values):
        key = (t.year, t.month)
        pev_by_month[key] = pev
    
    results = []
    current = start_date
    while current <= end_date:
        month_key = (current.year, current.month)
        
        if month_key in pev_by_month:
            pev_m = -pev_by_month[month_key]  # ERA5 pev is negative, negate; units = m (total for month)
            
            _, days_in_month = calendar.monthrange(current.year, current.month)
            
            m3_month = pev_m * reservoir_area_km2 * 1_000_000
            m3_day = m3_month / days_in_month
        else:
            m3_day = None
        
        results.append({
            "date": current.isoformat(),
            "evaporation_m3": m3_day,
        })
        
        current += timedelta(days=1)
    
    return results


def _generate_fallback_daily_series(node: dict, start_date: date, end_date: date) -> list[dict]:
    """Fallback daily series when ERA5 is unavailable."""
    import calendar
    
    results = []
    current = start_date
    while current <= end_date:
        results.append({
            "date": current.isoformat(),
            "evaporation_m3": None,
        })
        current += timedelta(days=1)
    return results


def export_direct_pev_csv(results: list, output_node_id: str, output_dir: pathlib.Path = OUTPUT_DIR,
                      start_date: date = START_DATE, end_date: date = END_DATE):
    """Export direct PEV results to CSV."""
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{output_node_id}_{start_date.year}_{end_date.year}_direct.csv"
    
    lines = ["date,evaporation_m3"]
    
    for row in results:
        evap = row.get("evaporation_m3")
        if evap is None:
            lines.append(f"{row['date']},")
        else:
            lines.append(f"{row['date']},{evap:.6f}")
    
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    
    print(f"  Wrote: {output_path}")


def generate_time_series(node: dict, coeffs: tuple[float, float],
                        n_scenarios: int = 1,
                        start_date: date = START_DATE,
                        end_date: date = END_DATE) -> list[dict]:
    """Generate evaporation time series with scenarios."""
    node_id = node["id"]
    reservoir_area_km2 = node.get("reservoir_area_km2", 1000)

    data_path = _get_nile_basin_data()
    
    if data_path is None:
        print(f"  Using fallback data for {node_id}")
        era5_data = _fallback_data(node)
    else:
        era5_data = _extract_node_data(node, data_path)
        if era5_data is None:
            print(f"  Using fallback data for {node_id}")
            era5_data = _fallback_data(node)

    slope, intercept = coeffs

    temp_data = era5_data.get("temperature", [])
    pev_data = era5_data.get("pev", [])

    if not temp_data:
        temp_data = _fallback_data(node)["temperature"]
    if not pev_data:
        pev_data = _fallback_data(node)["pev"]

    start_idx = max(0, (start_date - START_DATE).days)
    end_idx = min(len(temp_data), (end_date - START_DATE).days + 1)

    temps = temp_data[start_idx:end_idx]
    pevs = pev_data[start_idx:end_idx]

    scenario_cols = {f"scenario_{s+1}": [] for s in range(n_scenarios)}

    for i, (temp, pev_raw) in enumerate(zip(temps, pevs)):
        temp_k = temp if temp > 100 else temp + 273.15
        temp_c = temp_k - 273.15

        evap_mm = slope * temp_c + intercept

        if evap_mm < 0:
            evap_mm = 0.0

        evap_m3 = evap_mm * reservoir_area_km2 * 1000

        for s in range(n_scenarios):
            noise = 0.0 if s == 0 else np.random.normal(0, evap_m3 * 0.1)
            scenario_cols[f"scenario_{s+1}"].append(evap_m3 + noise)

    results = []
    d = start_date
    for i in range(len(temps)):
        row = {"date": d.isoformat()}
        for s in range(n_scenarios):
            row[f"scenario_{s+1}"] = scenario_cols[f"scenario_{s+1}"][i]
        results.append(row)
        d += timedelta(days=1)

    return results


def export_csv(results: list, node_id: str, output_dir: pathlib.Path = OUTPUT_DIR,
            start_date: date = START_DATE, end_date: date = END_DATE):
    """Export results to CSV in wide format."""
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{node_id}_{start_date.year}_{end_date.year}.csv"

    scenario_keys = [k for k in results[0].keys() if k != "date"]
    
    lines = ["date," + ",".join(scenario_keys)]
    
    for row in results:
        values = [str(row.get(k, 0)) for k in scenario_keys]
        lines.append(f"{row['date']},{','.join(values)}")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"  Wrote: {output_path}")


def compute_all_coefficients(force_recompute: bool = False, month: int = None) -> dict:
    """Compute or load regression coefficients for all nodes."""
    coeff_file = _coeff_file_path(month)
    if not force_recompute and coeff_file.exists():
        with open(coeff_file) as f:
            return json.load(f)

    nodes = load_nodes()
    coeffs = {}

    for node in nodes:
        node_id = node["id"]
        print(f"Computing regression for {node_id}...")

        slope, intercept = compute_regression_coefficients(node, month=month)

        coeffs[node_id] = {
            "slope": slope,
            "intercept": intercept,
        }

    with open(coeff_file, "w") as f:
        json.dump(coeffs, f, indent=2)

    return coeffs


def main():
    parser = argparse.ArgumentParser(
        description="Nile Basin Evaporation Module.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--start-date", type=str, default="1950-01-01",
        help="Start date (ISO 8601)"
    )
    parser.add_argument(
        "--end-date", type=str, default="2026-12-31",
        help="End date (ISO 8601)"
    )
    parser.add_argument(
        "--n-scenarios", type=int, default=1,
        help="Number of scenario columns"
    )
    parser.add_argument(
        "--download", dest="force_download", action="store_true",
        help="Force re-download from CDS"
    )
    parser.add_argument(
        "--download-lake-cover", dest="download_lake_cover", action="store_true",
        help="Download static lake cover mask"
    )
    parser.add_argument(
        "--recompute", dest="force_recompute", action="store_true",
        help="Force recompute regression coefficients"
    )
    parser.add_argument(
        "--month", type=int, default=None,
        help="Month (1-12) to filter data. If set, only uses data from that month each year"
    )
    parser.add_argument(
        "--generate-csv", dest="generate_csv", action="store_true",
        help="Generate CSV output files using regression model"
    )
    parser.add_argument(
        "--direct-pev", dest="direct_pev", action="store_true",
        help="Generate CSV with direct PEV (not regression)"
    )
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date)
    n_scenarios = args.n_scenarios

    print(f"Evaporation Module")
    print(f"  Period: {start_date} → {end_date}")
    print(f"  Scenarios: {n_scenarios}")

    nodes = load_nodes()
    print(f"  Nodes: {len(nodes)}")

    if args.force_download:
        print(f"\nForcing download of ERA5 data for Nile basin...")
        _download_era5_nile_basin()
    
    if args.download_lake_cover:
        print(f"\nDownloading static lake cover...")
        _download_lake_cover()

    coeffs = compute_all_coefficients(args.force_recompute, month=args.month)

    if args.generate_csv:
        for node in nodes:
            node_id = node["id"]
            print(f"\nProcessing {node_id}...")

            node_coeffs = coeffs.get(node_id, {"slope": 0.15, "intercept": 0.5})
            slope = node_coeffs["slope"]
            intercept = node_coeffs["intercept"]

            results = generate_time_series(
                node, (slope, intercept),
                n_scenarios=n_scenarios,
                start_date=start_date,
                end_date=end_date
            )

            export_csv(results, node_id, start_date=start_date, end_date=end_date)
    
    if args.direct_pev:
        for node in nodes:
            node_id = node["id"]
            print(f"\nGenerating direct PEV for {node_id}...")
            
            results = generate_direct_pev_series(node, start_date=start_date, end_date=end_date)
            
            export_direct_pev_csv(results, node_id, start_date=start_date, end_date=end_date)


if __name__ == "__main__":
    main()
