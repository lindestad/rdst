"""Thin wrapper around cdsapi for ERA5 daily fetches."""
from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

CDS_DATASET = "derived-era5-single-levels-daily-statistics"
VARIABLES = [
    "total_precipitation",
    "2m_temperature",
    "2m_dewpoint_temperature",
    "surface_solar_radiation_downwards",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "runoff",
]


def fetch_era5_daily(
    bbox: tuple[float, float, float, float],   # (lat_max, lon_min, lat_min, lon_max) -- CDS order
    start: str,
    end: str,
    out_path: Path,
) -> Path:
    """Download ERA5 daily NetCDF for bbox + date range. Cached on disk.

    CDS rejects the full 20-year request for this project as too expensive, so
    fetch month-by-month and stitch locally.
    """
    if out_path.exists():
        return out_path
    import cdsapi
    import xarray as xr

    c = cdsapi.Client()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    chunk_dir = out_path.parent / f".{out_path.stem}_chunks"
    chunk_dir.mkdir(parents=True, exist_ok=True)

    month_paths: list[Path] = []
    for year, month, days in _iter_month_requests(start, end):
        month_path = chunk_dir / f"{out_path.stem}_{year}_{month}.nc"
        month_paths.append(month_path)
        if month_path.exists():
            continue
        variable_paths = []
        for variable in VARIABLES:
            variable_path = chunk_dir / f"{out_path.stem}_{year}_{month}_{variable}.nc"
            variable_paths.append(variable_path)
            if variable_path.exists():
                continue
            print(
                f"fetching ERA5 {out_path.stem} {year}-{month} {variable}",
                flush=True,
            )
            c.retrieve(
                CDS_DATASET,
                {
                    "product_type": "reanalysis",
                    "variable": [variable],
                    "year": [year],
                    "month": [month],
                    "day": days,
                    "daily_statistic": "daily_mean",
                    "time_zone": "UTC+00:00",
                    "frequency": "1_hourly",
                    "area": list(bbox),
                    "format": "netcdf",
                },
                str(variable_path),
            )
        _merge_variable_chunks(variable_paths, month_path)

    datasets = []
    merged = None
    try:
        datasets = [_open_era5_dataset(path) for path in month_paths]
        merged = xr.concat(datasets, dim="time").sortby("time")
        merged.to_netcdf(out_path)
    finally:
        if merged is not None:
            merged.close()
        for ds in datasets:
            ds.close()

    return out_path


def _merge_variable_chunks(variable_paths: list[Path], out_path: Path) -> None:
    import xarray as xr

    datasets = []
    merged = None
    try:
        datasets = [_open_era5_dataset(path) for path in variable_paths]
        merged = xr.merge(datasets, compat="override").load()
        merged.to_netcdf(out_path)
    finally:
        if merged is not None:
            merged.close()
        for ds in datasets:
            ds.close()


def _open_era5_dataset(path: Path):
    import xarray as xr

    ds = xr.open_dataset(path)
    if "valid_time" in ds.coords or "valid_time" in ds.dims:
        ds = ds.rename({"valid_time": "time"})
    return ds


def _iter_month_requests(start: str, end: str) -> list[tuple[str, str, list[str]]]:
    start_month = date.fromisoformat(start[:10]).replace(day=1)
    end_month = date.fromisoformat(end[:10]).replace(day=1)
    out: list[tuple[str, str, list[str]]] = []
    current = start_month
    while current <= end_month:
        year = f"{current.year:04d}"
        month = f"{current.month:02d}"
        n_days = calendar.monthrange(current.year, current.month)[1]
        out.append((year, month, [f"{day:02d}" for day in range(1, n_days + 1)]))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return out
