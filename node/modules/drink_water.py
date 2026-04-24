"""Drink-water demand module.

Supports constant, timeseries, and CSV-backed daily demand.

* :class:`DrinkWaterDemand` — constant daily demand (backward-compatible default).
* :class:`TimeSeriesDrinkWater` — list of daily demands indexed by timestep.
* :class:`CSVDrinkWater` — daily demands read from a named column in a CSV file.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DrinkWaterDemand:
    """Constant drinking-water demand.

    Parameters
    ----------
    daily_demand:
        Volume (m3/day) that must be withdrawn from the reservoir each day.
    """
    daily_demand: float  # m3/day

    def demand(self, timestep: int = 0, dt_days: float = 1.0) -> float:  # noqa: ARG002
        """Return ``daily_demand × dt_days`` regardless of timestep."""
        return self.daily_demand * dt_days


@dataclass
class TimeSeriesDrinkWater:
    """Time-varying drinking-water demand from an in-memory list.

    Parameters
    ----------
    values:
        Daily demand rates (m3/day), one per timestep.  Wraps around.
    """
    values: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("TimeSeriesDrinkWater requires at least one value.")

    def demand(self, timestep: int = 0, dt_days: float = 1.0) -> float:
        """Return ``values[t % len] × dt_days``."""
        return float(self.values[timestep % len(self.values)]) * dt_days


@dataclass
class CSVDrinkWater:
    """Drinking-water demand read from a column in a CSV file.

    Parameters
    ----------
    filepath:
        Path to the CSV file.
    column:
        Header name of the column containing daily demand rates (m3/day).
    """
    filepath: str
    column: str
    _values: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        path = Path(self.filepath)
        if not path.exists():
            raise FileNotFoundError(f"CSVDrinkWater: file not found: {path}")
        with path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            if self.column not in (reader.fieldnames or []):
                raise KeyError(
                    f"CSVDrinkWater: column '{self.column}' not found in {path}. "
                    f"Available: {reader.fieldnames}"
                )
            self._values = [float(row[self.column]) for row in reader]
        if not self._values:
            raise ValueError(f"CSVDrinkWater: no data rows in {path}.")

    def demand(self, timestep: int = 0, dt_days: float = 1.0) -> float:
        """Return the demand volume for *timestep*, scaled by *dt_days*."""
        return self._values[timestep % len(self._values)] * dt_days

