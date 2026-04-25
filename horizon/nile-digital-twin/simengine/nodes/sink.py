from __future__ import annotations

from simengine.graph import register_node_class
from simengine.nodes.base import Node


@register_node_class("sink")
class Sink(Node):
    def __init__(self, id, upstream, downstream, *, min_environmental_flow_m3s: float = 0.0,
                 **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.min_environmental_flow_m3s = min_environmental_flow_m3s

    def step(self, t, state):
        inflow = self.upstream_inflow_m3s(state)
        state[self.id] = {
            "outflow_m3s": 0.0,
            "inflow_m3s": inflow,
            "shortfall_m3s": max(0.0, self.min_environmental_flow_m3s - inflow),
        }
