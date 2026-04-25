from __future__ import annotations

from nrsm_optimizer.objectives import pareto_objectives


def test_pareto_objectives_minimize_regrets_shortages_and_spill() -> None:
    summary = {
        "total_energy_value": 80.0,
        "total_unmet_drink_water": -1.0,
        "total_unmet_food_water": 5.0,
        "total_spill": 2.0,
    }

    objectives = pareto_objectives(summary, baseline_energy_value=100.0)

    assert objectives.tolist() == [20.0, 0.0, 5.0, 2.0]
