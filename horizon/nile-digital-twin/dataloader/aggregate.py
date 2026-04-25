"""Spatial crop + area-weighted mean + monthly resampling for ERA5 inputs."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from dataloader.penman import pet_mm_monthly

SPEC_COLUMNS = [
    "month", "precip_mm", "temp_c", "radiation_mj_m2",
    "wind_ms", "dewpoint_c", "pet_mm", "runoff_mm", "historical_discharge_m3s",
]


def crop_bbox(ds: xr.Dataset, lat_min, lat_max, lon_min, lon_max) -> xr.Dataset:
    return ds.where(
        (ds.latitude >= lat_min) & (ds.latitude <= lat_max) &
        (ds.longitude >= lon_min) & (ds.longitude <= lon_max),
        drop=True,
    )


def _spatial_mean(ds: xr.Dataset) -> xr.Dataset:
    """Cosine-latitude-weighted mean over the lat/lon dims."""
    weights = np.cos(np.deg2rad(ds.latitude))
    return ds.weighted(weights).mean(dim=("latitude", "longitude"))


def monthly_forcings_from_era5(
    source: Path | str | xr.Dataset, *, lat_min, lat_max, lon_min, lon_max,
) -> pd.DataFrame:
    """Crop to bbox, area-weighted spatial mean, monthly resample, compute
    derived fields (PET). `source` is either a NetCDF path or an in-memory
    xarray Dataset — production opens files, tests pass Datasets directly."""
    ds = source if isinstance(source, xr.Dataset) else xr.open_dataset(source)
    if "valid_time" in ds.coords or "valid_time" in ds.dims:
        ds = ds.rename({"valid_time": "time"})
    ds = crop_bbox(ds, lat_min, lat_max, lon_min, lon_max)
    ds = _spatial_mean(ds)

    # Unit conversions:
    precip_mm_day = ds["tp"] * 1000.0                   # m → mm
    temp_c = ds["t2m"] - 273.15                         # K → °C
    dew_c = ds["d2m"] - 273.15
    rad_mj_m2_day = ds["ssrd"] / 1e6                    # J/m² → MJ/m²
    if "si10" in ds:
        wind_ms = ds["si10"]
    else:
        wind_ms = np.hypot(ds["u10"], ds["v10"])
    runoff_mm_day = ds["ro"] * 1000.0                   # m → mm

    daily = xr.Dataset({
        "precip_mm": precip_mm_day,
        "temp_c": temp_c,
        "dewpoint_c": dew_c,
        "radiation_mj_m2": rad_mj_m2_day,
        "wind_ms": wind_ms,
        "runoff_mm": runoff_mm_day,
    })
    monthly_sum = daily[["precip_mm", "runoff_mm"]].resample(time="1MS").sum()
    monthly_mean = daily[["temp_c", "dewpoint_c", "radiation_mj_m2", "wind_ms"]].resample(time="1MS").mean()
    merged = xr.merge([monthly_sum, monthly_mean]).to_dataframe().reset_index().rename(columns={"time": "month"})

    days = merged["month"].dt.days_in_month.to_numpy()
    merged["pet_mm"] = pet_mm_monthly(
        temp_c=merged["temp_c"].to_numpy(),
        dewpoint_c=merged["dewpoint_c"].to_numpy(),
        radiation_mj_m2_day=merged["radiation_mj_m2"].to_numpy(),
        wind_ms=merged["wind_ms"].to_numpy(),
        days_in_month=days,
    )
    merged["historical_discharge_m3s"] = pd.NA
    return merged[SPEC_COLUMNS]
