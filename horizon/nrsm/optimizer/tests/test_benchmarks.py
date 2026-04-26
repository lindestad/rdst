from __future__ import annotations

import numpy as np
import pandas as pd

from nrsm_optimizer.benchmarks import (
    BenchmarkRun,
    inflow_proxy_actions,
    read_action_matrix,
    storage_guardrail_actions,
    write_action_matrix,
    write_benchmark_summary,
)


def sample_result() -> dict:
    return {
        "periods": [
            {
                "period_index": 0,
                "start_day": 0,
                "end_day_exclusive": 1,
                "node_results": [
                    {
                        "node_id": "a",
                        "total_inflow": 10.0,
                        "production_release": 20.0,
                        "reservoir_level": 100.0,
                    },
                    {
                        "node_id": "b",
                        "total_inflow": 40.0,
                        "production_release": 40.0,
                        "reservoir_level": 20.0,
                    },
                ],
            },
            {
                "period_index": 1,
                "start_day": 1,
                "end_day_exclusive": 2,
                "node_results": [
                    {
                        "node_id": "a",
                        "total_inflow": 30.0,
                        "production_release": 10.0,
                        "reservoir_level": 30.0,
                    },
                    {
                        "node_id": "b",
                        "total_inflow": 20.0,
                        "production_release": 20.0,
                        "reservoir_level": 80.0,
                    },
                ],
            },
        ]
    }


def test_inflow_proxy_actions_follow_inflow_over_observed_release() -> None:
    actions = inflow_proxy_actions(sample_result(), ("a", "b"))

    assert actions.tolist() == [[0.5, 1.0], [1.0, 0.5]]


def test_storage_guardrail_actions_reduce_low_storage_nodes() -> None:
    actions = storage_guardrail_actions(
        sample_result(),
        ("a", "b"),
        low_fraction=0.25,
        high_fraction=0.75,
        low_action=0.2,
        high_action=1.0,
    )

    assert actions[0, 0] == 1.0
    assert actions[0, 1] == 0.2
    assert actions[1, 0] > 0.2
    assert actions[1, 1] == 1.0


def test_action_matrix_round_trip(tmp_path) -> None:
    matrix = np.array([[0.1, 0.2], [0.3, 0.4]])

    write_action_matrix(matrix, ("a", "b"), tmp_path, None)
    loaded = read_action_matrix(tmp_path, ("a", "b"), 2, column="action")

    assert loaded.tolist() == matrix.tolist()


def test_benchmark_summary_writes_deltas_and_reliability(tmp_path) -> None:
    runs = [
        BenchmarkRun(
            name="full_production",
            description="baseline",
            summary={
                "total_energy_value": 10.0,
                "total_food_water_met": 8.0,
                "total_food_water_demand": 10.0,
                "total_drink_water_met": 5.0,
                "total_unmet_drink_water": 0.0,
            },
            actions_dir=tmp_path / "full" / "actions",
            results_dir=tmp_path / "full" / "results",
        ),
        BenchmarkRun(
            name="optimized",
            description="optimized",
            summary={
                "total_energy_value": 12.0,
                "total_food_water_met": 9.0,
                "total_food_water_demand": 10.0,
                "total_drink_water_met": 4.0,
                "total_unmet_drink_water": 1.0,
            },
            actions_dir=tmp_path / "opt" / "actions",
            results_dir=tmp_path / "opt" / "results",
        ),
    ]

    write_benchmark_summary(runs, tmp_path / "benchmark_summary.csv")

    frame = pd.read_csv(tmp_path / "benchmark_summary.csv")
    optimized = frame.loc[frame["policy"] == "optimized"].iloc[0]
    assert optimized["delta_total_energy_value"] == 2.0
    assert optimized["food_water_reliability"] == 0.9
    assert optimized["drink_water_reliability"] == 0.8
