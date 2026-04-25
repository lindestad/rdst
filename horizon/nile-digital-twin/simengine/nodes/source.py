from __future__ import annotations

from simengine.graph import register_node_class
from simengine.nodes.base import Node, days_in_month_from_ts


@register_node_class("source")
class Source(Node):
    def __init__(self, id, upstream, downstream, *, catchment_area_km2: float,
                 catchment_scale: float = 1.0, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.catchment_area_km2 = catchment_area_km2
        self.catchment_scale = catchment_scale

    def step(self, t, state):
        row = self.forcings.iloc[t]
        runoff_mm = float(row["runoff_mm"])
        days = days_in_month_from_ts(row["month"])
        # mm × km² = 1e-3 m × 1e6 m² = 1e3 m³  →  per-month m³ = runoff_mm × area_km2 × 1e3
        monthly_m3 = runoff_mm * self.catchment_area_km2 * 1e3 * self.catchment_scale
        outflow_m3s = monthly_m3 / (days * 86400.0)
        state[self.id] = {"outflow_m3s": outflow_m3s, "runoff_mm": runoff_mm}
