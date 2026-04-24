import json
from pathlib import Path

import pytest

from simengine.scenario import Scenario


def test_load_minimal_scenario(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({
        "name": "x",
        "period": ["2005-01", "2024-12"],
        "policy": {"reservoirs": {}, "demands": {}, "constraints": {}, "weights": {
            "water": 0.4, "food": 0.3, "energy": 0.3}},
    }))
    s = Scenario.from_file(p)
    assert s.name == "x"
    assert s.policy.weights.water == 0.4


def test_weights_must_sum_to_one():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Scenario(name="x", period=["2005-01", "2024-12"],
                 policy={"reservoirs": {}, "demands": {}, "constraints": {},
                         "weights": {"water": 0.5, "food": 0.3, "energy": 0.3}})


def test_round_trip_to_file(tmp_path):
    s = Scenario(
        name="t", period=["2020-01", "2020-12"],
        policy={"reservoirs": {}, "demands": {}, "constraints": {},
                "weights": {"water": 0.4, "food": 0.3, "energy": 0.3}},
    )
    p = tmp_path / "out.json"
    s.to_file(p)
    loaded = Scenario.from_file(p)
    assert loaded.name == "t"
