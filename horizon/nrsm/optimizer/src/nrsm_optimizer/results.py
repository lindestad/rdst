from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


NODE_COLUMNS = [
    "period_index",
    "start_day",
    "end_day_exclusive",
    "duration_days",
    "node_id",
    "action",
    "reservoir_level",
    "total_inflow",
    "evaporation",
    "drink_water_met",
    "unmet_drink_water",
    "food_water_demand",
    "food_water_met",
    "unmet_food_water",
    "food_produced",
    "production_release",
    "generated_electricity_kwh",
    "generated_electricity_mwh",
    "water_value_eur_per_m3",
    "spill",
    "release_for_routing",
    "downstream_release",
    "routing_loss",
    "energy_value",
]

SUMMARY_COLUMNS = [
    "period_index",
    "start_day",
    "end_day_exclusive",
    "duration_days",
    "total_inflow",
    "total_evaporation",
    "total_drink_water_met",
    "total_unmet_drink_water",
    "total_food_water_demand",
    "total_food_water_met",
    "total_unmet_food_water",
    "total_food_produced",
    "total_production_release",
    "total_generated_electricity_kwh",
    "total_generated_electricity_mwh",
    "total_spill",
    "total_release_for_routing",
    "total_downstream_release",
    "total_routing_loss",
    "total_energy_value",
    "terminal_reservoir_storage",
]


def write_result_csvs(result: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    node_rows: dict[str, list[dict]] = {}
    summary_rows: list[dict] = []

    for period in result["periods"]:
        duration_days = int(period["end_day_exclusive"]) - int(period["start_day"])
        summary_row = _empty_summary_row(period, duration_days)

        for node in period["node_results"]:
            row = _node_row(period, node, duration_days)
            node_rows.setdefault(str(node["node_id"]), []).append(row)
            _add_node_to_summary(summary_row, row)

        summary_rows.append(summary_row)

    for node_id, rows in node_rows.items():
        path = output_dir / f"{node_id}.csv"
        pd.DataFrame(rows, columns=NODE_COLUMNS).to_csv(path, index=False)
        written.append(path)

    summary_path = output_dir / "summary.csv"
    pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS).to_csv(summary_path, index=False)
    written.append(summary_path)

    (output_dir / "result_summary.json").write_text(
        json.dumps(result["summary"], indent=2),
        encoding="utf-8",
    )
    return written


def _node_row(period: dict, node: dict, duration_days: int) -> dict:
    production_release = float(node.get("production_release", 0.0))
    spill = float(node.get("spill", 0.0))
    downstream_release = float(node.get("downstream_release", 0.0))
    generated_kwh = float(node.get("generated_electricity_kwh", 0.0))
    release_for_routing = production_release + spill
    return {
        "period_index": period["period_index"],
        "start_day": period["start_day"],
        "end_day_exclusive": period["end_day_exclusive"],
        "duration_days": duration_days,
        "node_id": node["node_id"],
        "action": node.get("action", 0.0),
        "reservoir_level": node.get("reservoir_level", 0.0),
        "total_inflow": node.get("total_inflow", 0.0),
        "evaporation": node.get("evaporation", 0.0),
        "drink_water_met": node.get("drink_water_met", 0.0),
        "unmet_drink_water": node.get("unmet_drink_water", 0.0),
        "food_water_demand": node.get("food_water_demand", 0.0),
        "food_water_met": node.get("food_water_met", 0.0),
        "unmet_food_water": node.get("unmet_food_water", 0.0),
        "food_produced": node.get("food_produced", 0.0),
        "production_release": production_release,
        "generated_electricity_kwh": generated_kwh,
        "generated_electricity_mwh": generated_kwh / 1_000.0,
        "water_value_eur_per_m3": node.get("water_value_eur_per_m3", 0.0),
        "spill": spill,
        "release_for_routing": release_for_routing,
        "downstream_release": downstream_release,
        "routing_loss": max(0.0, release_for_routing - downstream_release),
        "energy_value": node.get("energy_value", 0.0),
    }


def _empty_summary_row(period: dict, duration_days: int) -> dict:
    return {
        "period_index": period["period_index"],
        "start_day": period["start_day"],
        "end_day_exclusive": period["end_day_exclusive"],
        "duration_days": duration_days,
        "total_inflow": 0.0,
        "total_evaporation": 0.0,
        "total_drink_water_met": 0.0,
        "total_unmet_drink_water": 0.0,
        "total_food_water_demand": 0.0,
        "total_food_water_met": 0.0,
        "total_unmet_food_water": 0.0,
        "total_food_produced": 0.0,
        "total_production_release": 0.0,
        "total_generated_electricity_kwh": 0.0,
        "total_generated_electricity_mwh": 0.0,
        "total_spill": 0.0,
        "total_release_for_routing": 0.0,
        "total_downstream_release": 0.0,
        "total_routing_loss": 0.0,
        "total_energy_value": 0.0,
        "terminal_reservoir_storage": 0.0,
    }


def _add_node_to_summary(summary: dict, node: dict) -> None:
    summary["total_inflow"] += float(node["total_inflow"])
    summary["total_evaporation"] += float(node["evaporation"])
    summary["total_drink_water_met"] += float(node["drink_water_met"])
    summary["total_unmet_drink_water"] += float(node["unmet_drink_water"])
    summary["total_food_water_demand"] += float(node["food_water_demand"])
    summary["total_food_water_met"] += float(node["food_water_met"])
    summary["total_unmet_food_water"] += float(node["unmet_food_water"])
    summary["total_food_produced"] += float(node["food_produced"])
    summary["total_production_release"] += float(node["production_release"])
    summary["total_generated_electricity_kwh"] += float(node["generated_electricity_kwh"])
    summary["total_generated_electricity_mwh"] += float(node["generated_electricity_mwh"])
    summary["total_spill"] += float(node["spill"])
    summary["total_release_for_routing"] += float(node["release_for_routing"])
    summary["total_downstream_release"] += float(node["downstream_release"])
    summary["total_routing_loss"] += float(node["routing_loss"])
    summary["total_energy_value"] += float(node["energy_value"])
    summary["terminal_reservoir_storage"] += float(node["reservoir_level"])
