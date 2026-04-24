"""Simplified monthly crop water requirement for Nile-basin irrigation.

Uses a single seasonal sinusoid peaking in July; amplitude and offset tuned
to FAO AquaStat numbers for the Gezira/Nile-Delta mean cropping pattern.
Values in mm/month."""
import math


def monthly_water_requirement_mm(month: int, peak_month: int = 7,
                                 annual_mean_mm: float = 130.0,
                                 amplitude_mm: float = 90.0) -> float:
    phase = (month - peak_month) * math.pi / 6.0
    return max(20.0, annual_mean_mm + amplitude_mm * math.cos(phase))
