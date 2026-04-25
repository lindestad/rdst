from __future__ import annotations

import pandas as pd

from nrsm_optimizer.results import write_result_csvs


def test_write_result_csvs_matches_plotting_contract(tmp_path) -> None:
    result = {
        "summary": {
            "total_energy_value": 3.0,
            "terminal_reservoir_storage": 7.0,
        },
        "periods": [
            {
                "period_index": 0,
                "start_day": 0,
                "end_day_exclusive": 1,
                "node_results": [
                    {
                        "node_id": "a",
                        "action": 0.5,
                        "reservoir_level": 7.0,
                        "total_inflow": 10.0,
                        "evaporation": 1.0,
                        "drink_water_met": 2.0,
                        "unmet_drink_water": 0.0,
                        "food_water_demand": 3.0,
                        "food_water_met": 3.0,
                        "unmet_food_water": 0.0,
                        "food_produced": 3.0,
                        "production_release": 4.0,
                        "generated_electricity_kwh": 5.0,
                        "water_value_eur_per_m3": 0.1,
                        "spill": 1.0,
                        "downstream_release": 4.5,
                        "energy_value": 3.0,
                    }
                ],
            }
        ],
    }

    write_result_csvs(result, tmp_path)

    node = pd.read_csv(tmp_path / "a.csv")
    summary = pd.read_csv(tmp_path / "summary.csv")
    assert node.loc[0, "release_for_routing"] == 5.0
    assert node.loc[0, "routing_loss"] == 0.5
    assert summary.loc[0, "terminal_reservoir_storage"] == 7.0
