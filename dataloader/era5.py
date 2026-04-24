"""Thin wrapper around cdsapi for ERA5 daily fetches.

cdsapi is lazy-imported inside the function so stub-mode tests/runs don't need
it installed. The team adds `cdsapi>=0.7` to pyproject when wiring the real
CDS pipeline.
"""
from __future__ import annotations

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
    """Download ERA5 daily NetCDF for bbox + date range. Cached on disk."""
    if out_path.exists():
        return out_path
    import cdsapi
    c = cdsapi.Client()
    years = list(range(int(start[:4]), int(end[:4]) + 1))
    months = [f"{m:02d}" for m in range(1, 13)]
    days = [f"{d:02d}" for d in range(1, 32)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c.retrieve(
        CDS_DATASET,
        {
            "product_type": "reanalysis",
            "variable": VARIABLES,
            "year": [str(y) for y in years],
            "month": months,
            "day": days,
            "daily_statistic": "daily_mean",
            "time_zone": "UTC+00:00",
            "frequency": "1_hourly",
            "area": list(bbox),
            "format": "netcdf",
        },
        str(out_path),
    )
    return out_path
