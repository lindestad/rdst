import pandas as pd

from simengine.nodes.reach import Reach


def _forcings(n=5):
    return pd.DataFrame({"month": pd.date_range("2020-01-01", periods=n, freq="MS"),
                         "pet_mm": [0.0] * n})


def test_steady_state_passthrough():
    r = Reach(id="r", upstream=["u"], downstream=["d"],
              travel_time_months=1.0, muskingum_k=1.0, muskingum_x=0.2)
    r.load_forcings(_forcings())
    state = {"u": {"outflow_m3s": 500.0}}
    # Warm up: feed same inflow enough times for outflow to converge
    for t in range(50):
        r.step(t, state)
    assert abs(state["r"]["outflow_m3s"] - 500.0) < 1.0


def test_pulse_attenuation():
    r = Reach(id="r", upstream=["u"], downstream=["d"],
              travel_time_months=1.0, muskingum_k=1.0, muskingum_x=0.2)
    r.load_forcings(_forcings())
    state = {"u": {"outflow_m3s": 0.0}}
    r.step(0, state)
    state["u"]["outflow_m3s"] = 1000.0
    r.step(1, state)
    peak1 = state["r"]["outflow_m3s"]
    state["u"]["outflow_m3s"] = 0.0
    r.step(2, state)
    peak2 = state["r"]["outflow_m3s"]
    # Peak attenuated below input, and some flow persists after pulse passes
    assert peak1 < 1000.0
    assert peak2 > 0.0
