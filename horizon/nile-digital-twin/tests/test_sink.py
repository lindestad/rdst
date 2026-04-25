import pandas as pd

from simengine.nodes.sink import Sink


def test_sink_no_shortfall_when_inflow_meets_min():
    s = Sink(id="snk", upstream=["u"], downstream=[], min_environmental_flow_m3s=100.0)
    state = {"u": {"outflow_m3s": 150.0}}
    s.step(0, state)
    assert state["snk"]["outflow_m3s"] == 0.0
    assert state["snk"]["inflow_m3s"] == 150.0
    assert state["snk"]["shortfall_m3s"] == 0.0


def test_sink_shortfall_when_inflow_below_min():
    s = Sink(id="snk", upstream=["u"], downstream=[], min_environmental_flow_m3s=500.0)
    state = {"u": {"outflow_m3s": 200.0}}
    s.step(0, state)
    assert state["snk"]["shortfall_m3s"] == 300.0


def test_sink_sums_multiple_upstream():
    s = Sink(id="snk", upstream=["a", "b"], downstream=[], min_environmental_flow_m3s=0.0)
    state = {"a": {"outflow_m3s": 50.0}, "b": {"outflow_m3s": 30.0}}
    s.step(0, state)
    assert state["snk"]["inflow_m3s"] == 80.0


def test_sink_tolerates_missing_upstream_in_state():
    """If topological sort / partial state means an upstream hasn't stepped yet,
    upstream_inflow_m3s silently treats it as 0 rather than raising KeyError."""
    s = Sink(id="snk", upstream=["a", "b"], downstream=[], min_environmental_flow_m3s=0.0)
    state = {"a": {"outflow_m3s": 50.0}}   # "b" absent
    s.step(0, state)
    assert state["snk"]["inflow_m3s"] == 50.0
