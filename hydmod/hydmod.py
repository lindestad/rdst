#!/home/bernt/py_env/cdsapi/bin/python

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys 
import model 

# Programmer: Bernt Viggo Matheussen 
# Simple hydrological model for the Nile basin using ERA5-Land data

#datafolder = "../era5/"
datafolder = "../era5_1950_2025/"

stationfile = "climate_stations_lat_lon.txt"
catchmentfile = "catchments.txt"

#df_catchments = pd.read_csv(catchmentfile, sep="\t")
df_catchments = pd.read_csv(catchmentfile, sep=r"\s+", engine="python")

df_stations = pd.read_csv(stationfile, sep="\t")

n_catchments = len(df_catchments)
print(f"Number of catchments: {n_catchments}")

inflowdata_list = []

catch_Q = [] 

for n in range(n_catchments):

    print("#######  n =",n," ################")
    nodename = df_catchments["CatchmentName"][n].strip()

    mask = df_stations["NodeNr"] == n
    coords = df_stations.loc[mask, ["Lat", "Lon"]]

    prcpfiles = [f"era5_prcp_{row.Lat}_{row.Lon}.csv" for _, row in coords.iterrows()]

    airtfiles = [f"era5_land_{row.Lat}_{row.Lon}.csv" for _, row in coords.iterrows()]

    tp_arrays = []
    for f in prcpfiles:
        pfile = datafolder + f
        df_prcp = pd.read_csv(pfile, parse_dates=["valid_time"], index_col="valid_time")
        tp_arrays.append(df_prcp["tp"].to_numpy())

    tp_all = np.array(tp_arrays)  # shape: (4, 5481)
    tp_mean = tp_all.mean(axis=0)   # shape: (5481,)

    airt_arrays = [] 
    for a in airtfiles:
        afile = datafolder + a
        df_airt = pd.read_csv(afile, parse_dates=["valid_time"], index_col="valid_time")
        airt_arrays.append(df_airt["t2m"].to_numpy())

    airt_all = np.array(airt_arrays)   
    airt_mean = airt_all.mean(axis=0)   # shape: (5481,)

    # Find the area of the current catchment 
    area_km2 = df_catchments["AREA_KM2"][n]

    print("Nodename = ", nodename, " - Area (km²) = ", area_km2 )
    
    SM, ET_act, Q, Q_m3s = model.hydrological_model(area_km2*1000000, airt_mean, tp_mean)
    catch_Q.append(Q_m3s)  # Store the runoff for this catchment

    outfilename = "hydro_" + nodename + ".txt"
    
    print(f"Saving results to {outfilename}...")
    header = "Date  Precip_mm_day  AirTemp_C  SoilMoisture_mm  ActualET_mm_day  Runoff_mm_day  Runoff_m3s"
    output_data = np.column_stack((df_prcp.index.strftime("%Y-%m-%d"), tp_mean, airt_mean, SM, ET_act, Q, Q_m3s))

    np.savetxt(outfilename, output_data, header=header, fmt="%s", delimiter="\t")



catch_Q_all = np.array(catch_Q)   # shape: (n_catchments, n_timesteps)
names = [df_catchments["CatchmentName"][n].strip() for n in range(n_catchments)]
header_q = "\t".join(names)
np.savetxt("catch_Q_all.txt", catch_Q_all.T, header=header_q, fmt="%.5f", delimiter="\t")


dates = df_prcp.index  # same dates for all catchments
fig, ax = plt.subplots(figsize=(14, 6))
for n, Q_series in enumerate(catch_Q):
    name = df_catchments["CatchmentName"][n].strip()
    ax.plot(dates, Q_series, label=name)

ax.set_title("Catchment Runoff All Catchments")
ax.set_xlabel("Date")
ax.set_ylabel("Runoff (m³/s)")
ax.legend(loc="upper right", fontsize=7)
plt.tight_layout()
plt.show()







sys.exit(0)






# Prcp 
prcpfile=[
    "era5_prcp_-0.17_31.37.csv", 
    "era5_prcp_-1.86_34.52.csv", 
    "era5_prcp_-1.94_35.1.csv",
    "era5_prcp_-1.83_30.42.csv"]

print("Precipitation files:"    )

for f in prcpfile:
   
    #pfile = infolder + prcpfile[0]
    pfile = infolder + f
    print(f"Reading {pfile}...")
    df_prcp = pd.read_csv(pfile, parse_dates=["valid_time"], index_col="valid_time")
    print(df_prcp.head())

tp_arrays = []

for f in prcpfile:
    pfile = infolder + f
    print(f"Reading {pfile}...")
    df_prcp = pd.read_csv(pfile, parse_dates=["valid_time"], index_col="valid_time")
    tp_arrays.append(df_prcp["tp"].to_numpy())

# tp_arrays[0] = first file, tp_arrays[1] = second, etc.
print(tp_arrays[:][:5])  # Print first 5 values from the first file

tp_all = np.array(tp_arrays)          # shape: (4, 5481)

header = "  ".join(f.replace(".csv","") for f in prcpfile)
np.savetxt("tp_all.txt", tp_all.T, header=header, fmt="%.3f")

tp_mean = tp_all.mean(axis=0)   # shape: (5481,)

dates = df_prcp.index  # reuse index from last file read in the loop

infile = infolder + "era5_land_-0.17_31.37.csv"

airtfiles=["era5_land_-1.83_30.42.csv",
           "era5_land_-1.86_34.52.csv",
           "era5_land_-1.94_35.1.csv",
           "era5_land_-0.17_31.37.csv"]

airt_arrays = []

for a in airtfiles:
    afile = infolder + a
    print(f"Reading {afile}...")
    df_airt = pd.read_csv(afile, parse_dates=["valid_time"], index_col="valid_time")
    print(df_airt.head()    )
    airt_arrays.append(df_airt["t2m"].to_numpy())

airt_all = np.array(airt_arrays)   
header = "  ".join(f.replace(".csv","") for a in airtfiles)

airt_mean = airt_all.mean(axis=0)   # shape: (5481,)
dates = df_prcp.index  # reuse index from last file read in the loop







# ============================================================
# Simple Hydrological Model
# ============================================================

# Lake Victoria area
#lake_area_m2 = 68800e6   # 68,800 km²

land_area_m2 = 263804e6   # 263,804 km²


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

# Convert runoff mm/day → m³/s over Lake Victoria catchment
Q_m3s = Q * 1e-3 * land_area_m2 / 86400.0






# Plot
fig, axes = plt.subplots(4, 1, figsize=(14, 14), sharex=True)

axes[0].plot(dates, tp_mean)
axes[0].set_ylabel("Precipitation (mm/day)")
axes[0].set_title("Simple Hydrological Model – Lake Victoria")

axes[1].plot(dates, airt_mean, color="tab:red")
axes[1].set_ylabel("Air Temp (°C)")

axes[2].plot(dates, SM, color="tab:brown")
axes[2].axhline(FC, color="k", linestyle="--", linewidth=0.8, label=f"FC = {FC} mm")
axes[2].set_ylabel("Soil Moisture (mm)")
axes[2].legend()

axes[3].plot(dates, Q_m3s, color="tab:blue")
axes[3].set_ylabel("Lake Inflow (m³/s)")
axes[3].set_xlabel("Date")

plt.tight_layout()
plt.show()




