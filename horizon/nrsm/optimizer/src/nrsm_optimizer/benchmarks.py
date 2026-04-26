from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from nrsm_optimizer.results import write_result_csvs

ACTION_COLUMN = "action"


@dataclass(frozen=True)
class BenchmarkPolicy:
    name: str
    actions: np.ndarray
    description: str

    def flat(self) -> list[float]:
        return self.actions.reshape(-1).tolist()


@dataclass(frozen=True)
class BenchmarkRun:
    name: str
    description: str
    summary: dict[str, float]
    actions_dir: Path
    results_dir: Path


def run_benchmarks(
    simulator,
    output_dir: Path,
    *,
    optimized_actions_dir: Path | None = None,
    optimized_action_column: str = "optimized",
    start_date: date | None = None,
    controlled_nodes: Sequence[str] | None = None,
) -> list[BenchmarkRun]:
    output_dir.mkdir(parents=True, exist_ok=True)
    node_ids = tuple(simulator.node_ids())
    horizon_days = simulator.horizon_days()
    full = np.ones((horizon_days, len(node_ids)), dtype=float)
    full_result = simulator.result(full.reshape(-1).tolist())

    policies = [
        BenchmarkPolicy(
            "full_production",
            full,
            "Action 1.0 at every node and day.",
        ),
        BenchmarkPolicy(
            "no_production",
            np.zeros_like(full),
            "Action 0.0 at every node and day.",
        ),
        BenchmarkPolicy(
            "constant_50",
            np.full_like(full, 0.5),
            "Action 0.5 at every node and day.",
        ),
        BenchmarkPolicy(
            "inflow_proxy",
            inflow_proxy_actions(full_result, node_ids),
            "Action follows observed full-production inflow divided by observed max release.",
        ),
        BenchmarkPolicy(
            "storage_guardrail",
            storage_guardrail_actions(full_result, node_ids),
            "Action is reduced where full-production storage falls below guardrail levels.",
        ),
    ]
    if controlled_nodes:
        policies = [
            BenchmarkPolicy(
                policy.name,
                freeze_uncontrolled_nodes(policy.actions, node_ids, controlled_nodes),
                policy.description,
            )
            for policy in policies
        ]
    if optimized_actions_dir:
        policies.append(
            BenchmarkPolicy(
                "optimized",
                read_action_matrix(
                    optimized_actions_dir,
                    node_ids,
                    horizon_days,
                    column=optimized_action_column,
                ),
                f"Action CSVs read from {optimized_actions_dir}.",
            )
        )

    runs = [
        evaluate_policy(simulator, policy, output_dir, start_date=start_date)
        for policy in policies
    ]
    write_benchmark_summary(runs, output_dir / "benchmark_summary.csv")
    write_manifest(runs, output_dir)
    return runs


def evaluate_policy(
    simulator,
    policy: BenchmarkPolicy,
    output_dir: Path,
    *,
    start_date: date | None,
) -> BenchmarkRun:
    policy_dir = output_dir / "policies" / policy.name
    actions_dir = policy_dir / "actions"
    results_dir = policy_dir / "results"
    write_action_matrix(policy.actions, tuple(simulator.node_ids()), actions_dir, start_date)
    result = simulator.result(policy.flat())
    write_result_csvs(result, results_dir)
    (policy_dir / "policy.json").write_text(
        json.dumps({"name": policy.name, "description": policy.description}, indent=2),
        encoding="utf-8",
    )
    return BenchmarkRun(
        name=policy.name,
        description=policy.description,
        summary=result["summary"],
        actions_dir=actions_dir,
        results_dir=results_dir,
    )


def inflow_proxy_actions(result: dict, node_ids: Sequence[str]) -> np.ndarray:
    rows = node_result_frames(result, node_ids)
    matrix = np.ones((len(result["periods"]), len(node_ids)), dtype=float)
    for node_index, node_id in enumerate(node_ids):
        frame = rows[node_id]
        max_release = max(float(frame["production_release"].max()), 1.0)
        matrix[:, node_index] = np.clip(
            frame["total_inflow"].to_numpy(dtype=float) / max_release,
            0.0,
            1.0,
        )
    return matrix


def storage_guardrail_actions(
    result: dict,
    node_ids: Sequence[str],
    *,
    low_fraction: float = 0.25,
    high_fraction: float = 0.60,
    low_action: float = 0.25,
    high_action: float = 1.0,
) -> np.ndarray:
    rows = node_result_frames(result, node_ids)
    matrix = np.ones((len(result["periods"]), len(node_ids)), dtype=float)
    for node_index, node_id in enumerate(node_ids):
        storage = rows[node_id]["reservoir_level"].to_numpy(dtype=float)
        max_storage = max(float(np.max(storage)), 1.0)
        low = low_fraction * max_storage
        high = high_fraction * max_storage
        if high <= low:
            continue
        scaled = (storage - low) / (high - low)
        matrix[:, node_index] = low_action + np.clip(scaled, 0.0, 1.0) * (high_action - low_action)
    return matrix


def freeze_uncontrolled_nodes(
    actions: np.ndarray,
    node_ids: Sequence[str],
    controlled_nodes: Sequence[str],
) -> np.ndarray:
    controlled = set(controlled_nodes)
    frozen = np.ones_like(actions)
    for node_index, node_id in enumerate(node_ids):
        if node_id in controlled:
            frozen[:, node_index] = actions[:, node_index]
    return frozen


def node_result_frames(result: dict, node_ids: Sequence[str]) -> dict[str, pd.DataFrame]:
    rows = {node_id: [] for node_id in node_ids}
    for period in result["periods"]:
        for node in period["node_results"]:
            rows[str(node["node_id"])].append(node)
    return {node_id: pd.DataFrame(node_rows) for node_id, node_rows in rows.items()}


def write_action_matrix(
    actions: np.ndarray,
    node_ids: Sequence[str],
    output_dir: Path,
    start_date: date | None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dates = action_dates(actions.shape[0], start_date)
    paths = []
    for node_index, node_id in enumerate(node_ids):
        path = output_dir / f"{node_id}.actions.csv"
        pd.DataFrame({"date": dates, ACTION_COLUMN: actions[:, node_index]}).to_csv(
            path,
            index=False,
            float_format="%.6f",
        )
        paths.append(path)
    return paths


def read_action_matrix(
    actions_dir: Path,
    node_ids: Sequence[str],
    horizon_days: int,
    *,
    column: str,
) -> np.ndarray:
    matrix = np.ones((horizon_days, len(node_ids)), dtype=float)
    for node_index, node_id in enumerate(node_ids):
        path = _action_path(actions_dir, node_id)
        frame = pd.read_csv(path)
        if column not in frame.columns:
            raise ValueError(f"{path} is missing action column `{column}`")
        values = frame[column].to_numpy(dtype=float)
        if values.size != horizon_days:
            raise ValueError(
                f"{path} has {values.size} rows, expected {horizon_days}"
            )
        matrix[:, node_index] = np.clip(values, 0.0, 1.0)
    return matrix


def _action_path(actions_dir: Path, node_id: str) -> Path:
    for path in (
        actions_dir / f"{node_id}.actions.csv",
        actions_dir / f"{node_id}.csv",
    ):
        if path.exists():
            return path
    raise FileNotFoundError(
        f"missing action CSV for node `{node_id}` in {actions_dir}"
    )


def action_dates(horizon_days: int, start_date: date | None) -> list[str]:
    if start_date is None:
        return [f"day_{day}" for day in range(horizon_days)]
    return [
        (start_date + timedelta(days=day)).isoformat()
        for day in range(horizon_days)
    ]


def write_benchmark_summary(runs: Sequence[BenchmarkRun], path: Path) -> None:
    baseline = next(
        (run.summary for run in runs if run.name == "full_production"),
        runs[0].summary,
    )
    rows = []
    for run in runs:
        row = {
            "policy": run.name,
            "description": run.description,
            "actions_dir": str(run.actions_dir),
            "results_dir": str(run.results_dir),
        }
        for key, value in run.summary.items():
            if isinstance(value, (int, float)):
                row[key] = float(value)
                row[f"delta_{key}"] = float(value) - float(baseline.get(key, 0.0))
        row["drink_water_reliability"] = ratio(
            run.summary.get("total_drink_water_met", 0.0),
            run.summary.get("total_drink_water_met", 0.0)
            + run.summary.get("total_unmet_drink_water", 0.0),
        )
        row["food_water_reliability"] = ratio(
            run.summary.get("total_food_water_met", 0.0),
            run.summary.get("total_food_water_demand", 0.0),
        )
        rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)


def write_manifest(runs: Sequence[BenchmarkRun], output_dir: Path) -> None:
    manifest = {
        "policies": [
            {
                "name": run.name,
                "description": run.description,
                "actions_dir": str(run.actions_dir),
                "results_dir": str(run.results_dir),
                "summary": run.summary,
            }
            for run in runs
        ]
    }
    (output_dir / "benchmark_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


def ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        return 1.0
    return float(numerator) / float(denominator)
