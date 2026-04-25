from __future__ import annotations

from pathlib import Path

import pandas as pd

from nrsm_plotting import load_results, plot_all


def test_plot_all_writes_manifest_and_metrics(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    output_dir = tmp_path / "plots"
    results_dir.mkdir()

    pd.DataFrame(
        {
            "period_index": [0, 1, 2],
            "start_day": [0, 1, 2],
            "end_day_exclusive": [1, 2, 3],
            "duration_days": [1, 1, 1],
            "total_inflow": [100.0, 120.0, 90.0],
            "total_evaporation": [5.0, 6.0, 4.0],
            "total_drink_water_met": [10.0, 10.0, 10.0],
            "total_unmet_drink_water": [0.0, 2.0, 0.0],
            "total_food_water_demand": [20.0, 20.0, 20.0],
            "total_food_water_met": [20.0, 12.0, 20.0],
            "total_unmet_food_water": [0.0, 8.0, 0.0],
            "total_food_produced": [20.0, 12.0, 20.0],
            "total_production_release": [60.0, 55.0, 50.0],
            "total_spill": [0.0, 0.0, 3.0],
            "total_release_for_routing": [60.0, 55.0, 53.0],
            "total_downstream_release": [57.0, 52.0, 50.0],
            "total_routing_loss": [3.0, 3.0, 3.0],
            "total_energy_value": [1000.0, 900.0, 800.0],
        }
    ).to_csv(results_dir / "summary.csv", index=False)

    for node_id, offset in [("upstream", 0.0), ("downstream", 20.0)]:
        pd.DataFrame(
            {
                "period_index": [0, 1, 2],
                "start_day": [0, 1, 2],
                "end_day_exclusive": [1, 2, 3],
                "duration_days": [1, 1, 1],
                "node_id": [node_id, node_id, node_id],
                "action": [1.0, 0.8, 0.6],
                "reservoir_level": [200.0 + offset, 190.0 + offset, 180.0 + offset],
                "total_inflow": [50.0, 60.0, 45.0],
                "evaporation": [2.0, 3.0, 2.0],
                "drink_water_met": [5.0, 5.0, 5.0],
                "unmet_drink_water": [0.0, 1.0, 0.0],
                "food_water_demand": [10.0, 10.0, 10.0],
                "food_water_met": [10.0, 6.0, 10.0],
                "unmet_food_water": [0.0, 4.0, 0.0],
                "food_produced": [10.0, 6.0, 10.0],
                "production_release": [30.0, 25.0, 20.0],
                "spill": [0.0, 0.0, 1.0],
                "release_for_routing": [30.0, 25.0, 21.0],
                "downstream_release": [28.0, 23.0, 20.0],
                "routing_loss": [2.0, 2.0, 1.0],
                "energy_value": [500.0, 450.0, 400.0],
            }
        ).to_csv(results_dir / f"{node_id}.csv", index=False)

    bundle = load_results(results_dir)
    manifest = plot_all(bundle, output_dir, file_format="png", dpi=80)

    assert manifest.manifest_json.exists()
    assert manifest.metrics_csv.exists()
    assert len(manifest.plots) == 7
    assert all(path.exists() for path in manifest.plots)

