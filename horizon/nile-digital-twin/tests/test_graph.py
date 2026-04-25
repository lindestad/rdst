from pathlib import Path

import pytest

from simengine.graph import Graph, load_graph

FIX = Path(__file__).parent / "fixtures"


def test_topological_order():
    g = load_graph(FIX / "three_node_config.yaml", FIX / "three_node_topology.json")
    assert g.order == ["src", "res", "snk"]


def test_cycle_detection(tmp_path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("nodes:\n  a: {type: source, catchment_area_km2: 1, catchment_scale: 1}\n"
                   "  b: {type: sink, min_environmental_flow_m3s: 0}\n")
    topo = tmp_path / "topo.json"
    topo.write_text('{"edges": [["a","b"],["b","a"]]}')
    with pytest.raises(ValueError, match="cycle"):
        load_graph(cfg, topo)


def test_unknown_node_type(tmp_path):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("nodes:\n  x: {type: alien}\n")
    topo = tmp_path / "topo.json"
    topo.write_text('{"edges": []}')
    with pytest.raises(ValueError, match="unknown node type"):
        load_graph(cfg, topo)
