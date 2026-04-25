from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REQUIRED_PERIOD_COLUMNS = [
    "period_index",
    "start_day",
    "end_day_exclusive",
    "duration_days",
]

OPTIONAL_NODE_COLUMNS = [
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
    "spill",
    "release_for_routing",
    "downstream_release",
    "routing_loss",
    "energy_value",
]

OPTIONAL_SUMMARY_COLUMNS = [
    "total_inflow",
    "total_evaporation",
    "total_drink_water_met",
    "total_unmet_drink_water",
    "total_food_water_demand",
    "total_food_water_met",
    "total_unmet_food_water",
    "total_food_produced",
    "total_production_release",
    "total_spill",
    "total_release_for_routing",
    "total_downstream_release",
    "total_routing_loss",
    "total_energy_value",
]


@dataclass(frozen=True)
class ResultBundle:
    results_dir: Path
    summary: pd.DataFrame
    nodes: dict[str, pd.DataFrame]
    warnings: tuple[str, ...]

    @property
    def node_ids(self) -> list[str]:
        return sorted(self.nodes)


def load_results(results_dir: str | Path, nodes: list[str] | None = None) -> ResultBundle:
    """Load an NRSM result folder produced by `nrsm-cli --results-dir`."""

    base = Path(results_dir)
    summary_path = base / "summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"missing summary.csv in {base}")

    warnings: list[str] = []
    selected = set(nodes) if nodes else None
    summary = pd.read_csv(summary_path)
    _prepare_frame(summary, REQUIRED_PERIOD_COLUMNS, "summary.csv", warnings)
    _ensure_numeric_columns(summary, OPTIONAL_SUMMARY_COLUMNS, "summary.csv", warnings)

    node_frames: dict[str, pd.DataFrame] = {}
    for path in sorted(base.glob("*.csv")):
        if path.name == "summary.csv":
            continue
        node_id = path.stem
        if selected is not None and node_id not in selected:
            continue
        frame = pd.read_csv(path)
        _prepare_frame(frame, REQUIRED_PERIOD_COLUMNS, path.name, warnings)
        if "node_id" not in frame.columns:
            frame["node_id"] = node_id
            warnings.append(f"{path.name}: missing node_id column, inferred from filename")
        _ensure_numeric_columns(frame, OPTIONAL_NODE_COLUMNS, path.name, warnings)
        node_frames[node_id] = frame.sort_values("period_index").reset_index(drop=True)

    if selected is not None:
        missing = sorted(selected - set(node_frames))
        if missing:
            raise FileNotFoundError(f"missing node result CSVs: {', '.join(missing)}")
    if not node_frames:
        raise FileNotFoundError(f"no node CSVs found in {base}")

    summary = summary.sort_values("period_index").reset_index(drop=True)
    return ResultBundle(base, summary, node_frames, tuple(warnings))


def _prepare_frame(
    frame: pd.DataFrame, required_columns: list[str], label: str, warnings: list[str]
) -> None:
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{label}: missing required columns: {', '.join(missing)}")
    for column in required_columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame["mid_day"] = (frame["start_day"] + frame["end_day_exclusive"]) / 2.0
    if (frame["duration_days"] <= 0).any():
        warnings.append(f"{label}: found non-positive duration_days")


def _ensure_numeric_columns(
    frame: pd.DataFrame, columns: list[str], label: str, warnings: list[str]
) -> None:
    for column in columns:
        if column not in frame.columns:
            frame[column] = 0.0
            warnings.append(f"{label}: missing optional column {column}, filled with 0")
            continue
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

