import pandas as pd

from dataloader import config
from dataloader import nodes as nodes_mod
from dataloader.overlays import NDVI_SPEC_COLUMNS, build


def test_stub_build_writes_one_parquet_per_zone(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "OVERLAYS_DIR", tmp_path / "overlays" / "ndvi")
    build(stub=True)
    files = list((tmp_path / "overlays" / "ndvi").glob("*.parquet"))
    assert len(files) == len(nodes_mod.NDVI_ZONES)
    df = pd.read_parquet(files[0])
    assert list(df.columns) == NDVI_SPEC_COLUMNS
    assert (df["ndvi_mean"].between(-1, 1)).all()
    assert (df["valid_pixel_frac"].between(0, 1)).all()
    assert len(df) == 240
