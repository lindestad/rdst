"""Node ABC and common helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class Node:
    """Base class. Subclasses override `.step()`."""
    id: str
    upstream: list[str]
    downstream: list[str]
    forcings: pd.DataFrame = field(default_factory=pd.DataFrame)

    def load_forcings(self, df: pd.DataFrame) -> None:
        self.forcings = df.reset_index(drop=True)

    def step(self, t: int, state: dict[str, dict[str, Any]]) -> None:  # pragma: no cover
        raise NotImplementedError

    def upstream_inflow_m3s(self, state: dict[str, dict[str, Any]]) -> float:
        """Sum of all upstream nodes' outflow_m3s, as seen this step."""
        return sum(state[u]["outflow_m3s"] for u in self.upstream if u in state)


def days_in_month_from_ts(ts) -> int:
    return pd.Timestamp(ts).days_in_month


def m3s_to_mcm_month(m3s: float, days: int) -> float:
    """m³/s × seconds-in-month / 1e6 → million m³."""
    return m3s * days * 86400.0 / 1e6


def mcm_to_m3s_month(mcm: float, days: int) -> float:
    return mcm * 1e6 / (days * 86400.0)
