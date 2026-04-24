"""Food-production module.

Supports constant, timeseries, and CSV-backed ``max_food_units`` capacity.
Food output is proportional to water available up to the capacity limit.

* :class:`FoodProduction` — constant max_food_units (backward-compatible default).
* :class:`TimeSeriesFoodProduction` — max_food_units varies by timestep.
* :class:`CSVFoodProduction` — max_food_units read from a CSV column.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


def _compute(water_available: float, water_coefficient: float, max_units_this_step: float) -> dict:
    if water_coefficient <= 0:
        raise ValueError("water_coefficient must be positive.")
    food_produced = min(water_available / water_coefficient, max_units_this_step)
    return {"food_produced": food_produced, "water_consumed": food_produced * water_coefficient}


@dataclass
class FoodProduction:
    """Water-driven food production with a constant daily capacity.

    Parameters
    ----------
    water_coefficient:
        m3 of water required to produce one food unit.
    max_food_units:
        Maximum food units producible per day.
    """
    water_coefficient: float
    max_food_units: float  # food units/day

    def produce(self, water_available: float, dt_days: float = 1.0) -> dict:
        """Return ``{"food_produced", "water_consumed"}``."""
        return _compute(water_available, self.water_coefficient, self.max_food_units * dt_days)


@dataclass
class TimeSeriesFoodProduction:
    """Food production with time-varying daily capacity from an in-memory list.

    Parameters
    ----------
    water_coefficient:
        m3 of water required to produce one food unit.
    max_food_units_values:
        List of daily capacity values (food units/day), one per timestep.  Wraps.
    """
    water_coefficient: float
    max_food_units_values: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.max_food_units_values:
            raise ValueError("TimeSeriesFoodProduction requires at least one value.")

    def produce(self, water_available: float, dt_days: float = 1.0) -> dict:
        raise NotImplementedError("Use produce(water_available, dt_days, timestep) for timeseries.")

    def produce_at(self, water_available: float, timestep: int = 0, dt_days: float = 1.0) -> dict:
        """Produce food using capacity for *timestep*."""
        cap = float(self.max_food_units_values[timestep % len(self.max_food_units_values)])
        return _compute(water_available, self.water_coefficient, cap * dt_days)


@dataclass
class CSVFoodProduction:
    """Food production with daily capacity read from a CSV column.

    Parameters
    ----------
    water_coefficient:
        m3 of water required to produce one food unit.
    filepath:
        Path to the CSV file.
    column:
        Header name of the column containing daily capacity (food units/day).
    """
    water_coefficient: float
    filepath: str
    column: str
    _values: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        path = Path(self.filepath)
        if not path.exists():
            raise FileNotFoundError(f"CSVFoodProduction: file not found: {path}")
        with path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            if self.column not in (reader.fieldnames or []):
                raise KeyError(
                    f"CSVFoodProduction: column '{self.column}' not found in {path}. "
                    f"Available: {reader.fieldnames}"
                )
            self._values = [float(row[self.column]) for row in reader]
        if not self._values:
            raise ValueError(f"CSVFoodProduction: no data rows in {path}.")

    def produce_at(self, water_available: float, timestep: int = 0, dt_days: float = 1.0) -> dict:
        """Produce food using capacity for *timestep*."""
        cap = self._values[timestep % len(self._values)]
        return _compute(water_available, self.water_coefficient, cap * dt_days)

