import pandas as pd

from simengine.nodes.wetland import Wetland


def test_evap_fraction_is_lost():
    w = Wetland(id="sudd", upstream=["u"], downstream=["d"], evap_loss_fraction_baseline=0.5)
    w.load_forcings(pd.DataFrame({"month": pd.date_range("2020-01-01", periods=1, freq="MS"),
                                  "pet_mm": [150.0]}))
    state = {"u": {"outflow_m3s": 1000.0}}
    w.step(0, state)
    assert 450 <= state["sudd"]["outflow_m3s"] <= 550
    assert abs(state["sudd"]["evap_loss_fraction"] - 0.5) < 0.01
