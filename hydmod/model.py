

import numpy as np


# ============================================================
# Simple Hydrological Model
# ============================================================

def hydrological_model(area_m2, airt_mean, tp_mean):
    """
    Simple hydrological model.
    
    Parameters
    ----------
    area_m2 : float
        Catchment area in m²
    airt_mean : array-like
        Time series of air temperature (°C)
    tp_mean : array-like
        Time series of precipitation (mm/day)
    
    Returns
    -------
    SM : ndarray
        Soil moisture (mm)
    ET_act : ndarray
        Actual evapotranspiration (mm/day)
    Q : ndarray
        Runoff (mm/day)
    Q_m3s : ndarray
        Runoff converted to m³/s
    """
    # Parameters
    FC     = 150.0   # field capacity (mm)
    k      = 0.05    # linear reservoir coefficient (day⁻¹)
    T_base = 5.0     # base temperature for PET (°C)
    alpha  = 0.15    # PET coefficient (mm/°C/day)

    n = len(tp_mean)
    SM     = np.zeros(n)
    ET_act = np.zeros(n)
    Q      = np.zeros(n)

    SM[0] = FC * 0.5   # initial soil moisture: half field capacity

    for i in range(1, n):
        P = tp_mean[i]
        T = airt_mean[i]

        # 1. PET from air temperature (degree-day)
        PET = alpha * max(T - T_base, 0.0)

        # 2. Add precipitation to soil moisture
        SM_t = SM[i-1] + P

        # 3. Actual ET limited by available moisture
        AET  = min(PET, SM_t)
        SM_t -= AET

        # 4. Surface runoff: excess above field capacity
        R_surf = max(SM_t - FC, 0.0)
        SM_t   = min(SM_t, FC)

        # 5. Baseflow: linear reservoir drainage
        R_base = k * SM_t
        SM_t  -= R_base

        SM[i]     = SM_t
        ET_act[i] = AET
        Q[i]      = R_surf + R_base   # mm/day

    # Convert runoff mm/day → m³/s over catchment
    Q_m3s = Q * 1e-3 * area_m2 / 86400.0
    
    return SM, ET_act, Q, Q_m3s


