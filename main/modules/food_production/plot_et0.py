"""
Plot daily ET₀ (mm/day) for all Nile basin zones.
Reads the nile_*_water.csv files produced by copernicus_egypt_agriculture.py.
"""

import pathlib
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

OUT = pathlib.Path(__file__).with_name("nile_et0.png")
CSV_DIR = pathlib.Path(__file__).parent

files = sorted(CSV_DIR.glob("nile_*_water.csv"))
if not files:
    raise SystemExit("No nile_*_water.csv files found.")

fig, ax = plt.subplots(figsize=(16, 7))

for f in files:
    name = f.stem.replace("nile_", "").replace("_water", "").capitalize()
    df = pd.read_csv(f, parse_dates=["date"])
    df = df[df["date"].dt.year < df["date"].dt.year.max()]  # drop partial final year
    # Daily line with low alpha; 365-day rolling mean as solid overlay
    ax.plot(df["date"], df["et0_mm_day"], linewidth=0.3, alpha=0.18)
    roll = df.set_index("date")["et0_mm_day"].rolling(365, center=True, min_periods=180).mean()
    ax.plot(roll.index, roll.values, linewidth=1.4, label=name)

ax.set_title("ERA5-Land Reference Evapotranspiration (ET₀) — Daily Values & 1-Year Rolling Mean by Zone")
ax.set_ylabel("ET₀ (mm day⁻¹)")
ax.set_xlabel("Year")
ax.xaxis.set_major_locator(mdates.YearLocator(10))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.legend(ncol=2, fontsize=8, loc="upper left")
ax.grid(True, alpha=0.3)
fig.tight_layout()
fig.savefig(OUT, dpi=150)
print(f"Saved {OUT}")
