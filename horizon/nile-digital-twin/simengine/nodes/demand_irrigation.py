from simengine.crop_water import monthly_water_requirement_mm
from simengine.graph import register_node_class
from simengine.nodes.base import Node, days_in_month_from_ts, mcm_to_m3s_month


@register_node_class("demand_irrigation")
class DemandIrrigation(Node):
    def __init__(self, id, upstream, downstream, *,
                 area_ha_baseline, crop_water_productivity_kg_per_m3, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.area_ha_baseline = float(area_ha_baseline)
        self.productivity = float(crop_water_productivity_kg_per_m3)

    def step(self, t, state, *, policy=None):
        policy = policy or {}
        scale = float(policy.get("area_scale", 1.0))
        area_ha = self.area_ha_baseline * scale

        row = self.forcings.iloc[t]
        month_num = row["month"].month
        days = days_in_month_from_ts(row["month"])
        req_mm = monthly_water_requirement_mm(month_num)
        # mm × ha = 1e-3 m × 1e4 m² = 10 m³  → demand (m³) = req_mm × area_ha × 10
        demand_m3 = req_mm * area_ha * 10.0

        inflow_m3s = self.upstream_inflow_m3s(state)
        inflow_m3 = inflow_m3s * days * 86400.0
        delivered_m3 = min(demand_m3, inflow_m3)
        delivered_fraction = delivered_m3 / demand_m3 if demand_m3 > 0 else 1.0
        food_tonnes = (delivered_m3 * self.productivity) / 1000.0

        outflow_m3s = (inflow_m3 - delivered_m3) / (days * 86400.0)
        state[self.id] = {
            "outflow_m3s": outflow_m3s,
            "inflow_m3s": inflow_m3s,
            "demand_m3": demand_m3,
            "delivered_m3": delivered_m3,
            "delivered_m3s": delivered_m3 / (days * 86400.0),
            "delivered_fraction": delivered_fraction,
            "food_tonnes_month": food_tonnes,
        }
