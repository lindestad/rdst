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
    storage_depletion: str = "storage_depletion"

    def as_tuple(self, include_storage_depletion: bool = False) -> tuple[str, ...]:
        names = (
            self.energy_regret,
            self.unmet_drink_water,
            self.unmet_food_water,
            self.spill,
        )
        if include_storage_depletion:
            return names + (self.storage_depletion,)
        return names


COMPROMISE_MODES = ("energy_food", "balanced", "storage_safe")


def pareto_objectives(
    summary: Mapping[str, float],
    *,
    baseline_energy_value: float,
    initial_storage: float | None = None,
    terminal_storage: float | None = None,
) -> np.ndarray:
    """Convert an NRSM summary to minimization objectives for NSGA-II."""

    energy = float(summary.get("total_energy_value", 0.0))
    objectives = [
        max(0.0, baseline_energy_value - energy),
        max(0.0, float(summary.get("total_unmet_drink_water", 0.0))),
        max(0.0, float(summary.get("total_unmet_food_water", 0.0))),
        max(0.0, float(summary.get("total_spill", 0.0))),
    ]
    if initial_storage is not None and terminal_storage is not None:
        objectives.append(max(0.0, initial_storage - terminal_storage))
    return np.asarray(objectives, dtype=float)


def compromise_weights(objective_names: tuple[str, ...], mode: str) -> np.ndarray:
    if mode not in COMPROMISE_MODES:
        raise ValueError(f"unknown compromise mode `{mode}`")

    names = ObjectiveNames()
    presets = {
        "energy_food": {
            names.energy_regret: 3.0,
            names.unmet_drink_water: 6.0,
            names.unmet_food_water: 3.0,
            names.spill: 0.5,
            names.storage_depletion: 0.25,
        },
        "balanced": {
            names.energy_regret: 1.0,
            names.unmet_drink_water: 4.0,
            names.unmet_food_water: 2.0,
            names.spill: 1.0,
            names.storage_depletion: 1.0,
        },
        "storage_safe": {
            names.energy_regret: 0.25,
            names.unmet_drink_water: 5.0,
            names.unmet_food_water: 1.0,
            names.spill: 1.0,
            names.storage_depletion: 8.0,
        },
    }
    preset = presets[mode]
    return np.asarray([preset.get(name, 1.0) for name in objective_names], dtype=float)


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
