"""Seasonal extensions for the water resource simulator modules.

Provides time-varying energy price and catchment inflow driven by a sinusoidal
annual cycle, suitable for year-long optimisation studies.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

# Allow importing from the sibling node/ package.
sys.path.insert(0, str(Path(__file__).parent.parent / "node"))

from modules.catchment_inflow import CatchmentInflow  # noqa: E402
from modules.energy_price import EnergyPrice  # noqa: E402


class SeasonalEnergyPrice(EnergyPrice):
    """Sinusoidally varying energy price with an annual period.

    Price peaks in mid-winter (day 0 / day 365 = Jan 1) and troughs in
    mid-summer (day 182), reflecting higher electricity demand for heating.

    Parameters
    ----------
    base_price:
        Mean price over the year (currency / m³).
    amplitude:
        Peak-to-mean variation (currency / m³).  Must be < base_price to
        keep the price positive.
    period_days:
        Length of one full cycle in days (default 365).
    """

    def __init__(
        self,
        base_price: float,
        amplitude: float,
        period_days: float = 365.0,
    ) -> None:
        super().__init__(price_per_unit=base_price)
        self.base_price = base_price
        self.amplitude = amplitude
        self.period_days = period_days

    def price(self, timestep: int = 0) -> float:
        """Return the energy price for *timestep* (day index).

        The cosine function starts at its maximum on day 0 (winter peak) and
        reaches its minimum around day 182 (summer trough).
        """
        phase = 2.0 * math.pi * timestep / self.period_days
        return self.base_price + self.amplitude * math.cos(phase)


class SeasonalInflow(CatchmentInflow):
    """Sinusoidal annual inflow pattern, typical of snowmelt-driven catchments.

    Inflow peaks in late spring / early summer and is lowest in late winter.

    Parameters
    ----------
    base_rate:
        Mean daily inflow over the year (m³/day).
    amplitude:
        Peak-to-mean variation (m³/day).  Must be < base_rate.
    peak_day:
        Day of the year (0-indexed) when inflow is at its maximum (default 150,
        roughly late May for snowmelt).
    period_days:
        Length of one full cycle in days (default 365).
    """

    def __init__(
        self,
        base_rate: float,
        amplitude: float,
        peak_day: float = 150.0,
        period_days: float = 365.0,
    ) -> None:
        self.base_rate = base_rate
        self.amplitude = amplitude
        self.peak_day = peak_day
        self.period_days = period_days

    def inflow(self, timestep: int = 0, dt_days: float = 1.0) -> float:
        """Return inflow volume (m³) for *timestep*."""
        day = timestep % self.period_days
        phase = 2.0 * math.pi * (day - self.peak_day) / self.period_days
        rate = self.base_rate + self.amplitude * math.cos(phase)
        return max(0.0, rate) * dt_days
