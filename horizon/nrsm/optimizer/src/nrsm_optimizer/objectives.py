from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np


@dataclass(frozen=True)
class ObjectiveNames:
    """Objective columns minimized by the optimizer."""

    energy_regret: str = "energy_regret"
    unmet_drink_water: str = "unmet_drink_water"
    unmet_food_water: str = "unmet_food_water"
    spill: str = "spill"
    terminal_storage_regret: str = "terminal_storage_regret"

    def as_tuple(self, include_terminal_storage: bool = False) -> tuple[str, ...]:
        names = (
            self.energy_regret,
            self.unmet_drink_water,
            self.unmet_food_water,
            self.spill,
        )
        if include_terminal_storage:
            return names + (self.terminal_storage_regret,)
        return names


def pareto_objectives(
    summary: Mapping[str, float],
    *,
    baseline_energy_value: float,
    terminal_storage: float | None = None,
    baseline_terminal_storage: float | None = None,
) -> np.ndarray:
    """Convert an NRSM summary to minimization objectives for NSGA-II."""

    energy = float(summary.get("total_energy_value", 0.0))
    objectives = [
        max(0.0, baseline_energy_value - energy),
        max(0.0, float(summary.get("total_unmet_drink_water", 0.0))),
        max(0.0, float(summary.get("total_unmet_food_water", 0.0))),
        max(0.0, float(summary.get("total_spill", 0.0))),
    ]
    if terminal_storage is not None and baseline_terminal_storage is not None:
        objectives.append(max(0.0, baseline_terminal_storage - terminal_storage))
    return np.asarray(objectives, dtype=float)


def compromise_score(
    objectives: np.ndarray,
    *,
    scales: np.ndarray | None = None,
    weights: np.ndarray | None = None,
) -> float:
    values = np.asarray(objectives, dtype=float)
    if scales is None:
        scales = np.maximum(np.nanmax(values, axis=0), 1.0)
    if weights is None:
        weights = np.ones(values.shape[-1], dtype=float)
    normalized = values / scales
    return float(np.sum(normalized * weights, axis=-1))
