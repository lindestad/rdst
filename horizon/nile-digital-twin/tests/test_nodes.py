import json

import pytest
import yaml

from dataloader.nodes import NODES, REACHES, build


def test_node_list_size_in_spec_range():
    assert 15 <= len(NODES) <= 20


def test_every_node_has_required_fields():
    for n in NODES:
        assert {"id", "name", "type", "country", "lat", "lon", "upstream", "downstream"}.issubset(n)
        assert n["type"] in {"source", "reservoir", "reach", "confluence", "wetland",
                             "demand_municipal", "demand_irrigation", "sink"}


def test_topology_is_acyclic_and_refers_to_real_nodes():
    ids = {n["id"] for n in NODES}
    for n in NODES:
        for u in n["upstream"]:
            assert u in ids, f"{n['id']} upstream references unknown node {u}"
        for d in n["downstream"]:
            assert d in ids, f"{n['id']} downstream references unknown node {d}"
    from graphlib import TopologicalSorter
    ts = TopologicalSorter({n["id"]: set(n["upstream"]) for n in NODES})
    list(ts.static_order())


def test_build_writes_valid_geojson_and_yaml(tmp_path, monkeypatch):
    import dataloader.config as cfg
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cfg, "NODES_GEOJSON", tmp_path / "nodes.geojson")
    monkeypatch.setattr(cfg, "NODE_CONFIG_YAML", tmp_path / "node_config.yaml")
    build(stub=False)
    gj = json.loads((tmp_path / "nodes.geojson").read_text())
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == len(NODES)
    cfg_out = yaml.safe_load((tmp_path / "node_config.yaml").read_text())
    assert set(cfg_out.keys()) == {"nodes", "reaches"}
    assert len(cfg_out["nodes"]) == len(NODES)
