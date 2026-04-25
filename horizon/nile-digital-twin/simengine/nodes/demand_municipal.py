from simengine.graph import register_node_class
from simengine.nodes.base import Node, days_in_month_from_ts


@register_node_class("demand_municipal")
class DemandMunicipal(Node):
    def __init__(self, id, upstream, downstream, *,
                 population_baseline, per_capita_l_day, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.population = float(population_baseline)
        self.per_capita_l_day = float(per_capita_l_day)

    def step(self, t, state, *, policy=None):
        policy = policy or {}
        pop = self.population * float(policy.get("population_scale", 1.0))

        row = self.forcings.iloc[t]
        days = days_in_month_from_ts(row["month"])
        demand_m3 = pop * self.per_capita_l_day * days / 1000.0

        inflow_m3s = self.upstream_inflow_m3s(state)
        inflow_m3 = inflow_m3s * days * 86400.0
        delivered_m3 = min(demand_m3, inflow_m3)
        served_pct = delivered_m3 / demand_m3 if demand_m3 > 0 else 1.0
        outflow_m3s = (inflow_m3 - delivered_m3) / (days * 86400.0)
        state[self.id] = {
            "outflow_m3s": outflow_m3s,
            "inflow_m3s": inflow_m3s,
            "demand_m3": demand_m3,
            "delivered_m3": delivered_m3,
            "served_pct": served_pct,
            "population_served": pop * served_pct,
        }
