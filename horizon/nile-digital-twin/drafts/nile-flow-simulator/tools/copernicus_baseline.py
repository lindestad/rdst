"""Build a browser-readable Copernicus baseline for the draft simulator.

This fetches real CEMS GloFAS river discharge and ERA5-Land monthly fields,
then aggregates them to the 12-row shape consumed by the frontend. Sentinel-2
crop activity and CLMS Water Bodies reservoir area are kept as documented
fallback climatologies here; replacing those requires a STAC/raster extraction
step over irrigation-zone and reservoir polygons.
"""
from __future__ import annotations

import calendar
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from dataloader import config

GLOFAS_DATASET = "cems-glofas-historical"
ERA5_LAND_DATASET = "reanalysis-era5-land-monthly-means"

NILE_AREA = [32.5, 21.0, -1.5, 39.5]  # north, west, south, east
MONTHS = [f"{m:02d}" for m in range(1, 13)]


@dataclass(frozen=True)
class SamplePoint:
    name: str
    lat: float
    lon: float


GLOFAS_POINTS = {
    "whiteNileM3s": SamplePoint("White Nile near Malakal", 9.53, 31.65),
    "blueNileToGerdM3s": SamplePoint("Blue Nile at GERD", 11.22, 35.09),
    "atbaraM3s": SamplePoint("Atbara branch", 14.0, 36.0),
}

# Temporary Copernicus-adjacent fallbacks. Replace via Sentinel-2/CLMS raster
# extraction once polygons for these zones are finalized.
SENTINEL2_CROP_ACTIVITY = {
    "geziraCropActivity": [0.72, 0.68, 0.62, 0.58, 0.66, 0.78, 0.92, 0.96, 0.88, 0.76, 0.70, 0.74],
    "egyptCropActivity": [0.88, 0.86, 0.79, 0.72, 0.84, 0.94, 0.98, 0.95, 0.87, 0.78, 0.82, 0.90],
}

WATER_BODIES_AREA_KM2 = {
    "gerdAreaKm2": [1030, 1015, 1000, 995, 1005, 1080, 1320, 1620, 1740, 1680, 1480, 1190],
    "aswanAreaKm2": [4780, 4680, 4550, 4420, 4310, 4240, 4280, 4480, 4760, 4930, 4990, 4920],
}


def build(
    *,
    start_year: int,
    end_year: int,
    out_path: Path,
    raw_dir: Path | None = None,
) -> Path:
    raw = raw_dir or config.DATA_DIR / "raw_copernicus"
    raw.mkdir(parents=True, exist_ok=True)
    years = [str(year) for year in range(start_year, end_year + 1)]

    glofas_path = _fetch_glofas(years, raw / f"glofas_{start_year}_{end_year}.nc")
    era5_path = _fetch_era5_land(years, raw / f"era5_land_{start_year}_{end_year}.nc")

    glofas = _monthly_glofas(glofas_path)
    era5 = _monthly_era5_land(era5_path)
    months = []
    for month in range(1, 13):
        months.append({
            "month": month,
            "label": calendar.month_abbr[month],
            "glofas": {
                "whiteNileM3s": _value(glofas, month, "whiteNileM3s"),
                "blueNileToGerdM3s": _value(glofas, month, "blueNileToGerdM3s"),
                "atbaraM3s": _value(glofas, month, "atbaraM3s"),
            },
            "era5Land": {
                "runoffIndex": _value(era5, month, "runoffIndex"),
                "petMm": _value(era5, month, "petMm"),
            },
            "sentinel2": {
                "geziraCropActivity": SENTINEL2_CROP_ACTIVITY["geziraCropActivity"][month - 1],
                "egyptCropActivity": SENTINEL2_CROP_ACTIVITY["egyptCropActivity"][month - 1],
            },
            "waterBodies": {
                "gerdAreaKm2": WATER_BODIES_AREA_KM2["gerdAreaKm2"][month - 1],
                "aswanAreaKm2": WATER_BODIES_AREA_KM2["aswanAreaKm2"][month - 1],
            },
        })

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "period": [start_year, end_year],
        "source": {
            "glofas": GLOFAS_DATASET,
            "era5Land": ERA5_LAND_DATASET,
            "note": (
                "GloFAS and ERA5-Land are fetched from Copernicus APIs. "
                "Sentinel-2 crop activity and CLMS Water Bodies areas are "
                "fallback climatologies pending raster extraction."
            ),
        },
        "months": months,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    return out_path


def _fetch_glofas(years: list[str], out_path: Path) -> Path:
    if out_path.exists():
        return out_path
    client = _cds_client("EWDS_API_URL", "EWDS_API_KEY", default_url="https://ewds.climate.copernicus.eu/api")
    request: dict[str, Any] = {
        "system_version": "version_4_0",
        "product_type": "consolidated",
        "hydrological_model": "lisflood",
        "variable": "river_discharge_in_the_last_24_hours",
        "hyear": years,
        "hmonth": MONTHS,
        "hday": [f"{day:02d}" for day in range(1, 32)],
        "area": NILE_AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    try:
        client.retrieve(GLOFAS_DATASET, request, str(out_path))
    except Exception as exc:
        raise RuntimeError(
            "GloFAS fetch failed. Ensure your EWDS credentials are configured. "
            "For cdsapi this usually means EWDS_API_URL=https://ewds.climate.copernicus.eu/api "
            "and EWDS_API_KEY='<uid>:<api-key>', or an equivalent ~/.cdsapirc."
        ) from exc
    return out_path


def _fetch_era5_land(years: list[str], out_path: Path) -> Path:
    if out_path.exists():
        return out_path
    client = _cds_client("CDSAPI_URL", "CDSAPI_KEY")
    request: dict[str, Any] = {
        "product_type": "monthly_averaged_reanalysis",
        "variable": ["runoff", "potential_evaporation"],
        "year": years,
        "month": MONTHS,
        "time": "00:00",
        "area": NILE_AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    try:
        client.retrieve(ERA5_LAND_DATASET, request, str(out_path))
    except Exception as exc:
        raise RuntimeError(
            "ERA5-Land fetch failed. Ensure CDS credentials are configured in ~/.cdsapirc "
            "or CDSAPI_URL/CDSAPI_KEY."
        ) from exc
    return out_path


def _cds_client(url_env: str, key_env: str, *, default_url: str | None = None):
    import cdsapi

    url = os.environ.get(url_env, default_url)
    key = os.environ.get(key_env)
    if url and key:
        return cdsapi.Client(url=url, key=key)
    if url:
        return cdsapi.Client(url=url)
    return cdsapi.Client()


def _monthly_glofas(path: Path) -> pd.DataFrame:
    import xarray as xr

    with xr.open_dataset(path) as ds:
        ds = _normalize_coords(ds)
        var = _find_var(ds, ["river_discharge", "discharge", "dis24", "dis"])
        rows = []
        for column, point in GLOFAS_POINTS.items():
            series = ds[var].sel(latitude=point.lat, longitude=point.lon, method="nearest")
            frame = series.to_dataframe(name=column).reset_index()
            time_col = _time_column(frame)
            frame["month"] = pd.to_datetime(frame[time_col]).dt.month
            monthly = frame.groupby("month", as_index=False)[column].mean()
            rows.append(monthly)

    out = rows[0]
    for frame in rows[1:]:
        out = out.merge(frame, on="month", how="outer")
    return out.sort_values("month")


def _monthly_era5_land(path: Path) -> pd.DataFrame:
    import xarray as xr

    with xr.open_dataset(path) as ds:
        ds = _normalize_coords(ds)
        runoff_var = _find_var(ds, ["runoff", "ro"])
        pet_var = _find_var(ds, ["potential_evaporation", "pev"])
        runoff = ds[runoff_var].mean(dim=[d for d in ds[runoff_var].dims if d in {"latitude", "longitude"}])
        pet = ds[pet_var].mean(dim=[d for d in ds[pet_var].dims if d in {"latitude", "longitude"}])
        frame = pd.DataFrame({
            "time": pd.to_datetime(runoff[_time_coord_name(runoff)].values),
            "runoffMm": (runoff.values.astype(float) * 1000.0),
            "petMm": abs(pet.values.astype(float) * 1000.0),
        })

    frame["month"] = frame["time"].dt.month
    monthly = frame.groupby("month", as_index=False).agg({"runoffMm": "mean", "petMm": "mean"})
    mean_runoff = max(1e-9, float(monthly["runoffMm"].mean()))
    monthly["runoffIndex"] = monthly["runoffMm"] / mean_runoff
    return monthly[["month", "runoffIndex", "petMm"]]


def _normalize_coords(ds):
    rename = {}
    if "lat" in ds.coords:
        rename["lat"] = "latitude"
    if "lon" in ds.coords:
        rename["lon"] = "longitude"
    if "valid_time" in ds.coords or "valid_time" in ds.dims:
        rename["valid_time"] = "time"
    if rename:
        ds = ds.rename(rename)
    if "longitude" in ds.coords and float(ds.longitude.max()) > 180:
        ds = ds.assign_coords(longitude=(((ds.longitude + 180) % 360) - 180)).sortby("longitude")
    return ds


def _find_var(ds, candidates: list[str]) -> str:
    for name in ds.data_vars:
        lower = name.lower()
        attrs = " ".join(str(v).lower() for v in ds[name].attrs.values())
        if any(candidate in lower or candidate in attrs for candidate in candidates):
            return name
    raise KeyError(f"could not find variable matching {candidates}; got {list(ds.data_vars)}")


def _time_column(frame: pd.DataFrame) -> str:
    for name in ["time", "valid_time", "hdate"]:
        if name in frame.columns:
            return name
    raise KeyError(f"could not find time column in {list(frame.columns)}")


def _time_coord_name(array) -> str:
    for name in ["time", "valid_time"]:
        if name in array.coords:
            return name
    raise KeyError(f"could not find time coord in {list(array.coords)}")


def _value(frame: pd.DataFrame, month: int, column: str) -> float:
    row = frame.loc[frame["month"] == month]
    if row.empty:
        raise ValueError(f"missing {column} for month {month}")
    return round(float(row.iloc[0][column]), 3)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build Copernicus baseline JSON for the draft simulator")
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("frontend/public/copernicus-baseline.json"),
    )
    args = parser.parse_args()
    print(build(start_year=args.start_year, end_year=args.end_year, out_path=args.out))
