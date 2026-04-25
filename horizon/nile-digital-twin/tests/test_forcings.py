import pandas as pd

from dataloader import config
from dataloader import nodes as nodes_mod
from dataloader.aggregate import SPEC_COLUMNS
from dataloader.forcings import build


def test_stub_build_produces_parquet_per_node(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TIMESERIES_DIR", tmp_path / "timeseries")
    monkeypatch.setattr(config, "NODES_GEOJSON", tmp_path / "nodes.geojson")
    monkeypatch.setattr(config, "NODE_CONFIG_YAML", tmp_path / "node_config.yaml")
    nodes_mod.build(stub=True)
    build(stub=True)

    files = sorted((tmp_path / "timeseries").glob("*.parquet"))
    # 4 stub nodes from dataloader.nodes._stub_nodes
    assert len(files) == 4
    df = pd.read_parquet(files[0])
    assert list(df.columns) == SPEC_COLUMNS
    assert len(df) == 240
    assert df["month"].dt.year.min() == 2005
    assert df["month"].dt.year.max() == 2024
    # Synthetic data should respect non-negativity on precip/runoff
    assert (df["precip_mm"] >= 0).all()
    assert (df["runoff_mm"] >= 0).all()
