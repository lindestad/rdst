from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize
from pymoo.termination import get_termination

from nrsm_optimizer.actions import PiecewiseActionSpace
from nrsm_optimizer.objectives import (
    ObjectiveNames,
    compromise_score,
    pareto_objectives,
)


@dataclass
class ParetoOptimizationResult:
    variables: np.ndarray
    objectives: np.ndarray
    summaries: list[dict[str, float]]
    action_space: PiecewiseActionSpace
    objective_names: tuple[str, ...]
    baseline_summary: dict[str, float]
    best_index: int

    @property
    def best_variables(self) -> np.ndarray:
        return self.variables[self.best_index]

    @property
    def best_objectives(self) -> np.ndarray:
        return self.objectives[self.best_index]

    @property
    def best_summary(self) -> dict[str, float]:
        return self.summaries[self.best_index]

    def results_frame(self) -> pd.DataFrame:
        rows = []
        for index, (objectives, summary) in enumerate(zip(self.objectives, self.summaries)):
            row = {"candidate": index, "is_selected_compromise": index == self.best_index}
            row.update(
                {
                    name: float(value)
                    for name, value in zip(self.objective_names, objectives, strict=True)
                }
            )
            row.update({f"summary_{key}": value for key, value in summary.items()})
            rows.append(row)
        return pd.DataFrame(rows)

    def write_outputs(
        self,
        output_dir: Path,
        *,
        start_date=None,
        action_column: str = "optimized",
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self.results_frame().to_csv(output_dir / "pareto_candidates.csv", index=False)
        self.action_space.segment_frame(self.best_variables).to_csv(
            output_dir / "selected_action_segments.csv",
            index=False,
        )
        self.action_space.write_action_csvs(
            self.best_variables,
            output_dir / "actions",
            start_date=start_date,
            column=action_column,
        )


class NrsmParetoProblem(ElementwiseProblem):
    def __init__(
        self,
        simulator,
        action_space: PiecewiseActionSpace,
        *,
        baseline_summary: dict[str, float],
        objective_names: tuple[str, ...],
    ) -> None:
        lower, upper = action_space.bounds
        super().__init__(
            n_var=action_space.variable_count,
            n_obj=len(objective_names),
            xl=lower,
            xu=upper,
        )
        self.simulator = simulator
        self.action_space = action_space
        self.baseline_summary = baseline_summary
        self.objective_names = objective_names
        self.summaries: list[dict[str, float]] = []

    def _evaluate(self, x, out, *args, **kwargs) -> None:
        actions = self.action_space.flatten(x)
        summary = self.simulator.summary(actions)
        self.summaries.append(summary)
        out["F"] = pareto_objectives(
            summary,
            baseline_energy_value=float(self.baseline_summary.get("total_energy_value", 0.0)),
            terminal_storage=float(summary.get("terminal_reservoir_storage", 0.0)),
            baseline_terminal_storage=float(
                self.baseline_summary.get("terminal_reservoir_storage", 0.0)
            ),
        )


def optimize_pareto(
    simulator,
    *,
    interval_days: int = 30,
    controlled_nodes: Sequence[str] | None = None,
    population_size: int = 48,
    generations: int = 40,
    seed: int = 7,
) -> ParetoOptimizationResult:
    action_space = PiecewiseActionSpace.from_simulator(
        simulator,
        interval_days=interval_days,
        controlled_nodes=controlled_nodes,
    )
    baseline_actions = np.ones(simulator.expected_action_len(), dtype=float)
    baseline_summary = simulator.summary(baseline_actions.tolist())
    objective_names = ObjectiveNames().as_tuple(include_terminal_storage=True)

    problem = NrsmParetoProblem(
        simulator,
        action_space,
        baseline_summary=baseline_summary,
        objective_names=objective_names,
    )
    algorithm = NSGA2(pop_size=population_size, eliminate_duplicates=True)
    result = minimize(
        problem,
        algorithm,
        get_termination("n_gen", generations),
        seed=seed,
        verbose=False,
    )

    variables = np.atleast_2d(result.X).astype(float)
    objectives = np.atleast_2d(result.F).astype(float)
    summaries = [simulator.summary(action_space.flatten(row)) for row in variables]
    scores = [compromise_score(objective, scales=np.maximum(objectives.max(axis=0), 1.0)) for objective in objectives]
    best_index = int(np.argmin(scores))

    return ParetoOptimizationResult(
        variables=variables,
        objectives=objectives,
        summaries=summaries,
        action_space=action_space,
        objective_names=objective_names,
        baseline_summary=baseline_summary,
        best_index=best_index,
    )
