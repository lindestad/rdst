"""Energy-price module.

Supports constant, timeseries, and CSV-backed energy prices.

* :class:`EnergyPrice` — constant price (backward-compatible default).
* :class:`TimeSeriesEnergyPrice` — price varies by timestep from a list.
* :class:`CSVEnergyPrice` — price read from a named column in a CSV file.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EnergyPrice:
    """Constant energy price.

    Parameters
    ----------
    price_per_unit:
        Currency value per m3 of water released for hydropower production.
    """
    price_per_unit: float

    def price(self, timestep: int = 0) -> float:  # noqa: ARG002
        """Return the constant energy price."""
        return self.price_per_unit


@dataclass
class TimeSeriesEnergyPrice:
    """Time-varying energy price from an in-memory list.

    Parameters
    ----------
    values:
        List of prices (currency/m3), one per timestep.  Wraps around.
    """
    values: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("TimeSeriesEnergyPrice requires at least one value.")

    def price(self, timestep: int = 0) -> float:
        """Return ``values[t % len]``."""
        return float(self.values[timestep % len(self.values)])


@dataclass
class CSVEnergyPrice:
    """Energy price read from a column in a CSV file.

    Parameters
    ----------
    filepath:
        Path to the CSV file.
    column:
        Header name of the column containing energy prices (currency/m3).
    """
    filepath: str
    column: str
    _values: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        path = Path(self.filepath)
        if not path.exists():
            raise FileNotFoundError(f"CSVEnergyPrice: file not found: {path}")
        with path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            if self.column not in (reader.fieldnames or []):
                raise KeyError(
                    f"CSVEnergyPrice: column '{self.column}' not found in {path}. "
                    f"Available: {reader.fieldnames}"
                )
            self._values = [float(row[self.column]) for row in reader]
        if not self._values:
            raise ValueError(f"CSVEnergyPrice: no data rows in {path}.")

    def price(self, timestep: int = 0) -> float:
        """Return the price for *timestep*, wrapping around the series."""
        return self._values[timestep % len(self._values)]

