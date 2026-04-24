"""L1 + L2 end-to-end: dataloader stub -> simengine run -> valid scenario."""
from __future__ import annotations

import json
from pathlib import Path

from dataloader import config as dl_config
from dataloader import forcings as dl_forcings
from dataloader import nodes as dl_nodes
from dataloader import overlays as dl_overlays
from simengine.engine import run
from simengine.scenario import Scenario


def test_stub_dataloader_feeds_simengine(tmp_path, monkeypatch):
    # Point the dataloader at a temp tree and run the full stub pipeline.
    monkeypatch.setattr(dl_config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dl_config, "TIMESERIES_DIR", tmp_path / "timeseries")
    monkeypatch.setattr(dl_config, "OVERLAYS_DIR", tmp_path / "overlays" / "ndvi")
    monkeypatch.setattr(dl_config, "NODES_GEOJSON", tmp_path / "nodes.geojson")
    monkeypatch.setattr(dl_config, "NODE_CONFIG_YAML", tmp_path / "node_config.yaml")
    dl_nodes.build(stub=True)
    dl_forcings.build(stub=True)
    dl_overlays.build(stub=True)

    # Construct a minimal scenario and run simengine against the stub data.
    scenario = Scenario(
        name="baseline-stub",
        period=["2005-01", "2024-12"],
        policy={"reservoirs": {}, "demands": {}, "constraints": {},
                "weights": {"water": 0.4, "food": 0.3, "energy": 0.3}},
    )
    result = run(
        scenario,
        config_path=tmp_path / "node_config.yaml",
        geojson_path=tmp_path / "nodes.geojson",
        timeseries_dir=tmp_path / "timeseries",
    )

    assert result.results is not None
    assert len(result.results.kpi_monthly) == 240   # 2005-01 .. 2024-12
    assert set(result.results.timeseries_per_node.keys()) == {
        "stub_source", "stub_reach", "stub_reservoir", "stub_sink"
    }
    # Reservoir storage should oscillate within [min, capacity] — never pinned
    storage = [row["storage_mcm"] for row in result.results.timeseries_per_node["stub_reservoir"]]
    assert min(storage) > 1000            # stub min
    assert max(storage) < 10000           # stub capacity
    # HEP produced nonzero energy overall
    total_gwh = sum(row["energy_gwh"] for row in result.results.timeseries_per_node["stub_reservoir"])
    assert total_gwh > 1000               # 1 GW nameplate * 20 years * some fraction
    # Score is sane
    assert 0.0 <= result.results.score <= 1.0
