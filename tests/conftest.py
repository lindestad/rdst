import numpy as np
import pandas as pd
import pytest
import xarray as xr


@pytest.fixture(scope="session")
def era5_mini_ds():
    """In-memory ERA5-shaped Dataset: 2x3x3 grid, 2 months daily, 6 variables.

    Kept in memory rather than written to NetCDF because netcdf4/h5netcdf are
    heavy install deps we don't need for stub-mode tests. Real data fetches
    read from disk via xr.open_dataset in production.
    """
    time = pd.date_range("2020-01-01", "2020-02-29", freq="D")
    lat = np.array([14.5, 15.0, 15.5])
    lon = np.array([32.5, 33.0, 33.5])
    rng = np.random.default_rng(0)
    shape = (len(time), len(lat), len(lon))
    return xr.Dataset(
        {
            "tp":   (("time", "latitude", "longitude"), rng.uniform(0, 0.005, shape)),
            "t2m":  (("time", "latitude", "longitude"), 298.0 + rng.normal(0, 2, shape)),
            "d2m":  (("time", "latitude", "longitude"), 288.0 + rng.normal(0, 2, shape)),
            "ssrd": (("time", "latitude", "longitude"), rng.uniform(1.5e7, 2.5e7, shape)),
            "si10": (("time", "latitude", "longitude"), rng.uniform(1.5, 4.0, shape)),
            "ro":   (("time", "latitude", "longitude"), rng.uniform(0, 0.0005, shape)),
        },
        coords={"time": time, "latitude": lat, "longitude": lon},
    )
