"""FAO-56 Penman–Monteith potential evapotranspiration.

Reference: Allen et al. (1998), FAO Irrigation & Drainage Paper 56.
Applied at monthly mean inputs; good enough (~10%) for reservoir evap.
"""
from __future__ import annotations

import numpy as np


def _saturation_vp_kpa(temp_c):
    """Tetens equation for saturation vapor pressure (kPa)."""
    return 0.6108 * np.exp((17.27 * temp_c) / (temp_c + 237.3))


def _slope_svp_kpa_per_c(temp_c):
    svp = _saturation_vp_kpa(temp_c)
    return 4098.0 * svp / ((temp_c + 237.3) ** 2)


def pet_mm_monthly(
    temp_c,
    dewpoint_c,
    radiation_mj_m2_day,
    wind_ms,
    days_in_month,
):
    """FAO-56 reference ET (mm per month).

    All inputs are monthly means (scalars or numpy arrays).
    """
    gamma = 0.066  # psychrometric constant (kPa/°C) at ~sea level
    es = _saturation_vp_kpa(temp_c)
    ea = _saturation_vp_kpa(dewpoint_c)
    delta = _slope_svp_kpa_per_c(temp_c)
    # Net radiation approx = 0.77 * Rs (albedo-adjusted for water)
    rn = 0.77 * radiation_mj_m2_day
    g_soil = 0.0
    num = 0.408 * delta * (rn - g_soil) + gamma * (900.0 / (temp_c + 273.0)) * wind_ms * (es - ea)
    den = delta + gamma * (1.0 + 0.34 * wind_ms)
    et0_day = num / den
    return et0_day * days_in_month
