import pandas as pd

from dataloader import config
from dataloader import nodes as nodes_mod
from dataloader.copernicus_csv import CATALOG_ROWS, build


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
