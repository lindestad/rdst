from __future__ import annotations

import numpy as np

from nrsm_optimizer.actions import PiecewiseActionSpace
from nrsm_optimizer.pareto import append_full_production_candidate, seeded_sampling


def test_append_full_production_candidate_adds_selectable_baseline() -> None:
    action_space = PiecewiseActionSpace(
        node_ids=("a", "b"),
        horizon_days=4,
        interval_days=2,
        controlled_nodes=("a",),
    )
    variables = np.array([[0.5, 0.25]])
    objectives = np.array([[10.0, 0.0, 2.0, 0.0, 50.0]])
    summaries = [{"total_energy_value": 90.0}]
    labels = ["pareto"]
    baseline_summary = {
        "total_energy_value": 100.0,
        "initial_reservoir_storage": 1000.0,
        "terminal_reservoir_storage": 900.0,
    }

    variables, objectives, summaries, labels = append_full_production_candidate(
        variables,
        objectives,
        summaries,
        labels,
        action_space,
        baseline_summary,
        (
            "energy_regret",
            "unmet_drink_water",
            "unmet_food_water",
            "spill",
            "storage_depletion",
        ),
    )

    assert labels == ["pareto", "full_production_baseline"]
    assert variables[-1].tolist() == [1.0, 1.0]
    assert objectives[-1].tolist() == [0.0, 0.0, 0.0, 0.0, 100.0]
    assert summaries[-1] == baseline_summary


def test_seeded_sampling_starts_with_full_production() -> None:
    sampling = seeded_sampling(variable_count=3, population_size=5, seed=11)

    assert sampling.shape == (5, 3)
    assert sampling[0].tolist() == [1.0, 1.0, 1.0]
    assert ((sampling[1:] >= 0.0) & (sampling[1:] <= 1.0)).all()
