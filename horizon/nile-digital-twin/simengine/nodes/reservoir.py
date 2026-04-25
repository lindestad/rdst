"""Reservoir node: mass balance + HEP + Penman evap × storage-scaled area."""
from __future__ import annotations

from simengine.graph import register_node_class
from simengine.nodes.base import Node, days_in_month_from_ts, m3s_to_mcm_month, mcm_to_m3s_month

RHO = 1000.0      # kg/m³
G = 9.81          # m/s²


@register_node_class("reservoir")
class Reservoir(Node):
    def __init__(self, id, upstream, downstream, *,
                 storage_capacity_mcm, storage_min_mcm,
                 surface_area_km2_at_full, initial_storage_mcm,
                 hep=None, **_ignored):
        super().__init__(id=id, upstream=upstream, downstream=downstream)
        self.capacity = float(storage_capacity_mcm)
        self.min = float(storage_min_mcm)
        self.area_full = float(surface_area_km2_at_full)
        self.storage = float(initial_storage_mcm)
        self.hep = hep  # None for dams without HEP

    def step(self, t, state, *, policy=None):
        policy = policy or {}
        row = self.forcings.iloc[t] if len(self.forcings) else None
        pet_mm = float(row["pet_mm"]) if row is not None else 0.0
        month_key = row["month"].strftime("%Y-%m") if row is not None else None
        days = days_in_month_from_ts(row["month"]) if row is not None else 30

        inflow_m3s = self.upstream_inflow_m3s(state)
        inflow_mcm = m3s_to_mcm_month(inflow_m3s, days)

        release_m3s = self._desired_release(policy, month_key, inflow_m3s)
        release_mcm = m3s_to_mcm_month(release_m3s, days)

        # Surface area scales linearly with storage (crude but OK)
        area_km2 = self.area_full * (self.storage / self.capacity) if self.capacity else 0.0
        evap_mcm = pet_mm * area_km2 * 1e-3  # mm × km² × 1e-3 = mcm

        new_storage = self.storage + inflow_mcm - release_mcm - evap_mcm

        # Clamp + spill
        spilled_mcm = max(0.0, new_storage - self.capacity)
        new_storage = min(self.capacity, new_storage)
        if new_storage < self.min:
            # Reduce release to keep storage at min (can't release what we don't have)
            deficit = self.min - new_storage
            release_mcm = max(0.0, release_mcm - deficit)
            new_storage = self.min

        # Turbined volume = controlled release AFTER min-guard, BEFORE adding spill.
        # Spillways bypass the turbines, so spilled water produces no energy.
        turbine_mcm = release_mcm
        total_out_mcm = turbine_mcm + spilled_mcm
        outflow_m3s = mcm_to_m3s_month(total_out_mcm, days)

        energy_gwh = 0.0
        if self.hep:
            # Energy comes from the turbined (controlled) release only.
            # Spilled water exits via the spillway and bypasses the turbines.
            turbine_m3 = turbine_mcm * 1e6
            head = float(self.hep["head_m"])
            eff = float(self.hep["efficiency"])
            energy_j = turbine_m3 * head * eff * RHO * G
            energy_gwh = energy_j / 3.6e12

        self.storage = new_storage
        state[self.id] = {
            "outflow_m3s": outflow_m3s,
            "inflow_m3s": inflow_m3s,
            "storage_mcm": new_storage,
            "release_m3s": mcm_to_m3s_month(turbine_mcm, days),
            "spill_m3s": mcm_to_m3s_month(spilled_mcm, days),
            "evap_mcm": evap_mcm,
            "energy_gwh": energy_gwh,
        }

    def _desired_release(self, policy, month_key, inflow_m3s) -> float:
        mode = policy.get("mode", "historical")
        if mode == "manual":
            mapping = policy.get("release_m3s_by_month", {})
            if month_key in mapping:
                return float(mapping[month_key])
            return inflow_m3s  # pass-through default
        if mode == "rule_curve":
            # Simple linear rule: release proportional to fractional storage
            frac = (self.storage - self.min) / max(1.0, self.capacity - self.min)
            return inflow_m3s * (0.5 + frac)
        # historical default: pass inflow through (plus any tiny draw-down from policy)
        return inflow_m3s
