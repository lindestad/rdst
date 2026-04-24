"""Catchment inflow module.

Provides natural inflow into a node's reservoir from its local catchment.
All rate values are in **m3/day**; the actual volume per timestep is
``rate × dt_days``.

Three implementations are provided:

* :class:`ConstantInflow` — a fixed daily rate (simple baseline).
* :class:`TimeSeriesInflow` — a list of daily rates indexed by timestep,
  allowing seasonal or historical inflow patterns.
* :class:`CSVInflow` — reads rates from a named column in a CSV file.

New inflow types can be added by subclassing :class:`CatchmentInflow` and
implementing :meth:`inflow`.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


class CatchmentInflow:
    """Abstract base for catchment inflow modules.

    Subclasses must implement :meth:`inflow`.
    """

    def inflow(self, timestep: int, dt_days: float = 1.0) -> float:
        """Return the inflow volume (m3) for this timestep.

        Parameters
        ----------
        timestep:
            Current timestep index (0-based).
        dt_days:
            Duration of one timestep in days.

        Returns
        -------
        float
            Inflow volume in m3 for this timestep.
        """
        raise NotImplementedError


@dataclass
class ConstantInflow(CatchmentInflow):
    """Constant catchment inflow at a fixed daily rate.

    Parameters
    ----------
    rate:
        Inflow rate in m3/day.
    """
    rate: float  # m3/day

    def inflow(self, timestep: int = 0, dt_days: float = 1.0) -> float:  # noqa: ARG002
        """Return ``rate × dt_days`` regardless of timestep.

        Parameters
        ----------
        timestep:
            Current timestep index (unused for constant inflow).
        dt_days:
            Duration of one timestep in days.

        Returns
        -------
        float
            Inflow volume in m3.
        """
        return self.rate * dt_days


@dataclass
class TimeSeriesInflow(CatchmentInflow):
    """Catchment inflow driven by a time-series of daily rates.

    The series wraps around (modulo indexing) so a one-year series can be
    used for multi-year simulations.

    Parameters
    ----------
    values:
        List of inflow rates (m3/day), one entry per timestep.
    """
    values: list = field(default_factory=list)  # m3/day per timestep

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("TimeSeriesInflow requires at least one value.")

    def inflow(self, timestep: int = 0, dt_days: float = 1.0) -> float:
        """Return the inflow volume for *timestep*, scaled by *dt_days*.

        Parameters
        ----------
        timestep:
            Current timestep index; wraps around the length of *values*.
        dt_days:
            Duration of one timestep in days.

        Returns
        -------
        float
            Inflow volume in m3.
        """
        rate = self.values[timestep % len(self.values)]
        return float(rate) * dt_days


@dataclass
class CSVInflow(CatchmentInflow):
    """Catchment inflow read from a column in a CSV file.

    The CSV must have a header row.  One column provides the daily inflow
    rates (m3/day).  Rows map to timesteps in file order (row 0 = timestep 0).
    The series wraps around if the simulation runs longer than the CSV.

    Parameters
    ----------
    filepath:
        Path to the CSV file (absolute, or relative to the working directory).
    column:
        Name of the column containing inflow rates (m3/day).

    Raises
    ------
    FileNotFoundError
        If *filepath* does not exist.
    KeyError
        If *column* is not found in the CSV header.
    ValueError
        If the CSV contains no data rows.
    """
    filepath: str
    column: str
    _values: list = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        path = Path(self.filepath)
        if not path.exists():
            raise FileNotFoundError(f"CSVInflow: file not found: {path}")
        with path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            if self.column not in (reader.fieldnames or []):
                raise KeyError(
                    f"CSVInflow: column '{self.column}' not found in {path}. "
                    f"Available columns: {reader.fieldnames}"
                )
            self._values = [float(row[self.column]) for row in reader]
        if not self._values:
            raise ValueError(f"CSVInflow: no data rows found in {path}.")

    def inflow(self, timestep: int = 0, dt_days: float = 1.0) -> float:
        """Return the inflow volume for *timestep*, scaled by *dt_days*.

        Parameters
        ----------
        timestep:
            Current timestep index; wraps around the length of the CSV series.
        dt_days:
            Duration of one timestep in days.

        Returns
        -------
        float
            Inflow volume in m3.
        """
        rate = self._values[timestep % len(self._values)]
        return rate * dt_days



class CatchmentInflow:
    """Abstract base for catchment inflow modules.

    Subclasses must implement :meth:`inflow`.
    """

    def inflow(self, timestep: int, dt_days: float = 1.0) -> float:
        """Return the inflow volume (m3) for this timestep.

        Parameters
        ----------
        timestep:
            Current timestep index (0-based).
        dt_days:
            Duration of one timestep in days.

        Returns
        -------
        float
            Inflow volume in m3 for this timestep.
        """
        raise NotImplementedError


@dataclass
class ConstantInflow(CatchmentInflow):
    """Constant catchment inflow at a fixed daily rate.

    Parameters
    ----------
    rate:
        Inflow rate in m3/day.
    """
    rate: float  # m3/day

    def inflow(self, timestep: int = 0, dt_days: float = 1.0) -> float:  # noqa: ARG002
        """Return ``rate × dt_days`` regardless of timestep.

        Parameters
        ----------
        timestep:
            Current timestep index (unused for constant inflow).
        dt_days:
            Duration of one timestep in days.

        Returns
        -------
        float
            Inflow volume in m3.
        """
        return self.rate * dt_days


@dataclass
class TimeSeriesInflow(CatchmentInflow):
    """Catchment inflow driven by a time-series of daily rates.

    The series wraps around (modulo indexing) so a one-year series can be
    used for multi-year simulations.

    Parameters
    ----------
    values:
        List of inflow rates (m3/day), one entry per timestep.
    """
    values: list = field(default_factory=list)  # m3/day per timestep

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("TimeSeriesInflow requires at least one value.")

    def inflow(self, timestep: int = 0, dt_days: float = 1.0) -> float:
        """Return the inflow volume for *timestep*, scaled by *dt_days*.

        Parameters
        ----------
        timestep:
            Current timestep index; wraps around the length of *values*.
        dt_days:
            Duration of one timestep in days.

        Returns
        -------
        float
            Inflow volume in m3.
        """
        rate = self.values[timestep % len(self.values)]
        return float(rate) * dt_days
