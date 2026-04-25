import pandas as pd
import xarray as xr

from dataloader import config
from dataloader import nodes as nodes_mod
from dataloader.copernicus_csv import CATALOG_ROWS, _era5_node_dataframes_from_months, build


def test_stub_csv_bundle_writes_logical_folder_structure(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "CSV_DIR", tmp_path / "csv")
    monkeypatch.setattr(config, "NODES_GEOJSON", tmp_path / "nodes.geojson")
    monkeypatch.setattr(config, "NODE_CONFIG_YAML", tmp_path / "node_config.yaml")
    monkeypatch.setattr(config, "OVERLAYS_DIR", tmp_path / "overlays" / "ndvi")

    nodes_mod.build(stub=True)
    build(stub=True, profile="full", start="2005-01-01", end="2005-02-28")

    csv_root = tmp_path / "csv"
    expected_dirs = ["era5_daily", "era5_monthly", "era5_land_monthly", "glofas", "ndvi"]
    for name in expected_dirs:
        assert (csv_root / name).is_dir()

    assert (csv_root / "catalog.csv").exists()
    assert (csv_root / "nodes.csv").exists()
    assert (csv_root / "edges.csv").exists()

    daily_files = sorted((csv_root / "era5_daily").glob("*.csv"))
    assert len(daily_files) == 4
    daily = pd.read_csv(daily_files[0])
    assert {"date", "precip_mm_day", "temp_c", "runoff_mm_day", "quality_flag"}.issubset(
        daily.columns
    )
    assert len(daily) == 59

    monthly = pd.read_csv(sorted((csv_root / "era5_monthly").glob("*.csv"))[0])
    assert {"month", "precip_mm", "pet_mm", "runoff_mm"}.issubset(monthly.columns)
    assert len(monthly) == 2

    land = pd.read_csv(sorted((csv_root / "era5_land_monthly").glob("*.csv"))[0])
    assert {"potential_evaporation_mm", "soil_water_layer1_m3_m3"}.issubset(land.columns)

    glofas = pd.read_csv(sorted((csv_root / "glofas").glob("*.csv"))[0])
    assert {"date", "river_discharge_m3s"}.issubset(glofas.columns)


def test_catalog_documents_broad_copernicus_sources():
    dataset_ids = {row["dataset_id"] for row in CATALOG_ROWS}

    assert "era5_daily_surface" in dataset_ids
    assert "era5_land_monthly_hydro" in dataset_ids
    assert "glofas_historical_discharge" in dataset_ids
    assert "sentinel2_ndvi_zones" in dataset_ids
    assert "clms_evapotranspiration" in dataset_ids
    assert "clms_dynamic_land_cover" in dataset_ids
    assert "clms_water_bodies" in dataset_ids
    assert "fao_wapor" in dataset_ids
    assert "fao_aquastat" in dataset_ids
    assert "nile_basin_information_systems" in dataset_ids
    assert "galileo_rinex_navigation" in dataset_ids
    assert "igs_mgex" in dataset_ids
    assert "cddis_gnss_daily" in dataset_ids


def test_shared_era5_month_file_can_feed_node_csvs(tmp_path):
    times = pd.date_range("2005-01-01", periods=2, freq="D")
    lat = [0.0, 1.0]
    lon = [32.0, 33.0]
    shape = (len(times), len(lat), len(lon))
    ds = xr.Dataset(
        {
            "tp": (("time", "latitude", "longitude"), 0.001 * _ones(shape)),
            "t2m": (("time", "latitude", "longitude"), 295.0 * _ones(shape)),
            "d2m": (("time", "latitude", "longitude"), 285.0 * _ones(shape)),
            "ssrd": (("time", "latitude", "longitude"), 18_000_000.0 * _ones(shape)),
            "u10": (("time", "latitude", "longitude"), 2.0 * _ones(shape)),
            "v10": (("time", "latitude", "longitude"), 1.0 * _ones(shape)),
            "ro": (("time", "latitude", "longitude"), 0.0001 * _ones(shape)),
        },
        coords={"time": times, "latitude": lat, "longitude": lon},
    )
    path = tmp_path / "era5_daily_2005_01.nc"
    ds.to_netcdf(path)

    daily, monthly = _era5_node_dataframes_from_months(
        [path],
        bbox=(1.5, 31.5, -0.5, 33.5),
    )

    assert len(daily) == 2
    assert daily["precip_mm_day"].round(3).tolist() == [1.0, 1.0]
    assert len(monthly) == 1
    assert round(float(monthly["precip_mm"].iloc[0]), 3) == 2.0


def _ones(shape):
    import numpy as np

    return np.ones(shape)
