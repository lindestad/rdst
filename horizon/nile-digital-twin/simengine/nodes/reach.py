"""Reach node with Muskingum routing (monthly Δt)."""
from __future__ import annotations

from simengine.graph import register_node_class
from simengine.nodes.base import Node


@register_node_class("reach")
class Reach(Node):
    def __init__(self, id, upstream, downstream, *,
                 travel_time_months=1.0, muskingum_k=1.0, muskingum_x=0.2, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        K = float(muskingum_k)
        x = float(muskingum_x)
        dt = 1.0  # monthly step
        denom = 2.0 * K * (1.0 - x) + dt
        self.C0 = (dt - 2.0 * K * x) / denom
        self.C1 = (dt + 2.0 * K * x) / denom
        self.C2 = (2.0 * K * (1.0 - x) - dt) / denom
        self._prev_in = 0.0
        self._prev_out = 0.0

    def step(self, t, state):
        inflow = self.upstream_inflow_m3s(state)
        out = self.C0 * inflow + self.C1 * self._prev_in + self.C2 * self._prev_out
        out = max(0.0, out)  # no negative flows
        self._prev_in = inflow
        self._prev_out = out
        state[self.id] = {"outflow_m3s": out, "inflow_m3s": inflow}
