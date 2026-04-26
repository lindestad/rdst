from __future__ import annotations

from nrsm_optimizer.objectives import compromise_weights, pareto_objectives


def test_pareto_objectives_minimize_regrets_shortages_and_spill() -> None:
    summary = {
        "total_energy_value": 80.0,
        "total_unmet_drink_water": -1.0,
        "total_unmet_food_water": 5.0,
        "total_spill": 2.0,
    }

    objectives = pareto_objectives(summary, baseline_energy_value=100.0)

    assert objectives.tolist() == [20.0, 0.0, 5.0, 2.0]


def test_pareto_objectives_can_include_storage_depletion() -> None:
    objectives = pareto_objectives(
        {"total_energy_value": 100.0},
        baseline_energy_value=100.0,
        initial_storage=100.0,
        terminal_storage=70.0,
    )

    assert objectives.tolist() == [0.0, 0.0, 0.0, 0.0, 30.0]


def test_compromise_weights_reflect_mode_priorities() -> None:
    objective_names = (
        "energy_regret",
        "unmet_drink_water",
        "unmet_food_water",
        "spill",
        "storage_depletion",
    )

    energy_food = compromise_weights(objective_names, "energy_food")
    storage_safe = compromise_weights(objective_names, "storage_safe")

    assert energy_food[0] > energy_food[-1]
    assert storage_safe[-1] > storage_safe[0]
