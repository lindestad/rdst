from simengine.graph import register_node_class
from simengine.nodes.base import Node


@register_node_class("wetland")
class Wetland(Node):
    def __init__(self, id, upstream, downstream, *, evap_loss_fraction_baseline=0.5, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.loss = float(evap_loss_fraction_baseline)

    def step(self, t, state):
        inflow = self.upstream_inflow_m3s(state)
        out = inflow * (1.0 - self.loss)
        state[self.id] = {
            "outflow_m3s": out,
            "inflow_m3s": inflow,
            "evap_loss_fraction": self.loss,
        }
