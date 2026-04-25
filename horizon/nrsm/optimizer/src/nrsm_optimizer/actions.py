from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PiecewiseActionSpace:
    """Compressed action schedule expanded to NRSM's daily T x N action matrix."""

    node_ids: tuple[str, ...]
    horizon_days: int
    interval_days: int = 30
    controlled_nodes: tuple[str, ...] | None = None
    default_action: float = 1.0

    def __post_init__(self) -> None:
        if self.horizon_days <= 0:
            raise ValueError("horizon_days must be positive")
        if self.interval_days <= 0:
            raise ValueError("interval_days must be positive")
        unknown = set(self.controlled_node_ids) - set(self.node_ids)
        if unknown:
            raise ValueError(f"controlled_nodes contains unknown node ids: {sorted(unknown)}")

    @classmethod
    def from_simulator(
        cls,
        simulator: object,
        *,
        interval_days: int = 30,
        controlled_nodes: Sequence[str] | None = None,
        default_action: float = 1.0,
    ) -> PiecewiseActionSpace:
        return cls(
            node_ids=tuple(simulator.node_ids()),
            horizon_days=int(simulator.horizon_days()),
            interval_days=interval_days,
            controlled_nodes=tuple(controlled_nodes) if controlled_nodes else None,
            default_action=default_action,
        )

    @property
    def controlled_node_ids(self) -> tuple[str, ...]:
        return self.controlled_nodes or self.node_ids

    @property
    def segment_count(self) -> int:
        return int(np.ceil(self.horizon_days / self.interval_days))

    @property
    def variable_count(self) -> int:
        return self.segment_count * len(self.controlled_node_ids)

    @property
    def bounds(self) -> tuple[np.ndarray, np.ndarray]:
        return np.zeros(self.variable_count), np.ones(self.variable_count)

    def expand(self, vector: Sequence[float]) -> np.ndarray:
        values = np.asarray(vector, dtype=float)
        if values.shape != (self.variable_count,):
            raise ValueError(
                f"expected {self.variable_count} action variables, found {values.size}"
            )

        matrix = np.full(
            (self.horizon_days, len(self.node_ids)),
            float(self.default_action),
            dtype=float,
        )
        node_positions = {node_id: index for index, node_id in enumerate(self.node_ids)}
        clipped = np.clip(values, 0.0, 1.0)

        offset = 0
        for segment in range(self.segment_count):
            start = segment * self.interval_days
            end = min(start + self.interval_days, self.horizon_days)
            for node_id in self.controlled_node_ids:
                matrix[start:end, node_positions[node_id]] = clipped[offset]
                offset += 1

        return matrix

    def flatten(self, vector: Sequence[float]) -> list[float]:
        return self.expand(vector).reshape(-1).tolist()

    def segment_frame(self, vector: Sequence[float]) -> pd.DataFrame:
        values = np.asarray(vector, dtype=float)
        if values.shape != (self.variable_count,):
            raise ValueError(
                f"expected {self.variable_count} action variables, found {values.size}"
            )

        rows: list[dict[str, float | int | str]] = []
        offset = 0
        clipped = np.clip(values, 0.0, 1.0)
        for segment in range(self.segment_count):
            start = segment * self.interval_days
            end = min(start + self.interval_days, self.horizon_days)
            for node_id in self.controlled_node_ids:
                rows.append(
                    {
                        "segment": segment,
                        "start_day": start,
                        "end_day_exclusive": end,
                        "node_id": node_id,
                        "action": clipped[offset],
                    }
                )
                offset += 1
        return pd.DataFrame(rows)

    def write_action_csvs(
        self,
        vector: Sequence[float],
        output_dir: Path,
        *,
        start_date: date | None = None,
        column: str = "optimized",
    ) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        matrix = self.expand(vector)
        dates = [
            (start_date + timedelta(days=day)).isoformat() if start_date else f"day_{day}"
            for day in range(self.horizon_days)
        ]

        written: list[Path] = []
        for node_index, node_id in enumerate(self.node_ids):
            path = output_dir / f"{node_id}.actions.csv"
            pd.DataFrame({"date": dates, column: matrix[:, node_index]}).to_csv(
                path,
                index=False,
                float_format="%.6f",
            )
            written.append(path)
        return written
