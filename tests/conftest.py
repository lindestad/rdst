import json

import numpy as np
import pandas as pd
import pytest
import xarray as xr
import yaml


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


_API_TEST_PREFIXES = (
    "test_health", "test_nodes_route", "test_overlays_route",
    "test_scenarios_route", "test_scenario_store",
)


@pytest.fixture(autouse=True)
def _api_data_dir(tmp_path, monkeypatch, request):
    """For API tests only: build a fresh data/ tree with 2 nodes + 2-month parquets
    and point NILE_DATA_DIR at it. Other tests opt out by file name."""
    if not request.node.fspath.basename.startswith(_API_TEST_PREFIXES):
        yield
        return

    d = tmp_path / "data"
    (d / "timeseries").mkdir(parents=True)
    (d / "overlays" / "ndvi").mkdir(parents=True)
    (d / "scenarios").mkdir()

    gj = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [33.0, 0.4]},
             "properties": {"id": "lake_victoria_outlet", "name": "L. Victoria",
                            "type": "source", "country": "UG",
                            "upstream": [], "downstream": ["gerd"]}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [35.1, 11.2]},
             "properties": {"id": "gerd", "name": "GERD",
                            "type": "reservoir", "country": "ET",
                            "upstream": ["lake_victoria_outlet"], "downstream": []}},
        ],
    }
    (d / "nodes.geojson").write_text(json.dumps(gj))

    cfg = {
        "nodes": {
            "lake_victoria_outlet": {"type": "source", "catchment_area_km2": 100000,
                                     "catchment_scale": 1.0},
            "gerd": {"type": "reservoir", "storage_capacity_mcm": 74000,
                     "storage_min_mcm": 14800, "surface_area_km2_at_full": 1874,
                     "initial_storage_mcm": 14800,
                     "hep": {"nameplate_mw": 6450, "head_m": 133, "efficiency": 0.9}},
        },
        "reaches": {},
    }
    (d / "node_config.yaml").write_text(yaml.safe_dump(cfg))

    for nid in ("lake_victoria_outlet", "gerd"):
        df = pd.DataFrame({
            "month": pd.date_range("2020-01-01", periods=2, freq="MS"),
            "precip_mm": [50.0, 60.0], "temp_c": [25.0, 26.0],
            "radiation_mj_m2": [20.0, 22.0], "wind_ms": [2.0, 2.1],
            "dewpoint_c": [15.0, 16.0], "pet_mm": [150.0, 160.0],
            "runoff_mm": [10.0, 12.0], "historical_discharge_m3s": pd.NA,
        })
        df.to_parquet(d / "timeseries" / f"{nid}.parquet", index=False)

    ndf = pd.DataFrame({
        "month": pd.date_range("2020-01-01", periods=2, freq="MS"),
        "ndvi_mean": [0.3, 0.4], "ndvi_std": [0.05, 0.06],
        "valid_pixel_frac": [0.9, 0.85],
    })
    ndf.to_parquet(d / "overlays" / "ndvi" / "gezira.parquet", index=False)

    monkeypatch.setenv("NILE_DATA_DIR", str(d))
    import api.deps as deps
    deps.DATA_DIR = d
    deps.nodes_geojson.cache_clear()
    deps.node_config.cache_clear()
    yield d
