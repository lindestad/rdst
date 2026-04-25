import numpy as np
import pandas as pd

from simengine.nodes.reservoir import Reservoir


def _forcings(pet_mm=100.0, months=3):
    return pd.DataFrame({
        "month": pd.date_range("2020-01-01", periods=months, freq="MS"),
        "pet_mm": [pet_mm] * months,
    })


def test_mass_conservation_one_step():
    r = Reservoir(id="r", upstream=["u"], downstream=["d"],
                  storage_capacity_mcm=10000, storage_min_mcm=100,
                  surface_area_km2_at_full=10, initial_storage_mcm=500,
                  hep={"nameplate_mw": 100, "head_m": 50, "efficiency": 0.9})
    r.load_forcings(_forcings(pet_mm=0.0))
    # 1000 m³/s inflow for Jan (31 days) → 2678.4 mcm; no release set → default = inflow
    state = {"u": {"outflow_m3s": 1000.0}}
    r.step(0, state, policy={"mode": "manual", "release_m3s_by_month": {"2020-01": 500.0}})
    s = state["r"]
    # Inflow in mcm
    inflow_mcm = 1000 * 31 * 86400 / 1e6
    release_mcm = 500 * 31 * 86400 / 1e6
    # Storage change should equal inflow - release - evap (evap=0 because pet=0)
    assert abs(s["storage_mcm"] - (500 + inflow_mcm - release_mcm)) < 0.5


def test_storage_clamped_to_capacity():
    r = Reservoir(id="r", upstream=["u"], downstream=["d"],
                  storage_capacity_mcm=1000, storage_min_mcm=100,
                  surface_area_km2_at_full=10, initial_storage_mcm=990,
                  hep={"nameplate_mw": 100, "head_m": 50, "efficiency": 0.9})
    r.load_forcings(_forcings(pet_mm=0.0))
    state = {"u": {"outflow_m3s": 2000.0}}  # Huge inflow
    r.step(0, state, policy={"mode": "manual", "release_m3s_by_month": {"2020-01": 0.0}})
    s = state["r"]
    assert s["storage_mcm"] == 1000
    # Spilled volume must exit as outflow
    assert s["outflow_m3s"] > 0
    # Policy said release zero — turbined portion is zero, spill carries the flow.
    assert s["release_m3s"] == 0
    assert s["spill_m3s"] > 0


def test_spilled_water_does_not_generate_energy():
    # Reservoir nearly full with zero policy-release and huge inflow → all excess spills.
    # Spill must exit as outflow but contribute ZERO energy (spillway bypasses turbine).
    r = Reservoir(id="r", upstream=["u"], downstream=["d"],
                  storage_capacity_mcm=1000, storage_min_mcm=100,
                  surface_area_km2_at_full=10, initial_storage_mcm=990,
                  hep={"nameplate_mw": 100, "head_m": 50, "efficiency": 0.9})
    r.load_forcings(_forcings(pet_mm=0.0))
    state = {"u": {"outflow_m3s": 2000.0}}  # massive inflow
    r.step(0, state, policy={"mode": "manual", "release_m3s_by_month": {"2020-01": 0.0}})
    s = state["r"]
    assert s["release_m3s"] == 0                      # policy said release zero
    assert s["spill_m3s"] > 0                          # inflow forced spill
    assert s["outflow_m3s"] == s["spill_m3s"]          # total outflow IS the spill
    assert s["energy_gwh"] == 0.0                      # spillway = no turbine = no energy


def test_energy_generation():
    r = Reservoir(id="r", upstream=["u"], downstream=["d"],
                  storage_capacity_mcm=10000, storage_min_mcm=100,
                  surface_area_km2_at_full=10, initial_storage_mcm=2000,
                  hep={"nameplate_mw": 100, "head_m": 50, "efficiency": 0.9})
    r.load_forcings(_forcings(pet_mm=0.0))
    state = {"u": {"outflow_m3s": 0.0}}
    r.step(0, state, policy={"mode": "manual", "release_m3s_by_month": {"2020-01": 500.0}})
    # E = V × h × η × ρ × g / 3.6e12
    # V = 500 m³/s × 31 × 86400 = 1.3392e9 m³
    # E_gwh = 1.3392e9 × 50 × 0.9 × 1000 × 9.81 / 3.6e12 ≈ 164.3 GWh
    assert 160 < state["r"]["energy_gwh"] < 170


def test_evaporation_scales_with_surface_area_and_pet():
    r = Reservoir(id="r", upstream=["u"], downstream=["d"],
                  storage_capacity_mcm=1000, storage_min_mcm=100,
                  surface_area_km2_at_full=10, initial_storage_mcm=500,
                  hep={"nameplate_mw": 100, "head_m": 50, "efficiency": 0.9})
    # 100 mm/month × 10 km² at half-full (so area ≈ 5 km²) = 0.1 m × 5e6 m² = 5e5 m³ = 0.5 mcm
    r.load_forcings(_forcings(pet_mm=100.0))
    state = {"u": {"outflow_m3s": 0.0}}
    r.step(0, state, policy={"mode": "manual", "release_m3s_by_month": {"2020-01": 0.0}})
    # Evap should be 0.3–0.7 mcm (some area-vs-storage scaling applied)
    assert 0.2 < state["r"]["evap_mcm"] < 0.8
