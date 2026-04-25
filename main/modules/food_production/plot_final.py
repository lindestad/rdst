"""
Plot weekly agricultural water demand (m³/s) for all Nile basin zones.
Reads every CSV from final/*.csv (columns: date, water_m3_s).
Output: final/nile_water_demand_weekly.png
"""

import pathlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

FINAL_DIR = pathlib.Path(__file__).with_name("final")
OUT_PNG   = FINAL_DIR / "nile_water_demand_weekly.png"


def load_weekly(path: pathlib.Path) -> pd.Series:
    df = pd.read_csv(path, index_col="date", parse_dates=True)
    return df["water_m3_s"].resample("W").mean().rename(path.stem)


def main() -> None:
    csvs = sorted(FINAL_DIR.glob("*.csv"))
    if not csvs:
        raise SystemExit(f"No CSV files found in {FINAL_DIR}")

    series = [load_weekly(p) for p in csvs]
    # Sort by mean value descending so the legend reads largest → smallest
    series.sort(key=lambda s: s.mean(), reverse=True)

    fig, ax = plt.subplots(figsize=(18, 8))
    cmap = plt.get_cmap("tab20", len(series))

    for i, s in enumerate(series):
        ax.plot(s.index, s.values, linewidth=1.1, color=cmap(i),
                label=f"{s.name.capitalize()}  (mean {s.mean():,.0f} m³/s)")

    ax.set_xlabel("Year")
    ax.set_ylabel("Agricultural water demand  (m³ s⁻¹)")
    ax.set_title(
        "Nile Basin Agricultural Water Demand — Weekly means, 1950–2026\n"
        "ET_crop = Kc × ERA5-Land ET₀ × CGLS-LC100 mean cropland area (2015–2019)",
        fontsize=11,
    )
    ax.xaxis.set_major_locator(mdates.YearLocator(10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.YearLocator(5))
    ax.legend(ncol=2, fontsize=8.5, loc="upper left", framealpha=0.9)
    ax.grid(True, alpha=0.25)

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()
