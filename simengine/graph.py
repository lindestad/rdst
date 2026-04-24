"""Graph loader: reads YAML config + topology and returns a topologically
ordered list of Node instances."""
from __future__ import annotations

import json
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any

import yaml

# Registry populated by simengine.nodes at import time
_NODE_CLASSES: dict[str, type] = {}


def register_node_class(type_name: str):
    def deco(cls):
        _NODE_CLASSES[type_name] = cls
        return cls
    return deco


@dataclass
class Graph:
    nodes: dict[str, Any]                # id -> Node instance
    order: list[str]                     # topological order (upstream first)
    upstream: dict[str, list[str]]
    downstream: dict[str, list[str]]


def load_graph(config_path: Path, topology_path: Path | None = None,
               geojson_path: Path | None = None) -> Graph:
    """Load graph from node_config.yaml + either a topology.json or nodes.geojson."""
    # Importing here avoids a circular import at module load time
    try:
        import simengine.nodes  # noqa: F401 -- triggers @register_node_class decorators
    except ModuleNotFoundError as e:
        # Tolerate simengine.nodes not existing yet (Task 2 runs before Task 3).
        # Re-raise if the missing module is anything else -- e.g. a typo in a
        # node submodule's own imports -- so we don't mask real bugs.
        if e.name != "simengine.nodes":
            raise

    cfg = yaml.safe_load(Path(config_path).read_text())
    nodes_cfg = cfg["nodes"]
    reaches_cfg = cfg.get("reaches", {})

    edges = _load_edges(topology_path, geojson_path)
    upstream: dict[str, list[str]] = {nid: [] for nid in nodes_cfg}
    downstream: dict[str, list[str]] = {nid: [] for nid in nodes_cfg}
    for u, d in edges:
        downstream.setdefault(u, []).append(d)
        upstream.setdefault(d, []).append(u)

    ts = TopologicalSorter({nid: set(upstream.get(nid, [])) for nid in nodes_cfg})
    try:
        order = list(ts.static_order())
    except CycleError as e:
        raise ValueError(f"topology contains a cycle: {e}")

    nodes: dict[str, Any] = {}
    for nid, nconf in nodes_cfg.items():
        ntype = nconf.get("type")
        if ntype not in _NODE_CLASSES:
            raise ValueError(f"unknown node type {ntype!r} for node {nid!r}")
        cls = _NODE_CLASSES[ntype]
        params = {k: v for k, v in nconf.items() if k != "type"}
        # Reach routing params may live in reaches_cfg instead of on the node
        if ntype == "reach" and nid in reaches_cfg:
            params = {**reaches_cfg[nid], **params}
        nodes[nid] = cls(id=nid, upstream=upstream.get(nid, []),
                         downstream=downstream.get(nid, []), **params)

    return Graph(nodes=nodes, order=order, upstream=upstream, downstream=downstream)


def _load_edges(topology_path: Path | None,
                geojson_path: Path | None) -> list[tuple[str, str]]:
    if topology_path and Path(topology_path).exists():
        obj = json.loads(Path(topology_path).read_text())
        return [tuple(e) for e in obj["edges"]]
    if geojson_path and Path(geojson_path).exists():
        gj = json.loads(Path(geojson_path).read_text())
        edges = []
        for feat in gj["features"]:
            nid = feat["properties"]["id"]
            for d in feat["properties"].get("downstream", []):
                edges.append((nid, d))
        return edges
    raise FileNotFoundError("need either topology_path or geojson_path")
