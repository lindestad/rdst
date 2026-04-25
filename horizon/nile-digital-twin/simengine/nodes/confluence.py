from simengine.graph import register_node_class
from simengine.nodes.base import Node


@register_node_class("confluence")
class Confluence(Node):
    def __init__(self, id, upstream, downstream, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)

    def step(self, t, state):
        inflow = self.upstream_inflow_m3s(state)
        state[self.id] = {"outflow_m3s": inflow, "inflow_m3s": inflow}
