"""Structured CSV exports for Nile-relevant Copernicus data.

This module is intentionally a CSV sidecar to the existing Parquet-oriented
pipeline. The simulator keeps reading `data/timeseries/*.parquet`; this writer
creates a wider exploration bundle for inspection, notebooks, and later Rust
dataloader work.
"""
from __future__ import annotations

import json
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from hashlib import blake2b
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from dataloader import config
from dataloader.aggregate import monthly_forcings_from_era5
from dataloader.forcings import _bbox_for_node
from dataloader.nodes import NDVI_ZONES, NODES, REACHES

PROFILE_ORDER = {"core": 1, "hydro": 2, "full": 3}

CATALOG_ROWS = [
    {
        "dataset_id": "era5_daily_surface",
        "source_name": "ERA5 daily single-level statistics",
        "provider": "Copernicus Climate Data Store / ECMWF",
        "api_dataset": "derived-era5-single-levels-daily-statistics",
        "temporal_resolution": "daily",
        "profile": "core",
        "output_folder": "era5_daily",
        "variables": (
            "total_precipitation; 2m_temperature; 2m_dewpoint_temperature; "
            "surface_solar_radiation_downwards; 10m_u_component_of_wind; "
            "10m_v_component_of_wind; runoff"
        ),
        "why_relevant": "Rainfall, heat, radiation, wind, humidity, and runoff for PET and inflow proxies.",
        "notes": "Converted to one CSV per node, spatially averaged over a node-specific bbox.",
    },
    {
        "dataset_id": "era5_monthly_forcings",
        "source_name": "ERA5 monthly forcings derived locally",
        "provider": "Local transform from ERA5 daily",
        "api_dataset": "derived-era5-single-levels-daily-statistics",
        "temporal_resolution": "monthly",
        "profile": "core",
        "output_folder": "era5_monthly",
        "variables": "precip_mm; temp_c; radiation_mj_m2; wind_ms; dewpoint_c; pet_mm; runoff_mm",
        "why_relevant": "Direct simulator-ready hydrometeorological forcing table.",
        "notes": "Same fields as the canonical Parquet timeseries contract, but written as CSV.",
    },
    {
        "dataset_id": "era5_land_monthly_hydro",
        "source_name": "ERA5-Land monthly means",
        "provider": "Copernicus Climate Data Store / ECMWF",
        "api_dataset": "reanalysis-era5-land-monthly-means",
        "temporal_resolution": "monthly",
        "profile": "hydro",
        "output_folder": "era5_land_monthly",
        "variables": (
            "total_precipitation; runoff; potential_evaporation; total_evaporation; "
            "volumetric_soil_water_layer_1..4; skin_temperature"
        ),
        "why_relevant": "Higher-resolution land water-cycle fields for irrigation demand and drought proxies.",
        "notes": "CDS may return zipped NetCDF; the loader unwraps it before conversion.",
    },
    {
        "dataset_id": "glofas_historical_discharge",
        "source_name": "GloFAS historical river discharge",
        "provider": "Copernicus Emergency Management Service / EWDS",
        "api_dataset": "cems-glofas-historical",
        "temporal_resolution": "daily",
        "profile": "full",
        "output_folder": "glofas",
        "variables": "river_discharge_in_the_last_24_hours",
        "why_relevant": "River discharge baseline for calibration at headwaters, confluences, and dams.",
        "notes": "Real conversion requires cfgrib/eccodes in the Python environment.",
    },
    {
        "dataset_id": "sentinel2_ndvi_zones",
        "source_name": "Sentinel-2 L2A NDVI aggregation",
        "provider": "Copernicus Data Space Ecosystem",
        "api_dataset": "sentinel-2-l2a",
        "temporal_resolution": "monthly",
        "profile": "core",
        "output_folder": "ndvi",
        "variables": "ndvi_mean; ndvi_std; valid_pixel_frac",
        "why_relevant": "Vegetation/crop-water proxy for Gezira and Egypt irrigation zones.",
        "notes": "Uses existing NDVI overlay outputs when present; stub mode writes synthetic monthly values.",
    },
]

ERA5_LAND_VARIABLES = [
    "total_precipitation",
    "runoff",
    "potential_evaporation",
    "total_evaporation",
    "volumetric_soil_water_layer_1",
    "volumetric_soil_water_layer_2",
    "volumetric_soil_water_layer_3",
    "volumetric_soil_water_layer_4",
    "skin_temperature",
]

ERA5_LAND_COLUMN_MAP = {
    "tp": ("total_precipitation_mm", lambda s: s * 1000.0),
    "ro": ("runoff_mm", lambda s: s * 1000.0),
    "pev": ("potential_evaporation_mm", lambda s: s.abs() * 1000.0),
    "e": ("total_evaporation_mm", lambda s: s.abs() * 1000.0),
    "swvl1": ("soil_water_layer1_m3_m3", lambda s: s),
    "swvl2": ("soil_water_layer2_m3_m3", lambda s: s),
    "swvl3": ("soil_water_layer3_m3_m3", lambda s: s),
    "swvl4": ("soil_water_layer4_m3_m3", lambda s: s),
    "skt": ("skin_temperature_c", lambda s: s - 273.15),
}


@dataclass(frozen=True)
class NodeRef:
    node_id: str
    name: str
    node_type: str
    country: str
    lat: float
    lon: float


def build(
    *,
    stub: bool = False,
    profile: str = "core",
    start: str | None = None,
    end: str | None = None,
    overwrite: bool = False,
) -> None:
    """Build CSV outputs under `data/csv`.

    Profiles:
    - core: nodes/edges/catalog, ERA5 daily, ERA5 monthly, NDVI
    - hydro: core + ERA5-Land monthly hydrology
    - full: hydro + GloFAS daily discharge
    """
    profile = _validate_profile(profile)
    start = start or config.PERIOD_START
    end = end or config.PERIOD_END

    _ensure_nodes_geojson()
    config.CSV_DIR.mkdir(parents=True, exist_ok=True)
    _write_catalog(profile, overwrite=overwrite)
    _write_nodes_csv(overwrite=overwrite)
    _write_edges_csv(overwrite=overwrite)

    nodes = _load_node_refs()
    _write_era5_csvs(nodes, start=start, end=end, stub=stub, overwrite=overwrite)
    _write_ndvi_csvs(start=start, end=end, stub=stub, overwrite=overwrite)

    if _profile_at_least(profile, "hydro"):
        _write_era5_land_csvs(nodes, start=start, end=end, stub=stub, overwrite=overwrite)
    if _profile_at_least(profile, "full"):
        _write_glofas_csvs(nodes, start=start, end=end, stub=stub, overwrite=overwrite)


def _validate_profile(profile: str) -> str:
    normalized = profile.lower().strip()
    if normalized not in PROFILE_ORDER:
        raise ValueError(f"Unknown CSV profile {profile!r}; expected core, hydro, or full")
    return normalized


def _profile_at_least(profile: str, minimum: str) -> bool:
    return PROFILE_ORDER[profile] >= PROFILE_ORDER[minimum]


def _ensure_nodes_geojson() -> None:
    if config.NODES_GEOJSON.exists():
        return
    from dataloader import nodes as nodes_mod

    nodes_mod.build(stub=False)


def _write_catalog(profile: str, *, overwrite: bool) -> None:
    path = config.CSV_DIR / "catalog.csv"
    if path.exists() and not overwrite:
        return
    max_level = PROFILE_ORDER[profile]
    rows = [row for row in CATALOG_ROWS if PROFILE_ORDER[row["profile"]] <= max_level]
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_nodes_csv(*, overwrite: bool) -> None:
    path = config.CSV_DIR / "nodes.csv"
    if path.exists() and not overwrite:
        return
    rows = []
    for node in NODES:
        params = node.get("params", {})
        rows.append(
            {
                "node_id": node["id"],
                "name": node["name"],
                "node_type": node["type"],
                "country": node["country"],
                "latitude": node["lat"],
                "longitude": node["lon"],
                "upstream": ";".join(node["upstream"]),
                "downstream": ";".join(node["downstream"]),
                "catchment_area_km2": params.get("catchment_area_km2"),
                "storage_capacity_mcm": params.get("storage_capacity_mcm"),
                "surface_area_km2_at_full": params.get("surface_area_km2_at_full"),
                "area_ha_baseline": params.get("area_ha_baseline"),
                "population_baseline": params.get("population_baseline"),
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_edges_csv(*, overwrite: bool) -> None:
    path = config.CSV_DIR / "edges.csv"
    if path.exists() and not overwrite:
        return
    rows = []
    for node in NODES:
        for downstream in node["downstream"]:
            reach_params = REACHES.get(node["id"], {})
            rows.append(
                {
                    "edge_id": f"{node['id']}__{downstream}",
                    "from_node_id": node["id"],
                    "to_node_id": downstream,
                    "flow_share": 1.0,
                    "travel_time_months": reach_params.get("travel_time_months"),
                    "muskingum_k": reach_params.get("muskingum_k"),
                    "muskingum_x": reach_params.get("muskingum_x"),
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)


def _load_node_refs() -> list[NodeRef]:
    geojson = json.loads(config.NODES_GEOJSON.read_text())
    nodes = []
    for feature in geojson["features"]:
        lon, lat = feature["geometry"]["coordinates"]
        props = feature["properties"]
        nodes.append(
            NodeRef(
                node_id=props["id"],
                name=props["name"],
                node_type=props["type"],
                country=props["country"],
                lat=float(lat),
                lon=float(lon),
            )
        )
    return nodes


def _write_era5_csvs(
    nodes: list[NodeRef], *, start: str, end: str, stub: bool, overwrite: bool
) -> None:
    daily_dir = config.CSV_DIR / "era5_daily"
    monthly_dir = config.CSV_DIR / "era5_monthly"
    daily_dir.mkdir(parents=True, exist_ok=True)
    monthly_dir.mkdir(parents=True, exist_ok=True)

    for node in nodes:
        daily_path = daily_dir / f"{node.node_id}.csv"
        monthly_path = monthly_dir / f"{node.node_id}.csv"
        if stub:
            if overwrite or not daily_path.exists():
                _stub_daily_forcings(node, start, end).to_csv(daily_path, index=False)
            if overwrite or not monthly_path.exists():
                _stub_monthly_forcings(node, start, end).to_csv(monthly_path, index=False)
            continue

        if daily_path.exists() and monthly_path.exists() and not overwrite:
            continue

        bbox = _bbox_for_node(node.node_type, node.lat, node.lon)
        nc_path = config.DATA_DIR / "raw_era5" / f"{node.node_id}_{start}_{end}.nc"
        from dataloader.era5 import fetch_era5_daily

        fetch_era5_daily(bbox, start, end, nc_path)
        if overwrite or not daily_path.exists():
            _era5_daily_dataframe(nc_path, bbox=bbox).to_csv(daily_path, index=False)
        if overwrite or not monthly_path.exists():
            monthly = monthly_forcings_from_era5(
                nc_path,
                lat_min=bbox[2],
                lat_max=bbox[0],
                lon_min=bbox[1],
                lon_max=bbox[3],
            )
            monthly.to_csv(monthly_path, index=False)


def _write_era5_land_csvs(
    nodes: list[NodeRef], *, start: str, end: str, stub: bool, overwrite: bool
) -> None:
    out_dir = config.CSV_DIR / "era5_land_monthly"
    out_dir.mkdir(parents=True, exist_ok=True)
    for node in nodes:
        out_path = out_dir / f"{node.node_id}.csv"
        if out_path.exists() and not overwrite:
            continue
        if stub:
            _stub_era5_land_monthly(node, start, end).to_csv(out_path, index=False)
            continue

        bbox = _bbox_for_node(node.node_type, node.lat, node.lon)
        nc_path = config.DATA_DIR / "raw_era5_land" / f"{node.node_id}_{start}_{end}.nc"
        fetch_era5_land_monthly(bbox, start, end, nc_path)
        _era5_land_monthly_dataframe(nc_path, bbox=bbox).to_csv(out_path, index=False)


def _write_glofas_csvs(
    nodes: list[NodeRef], *, start: str, end: str, stub: bool, overwrite: bool
) -> None:
    out_dir = config.CSV_DIR / "glofas"
    out_dir.mkdir(parents=True, exist_ok=True)
    for node in nodes:
        out_path = out_dir / f"{node.node_id}.csv"
        if out_path.exists() and not overwrite:
            continue
        if stub:
            _stub_glofas_discharge(node, start, end).to_csv(out_path, index=False)
            continue

        bbox = _small_bbox(node.lat, node.lon, radius=0.15)
        nc_path = config.DATA_DIR / "raw_glofas" / f"{node.node_id}_{start}_{end}.nc"
        fetch_glofas_daily(bbox, start, end, nc_path)
        _glofas_dataframe(nc_path, bbox=bbox).to_csv(out_path, index=False)


def _write_ndvi_csvs(*, start: str, end: str, stub: bool, overwrite: bool) -> None:
    out_dir = config.CSV_DIR / "ndvi"
    out_dir.mkdir(parents=True, exist_ok=True)
    for zone_id, zone in NDVI_ZONES.items():
        out_path = out_dir / f"{zone_id}.csv"
        if out_path.exists() and not overwrite:
            continue
        if stub:
            _stub_ndvi(zone_id, start, end).to_csv(out_path, index=False)
            continue
        parquet_path = config.OVERLAYS_DIR / f"{zone_id}.parquet"
        if parquet_path.exists():
            pd.read_parquet(parquet_path).to_csv(out_path, index=False)
        else:
            # The real NDVI fetch is still a placeholder in overlays.py. Keep
            # the CSV folder complete and mark the generated values as fallback.
            df = _stub_ndvi(zone_id, start, end)
            df["quality_flag"] = "fallback_stub_no_ndvi_parquet"
            df["node_id"] = zone["node_id"]
            df.to_csv(out_path, index=False)


def fetch_era5_land_monthly(
    bbox: tuple[float, float, float, float],
    start: str,
    end: str,
    out_path: Path,
) -> Path:
    """Download ERA5-Land monthly NetCDF for a node bbox and date range."""
    if out_path.exists():
        return out_path
    import cdsapi

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(".download")
    years = [str(year) for year in range(_date(start).year, _date(end).year + 1)]

    client = cdsapi.Client()
    client.retrieve(
        "reanalysis-era5-land-monthly-means",
        {
            "product_type": "monthly_averaged_reanalysis",
            "variable": ERA5_LAND_VARIABLES,
            "year": years,
            "month": [f"{month:02d}" for month in range(1, 13)],
            "time": "00:00",
            "area": list(bbox),
            "format": "netcdf",
        },
        str(tmp_path),
    )
    _move_unzipped_netcdf(tmp_path, out_path)
    return out_path


def fetch_glofas_daily(
    bbox: tuple[float, float, float, float],
    start: str,
    end: str,
    out_path: Path,
) -> Path:
    """Download GloFAS historical river discharge as NetCDF via EWDS."""
    if out_path.exists():
        return out_path
    import cdsapi

    url = _first_present("EWDS_API_URL", "CDS_API_URL") or "https://ewds.climate.copernicus.eu/api"
    key = _first_present("EWDS_API_KEY", "CDS_API_KEY") or _cdsapirc_key()
    if not key:
        raise RuntimeError("Missing EWDS_API_KEY, CDS_API_KEY, or ~/.cdsapirc key for GloFAS fetch")

    days = _date_parts(start, end)
    request = {
        "system_version": ["version_4_0"],
        "hydrological_model": ["lisflood"],
        "product_type": ["intermediate"],
        "variable": ["river_discharge_in_the_last_24_hours"],
        "hyear": sorted({y for y, _, _ in days}),
        "hmonth": sorted({m for _, m, _ in days}),
        "hday": sorted({d for _, _, d in days}),
        "area": list(bbox),
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = cdsapi.Client(url=url, key=key).retrieve("cems-glofas-historical", request)
    except Exception as error:
        message = str(error)
        if "didn't accept all required site policies" in message or "Missing policies" in message:
            raise RuntimeError(
                "EWDS rejected the GloFAS request because the account has not accepted "
                "the CEMS terms yet: https://ewds.climate.copernicus.eu/licences/terms-of-use-cems"
            ) from error
        raise
    if not hasattr(result, "download"):
        raise RuntimeError("cdsapi result does not expose download(); upgrade cdsapi")
    result.download(str(out_path))
    return out_path


def _era5_daily_dataframe(
    source: Path | str | xr.Dataset, *, bbox: tuple[float, float, float, float]
) -> pd.DataFrame:
    ds = _open_normalized_dataset(source)
    try:
        ds = _crop_and_spatial_mean(ds, bbox)
        frame = pd.DataFrame({"date": pd.to_datetime(ds["time"].values).date})
        if "tp" in ds:
            frame["precip_mm_day"] = _values(ds["tp"] * 1000.0)
        if "t2m" in ds:
            frame["temp_c"] = _values(ds["t2m"] - 273.15)
        if "d2m" in ds:
            frame["dewpoint_c"] = _values(ds["d2m"] - 273.15)
        if "ssrd" in ds:
            frame["radiation_mj_m2_day"] = _values(ds["ssrd"] / 1e6)
        if "si10" in ds:
            frame["wind_ms"] = _values(ds["si10"])
        elif "u10" in ds and "v10" in ds:
            frame["wind_ms"] = _values(np.hypot(ds["u10"], ds["v10"]))
        if "ro" in ds:
            frame["runoff_mm_day"] = _values(ds["ro"] * 1000.0)
        return frame
    finally:
        if not isinstance(source, xr.Dataset):
            ds.close()


def _era5_land_monthly_dataframe(
    source: Path | str | xr.Dataset, *, bbox: tuple[float, float, float, float]
) -> pd.DataFrame:
    ds = _open_normalized_dataset(source)
    try:
        ds = _crop_and_spatial_mean(ds, bbox)
        out = pd.DataFrame({"month": pd.to_datetime(ds["time"].values).to_period("M").to_timestamp()})
        for var_name, (column, transform) in ERA5_LAND_COLUMN_MAP.items():
            if var_name in ds:
                out[column] = _values(transform(ds[var_name]))
        return out
    finally:
        if not isinstance(source, xr.Dataset):
            ds.close()


def _glofas_dataframe(source: Path | str, *, bbox: tuple[float, float, float, float]) -> pd.DataFrame:
    try:
        ds = xr.open_dataset(source)
    except ValueError as error:
        raise RuntimeError(f"Could not open GloFAS NetCDF output at {source}") from error
    try:
        ds = _normalize_coords(ds)
        ds = _crop_and_spatial_mean(ds, bbox)
        variable = _first_data_var(ds, preferred=("dis24", "river_discharge"))
        return pd.DataFrame(
            {
                "date": pd.to_datetime(ds["time"].values).date,
                "river_discharge_m3s": _values(ds[variable]),
            }
        )
    finally:
        ds.close()


def _open_normalized_dataset(source: Path | str | xr.Dataset) -> xr.Dataset:
    ds = source if isinstance(source, xr.Dataset) else xr.open_dataset(source)
    return _normalize_coords(ds)


def _normalize_coords(ds: xr.Dataset) -> xr.Dataset:
    rename = {}
    if "valid_time" in ds.coords or "valid_time" in ds.dims:
        rename["valid_time"] = "time"
    if "latitude" not in ds.coords and "lat" in ds.coords:
        rename["lat"] = "latitude"
    if "longitude" not in ds.coords and "lon" in ds.coords:
        rename["lon"] = "longitude"
    return ds.rename(rename) if rename else ds


def _crop_and_spatial_mean(
    ds: xr.Dataset, bbox: tuple[float, float, float, float]
) -> xr.Dataset:
    lat_max, lon_min, lat_min, lon_max = bbox
    if "latitude" in ds.coords and "longitude" in ds.coords:
        ds = ds.where(
            (ds.latitude >= lat_min)
            & (ds.latitude <= lat_max)
            & (ds.longitude >= lon_min)
            & (ds.longitude <= lon_max),
            drop=True,
        )
        if "latitude" in ds.dims and "longitude" in ds.dims:
            weights = np.cos(np.deg2rad(ds.latitude))
            return ds.weighted(weights).mean(dim=("latitude", "longitude"))
    return ds


def _stub_daily_forcings(node: NodeRef, start: str, end: str) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="D")
    rng = _rng(node.node_id, "era5_daily")
    season = np.sin(2 * np.pi * (dates.dayofyear.to_numpy() - 100) / 365.25)
    wetness = 1.0 if node.lat < 12 else 0.45 if node.lat < 20 else 0.15
    precip = np.clip((2.0 + 4.0 * season) * wetness + rng.normal(0, 1.0, len(dates)), 0, None)
    runoff = np.clip(precip * (0.08 + 0.07 * wetness) + rng.normal(0, 0.05, len(dates)), 0, None)
    return pd.DataFrame(
        {
            "date": dates.date,
            "precip_mm_day": precip,
            "temp_c": 24 + 6 * season + (node.lat / 12) + rng.normal(0, 0.8, len(dates)),
            "dewpoint_c": 12 + 5 * season - max(node.lat - 12, 0) * 0.25,
            "radiation_mj_m2_day": np.clip(18 + 5 * season + rng.normal(0, 0.7, len(dates)), 4, None),
            "wind_ms": np.clip(2.5 + rng.normal(0, 0.35, len(dates)), 0.2, None),
            "runoff_mm_day": runoff,
            "quality_flag": "stub",
        }
    )


def _stub_monthly_forcings(node: NodeRef, start: str, end: str) -> pd.DataFrame:
    daily = _stub_daily_forcings(node, start, end)
    daily["date"] = pd.to_datetime(daily["date"])
    monthly = daily.resample("1MS", on="date").agg(
        {
            "precip_mm_day": "sum",
            "temp_c": "mean",
            "radiation_mj_m2_day": "mean",
            "wind_ms": "mean",
            "dewpoint_c": "mean",
            "runoff_mm_day": "sum",
        }
    )
    monthly = monthly.reset_index().rename(
        columns={
            "date": "month",
            "precip_mm_day": "precip_mm",
            "radiation_mj_m2_day": "radiation_mj_m2",
            "runoff_mm_day": "runoff_mm",
        }
    )
    monthly["pet_mm"] = np.clip(
        monthly["radiation_mj_m2"] * 4.2 + monthly["temp_c"] * 2.0 - monthly["dewpoint_c"],
        0,
        None,
    )
    monthly["historical_discharge_m3s"] = pd.NA
    monthly["quality_flag"] = "stub"
    return monthly[
        [
            "month",
            "precip_mm",
            "temp_c",
            "radiation_mj_m2",
            "wind_ms",
            "dewpoint_c",
            "pet_mm",
            "runoff_mm",
            "historical_discharge_m3s",
            "quality_flag",
        ]
    ]


def _stub_era5_land_monthly(node: NodeRef, start: str, end: str) -> pd.DataFrame:
    monthly = _stub_monthly_forcings(node, start, end)
    rng = _rng(node.node_id, "era5_land")
    out = pd.DataFrame(
        {
            "month": monthly["month"],
            "total_precipitation_mm": monthly["precip_mm"],
            "runoff_mm": monthly["runoff_mm"],
            "potential_evaporation_mm": monthly["pet_mm"] * 0.92,
            "total_evaporation_mm": monthly["pet_mm"] * 0.55,
            "soil_water_layer1_m3_m3": np.clip(0.18 + monthly["precip_mm"] / 800 + rng.normal(0, 0.01, len(monthly)), 0.04, 0.55),
            "soil_water_layer2_m3_m3": np.clip(0.20 + monthly["precip_mm"] / 900 + rng.normal(0, 0.01, len(monthly)), 0.04, 0.55),
            "soil_water_layer3_m3_m3": np.clip(0.22 + monthly["precip_mm"] / 1000 + rng.normal(0, 0.01, len(monthly)), 0.04, 0.55),
            "soil_water_layer4_m3_m3": np.clip(0.25 + monthly["precip_mm"] / 1200 + rng.normal(0, 0.01, len(monthly)), 0.04, 0.55),
            "skin_temperature_c": monthly["temp_c"] + 1.5,
            "quality_flag": "stub",
        }
    )
    return out


def _stub_glofas_discharge(node: NodeRef, start: str, end: str) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="D")
    rng = _rng(node.node_id, "glofas")
    season = np.sin(2 * np.pi * (dates.dayofyear.to_numpy() - 190) / 365.25)
    base = 450 + max(0, 18 - node.lat) * 60
    if node.node_type == "reservoir":
        base *= 1.5
    flow = np.clip(base + base * 0.45 * season + rng.normal(0, base * 0.05, len(dates)), 5, None)
    return pd.DataFrame({"date": dates.date, "river_discharge_m3s": flow, "quality_flag": "stub"})


def _stub_ndvi(zone_id: str, start: str, end: str) -> pd.DataFrame:
    months = pd.date_range(start, end, freq="MS")
    rng = _rng(zone_id, "ndvi")
    season = np.sin(2 * np.pi * (months.month.to_numpy() - 4) / 12)
    return pd.DataFrame(
        {
            "month": months,
            "ndvi_mean": np.clip(0.35 + 0.24 * season + rng.normal(0, 0.03, len(months)), -1, 1),
            "ndvi_std": np.clip(0.05 + rng.normal(0, 0.01, len(months)), 0.01, 0.2),
            "valid_pixel_frac": np.clip(0.82 + rng.normal(0, 0.08, len(months)), 0, 1),
            "quality_flag": "stub",
        }
    )


def _move_unzipped_netcdf(tmp_path: Path, out_path: Path) -> None:
    if zipfile.is_zipfile(tmp_path):
        with zipfile.ZipFile(tmp_path) as archive:
            nc_names = [name for name in archive.namelist() if name.endswith(".nc")]
            if not nc_names:
                raise RuntimeError(f"{tmp_path} is a ZIP with no NetCDF member")
            with archive.open(nc_names[0]) as source, out_path.open("wb") as target:
                target.write(source.read())
        tmp_path.unlink(missing_ok=True)
        return
    tmp_path.replace(out_path)


def _date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _date_parts(start: str, end: str) -> list[tuple[str, str, str]]:
    days = pd.date_range(start, end, freq="D")
    return [(f"{d.year:04d}", f"{d.month:02d}", f"{d.day:02d}") for d in days]


def _small_bbox(lat: float, lon: float, *, radius: float) -> tuple[float, float, float, float]:
    return (lat + radius, lon - radius, lat - radius, lon + radius)


def _values(array: xr.DataArray) -> np.ndarray:
    return np.asarray(array.values).reshape(-1)


def _first_data_var(ds: xr.Dataset, *, preferred: tuple[str, ...]) -> str:
    for name in preferred:
        if name in ds.data_vars:
            return name
    try:
        return next(iter(ds.data_vars))
    except StopIteration as error:
        raise RuntimeError("Dataset has no data variables") from error


def _first_present(*keys: str) -> str | None:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return None


def _cdsapirc_key(path: Path | None = None) -> str | None:
    rc_path = path or Path.home() / ".cdsapirc"
    if not rc_path.exists():
        return None
    match = re.search(r"^key:\s*(.+)$", rc_path.read_text(), flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _rng(*parts: str) -> np.random.Generator:
    digest = blake2b("|".join(parts).encode("utf-8"), digest_size=8).digest()
    seed = int.from_bytes(digest, byteorder="big", signed=False) % (2**32)
    return np.random.default_rng(seed)
