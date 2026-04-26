from __future__ import annotations

from pathlib import Path

import pandas as pd

from nrsm_plotting.compare import (
    benchmark_summary_path,
    load_named_runs,
    parse_run_specs,
    plot_comparison,
    runs_from_benchmark_dir,
)


def write_result_folder(path: Path, energy_scale: float) -> None:
    path.mkdir(parents=True)
    pd.DataFrame(
        {
            "period_index": [0, 1],
            "start_day": [0, 1],
            "end_day_exclusive": [1, 2],
            "duration_days": [1, 1],
            "total_inflow": [100.0, 120.0],
            "total_evaporation": [5.0, 6.0],
            "total_drink_water_met": [10.0, 10.0],
            "total_unmet_drink_water": [0.0, 1.0],
            "total_food_water_demand": [20.0, 20.0],
            "total_food_water_met": [20.0, 15.0],
            "total_unmet_food_water": [0.0, 5.0],
            "total_food_produced": [20.0, 15.0],
            "total_production_release": [60.0, 55.0],
            "total_generated_electricity_kwh": [1000.0, 900.0],
            "total_generated_electricity_mwh": [1.0, 0.9],
            "total_spill": [0.0, 2.0],
            "total_release_for_routing": [60.0, 57.0],
            "total_downstream_release": [58.0, 55.0],
            "total_routing_loss": [2.0, 2.0],
            "total_energy_value": [energy_scale * 100.0, energy_scale * 90.0],
            "terminal_reservoir_storage": [200.0, 190.0],
        }
    ).to_csv(path / "summary.csv", index=False)
    pd.DataFrame(
        {
            "period_index": [0, 1],
            "start_day": [0, 1],
            "end_day_exclusive": [1, 2],
            "duration_days": [1, 1],
            "node_id": ["node", "node"],
            "action": [1.0, 0.5],
            "reservoir_level": [200.0, 190.0],
            "total_inflow": [100.0, 120.0],
            "evaporation": [5.0, 6.0],
            "drink_water_met": [10.0, 10.0],
            "unmet_drink_water": [0.0, 1.0],
            "food_water_demand": [20.0, 20.0],
            "food_water_met": [20.0, 15.0],
            "unmet_food_water": [0.0, 5.0],
            "food_produced": [20.0, 15.0],
            "production_release": [60.0, 55.0],
            "generated_electricity_kwh": [1000.0, 900.0],
            "generated_electricity_mwh": [1.0, 0.9],
            "water_value_eur_per_m3": [0.1, 0.1],
            "spill": [0.0, 2.0],
            "release_for_routing": [60.0, 57.0],
            "downstream_release": [58.0, 55.0],
            "routing_loss": [2.0, 2.0],
            "energy_value": [energy_scale * 100.0, energy_scale * 90.0],
        }
    ).to_csv(path / "node.csv", index=False)


def test_parse_run_specs_accepts_labels_and_bare_paths() -> None:
    parsed = parse_run_specs(["full=results/full", "optimized"])

    assert parsed == [
        ("full", Path("results/full")),
        ("optimized", Path("optimized")),
    ]


def test_runs_from_benchmark_dir_reads_manifest(tmp_path: Path) -> None:
    benchmark = tmp_path / "benchmark"
    full_results = benchmark / "policies" / "full" / "results"
    optimized_results = benchmark / "policies" / "optimized" / "results"
    write_result_folder(full_results, 1.0)
    write_result_folder(optimized_results, 1.2)
    (benchmark / "benchmark_manifest.json").write_text(
        """
        {
          "policies": [
            {"name": "full", "results_dir": "%s"},
            {"name": "optimized", "results_dir": "%s"}
          ]
        }
        """
        % (full_results.as_posix(), optimized_results.as_posix()),
        encoding="utf-8",
    )

    assert runs_from_benchmark_dir(benchmark) == [
        ("full", full_results),
        ("optimized", optimized_results),
    ]
    assert benchmark_summary_path(benchmark) is None


def test_runs_from_benchmark_dir_resolves_relative_manifest_paths(tmp_path: Path) -> None:
    benchmark = tmp_path / "optimizer" / "runs" / "benchmarks" / "smoke"
    full_results = benchmark / "policies" / "full" / "results"
    write_result_folder(full_results, 1.0)
    benchmark.mkdir(parents=True, exist_ok=True)
    (benchmark / "benchmark_manifest.json").write_text(
        """
        {
          "policies": [
            {"name": "full", "results_dir": "runs/benchmarks/smoke/policies/full/results"}
          ]
        }
        """,
        encoding="utf-8",
    )

    assert runs_from_benchmark_dir(benchmark) == [("full", full_results)]


def test_plot_comparison_writes_summary_manifest_and_plots(tmp_path: Path) -> None:
    full = tmp_path / "full"
    optimized = tmp_path / "optimized"
    output = tmp_path / "plots"
    write_result_folder(full, 1.0)
    write_result_folder(optimized, 1.2)

    runs = load_named_runs([("full", full), ("optimized", optimized)])
    manifest = plot_comparison(runs, output, file_format="png", dpi=80)

    assert manifest.summary_csv.exists()
    assert manifest.manifest_json.exists()
    assert len(manifest.plots) == 5
    assert all(path.exists() for path in manifest.plots)
    summary = pd.read_csv(manifest.summary_csv)
    optimized_row = summary.loc[summary["run"] == "optimized"].iloc[0]
    assert optimized_row["delta_total_energy_value"] == 38.0


def test_plot_comparison_adds_policy_value_plot_from_benchmark_summary(tmp_path: Path) -> None:
    full = tmp_path / "full"
    optimized = tmp_path / "optimized"
    output = tmp_path / "plots"
    benchmark_summary = tmp_path / "benchmark_summary.csv"
    write_result_folder(full, 1.0)
    write_result_folder(optimized, 1.2)
    pd.DataFrame(
        {
            "policy": ["full", "optimized"],
            "policy_value": [190.0, 260.0],
            "delta_policy_value": [0.0, 70.0],
        }
    ).to_csv(benchmark_summary, index=False)

    runs = load_named_runs([("full", full), ("optimized", optimized)])
    manifest = plot_comparison(
        runs,
        output,
        file_format="png",
        dpi=80,
        benchmark_summary=benchmark_summary,
    )

    assert len(manifest.plots) == 6
    assert (output / "demo_policy_value.png").exists()
    summary = pd.read_csv(manifest.summary_csv)
    optimized_row = summary.loc[summary["run"] == "optimized"].iloc[0]
    assert optimized_row["policy_value"] == 260.0
    assert optimized_row["delta_policy_value"] == 70.0
