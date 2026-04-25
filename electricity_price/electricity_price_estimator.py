#!/usr/bin/env python3
"""
electricity_price_estimator.py

Estimates daily mean electricity prices (EUR/kWh) for every node defined in
nile.yaml, based on the dominant generation technology assigned to each region.

Three generation models are implemented:

  Solar    – prices are low during sunlit hours (latitude- and season-aware)
             and fall back to a higher backup price when the sun is absent.
             Daily mean is a weighted blend of the two.

  Hydro    – prices follow the Nile river-flow seasonal cycle.
             Cheap in the wet season (high reservoir), expensive in the dry.

  Gas/Coal – near-constant base price with a small seasonal demand swing.

Each region is assigned a primary and a secondary source; the final daily
price is a weighted blend (PRIMARY_FRACTION / 1−PRIMARY_FRACTION).

Output: one CSV per region in OUTPUT_DIR with columns: date, price_eur_kwh
        + an optional PNG plot via plot_prices().
"""

import csv
import math
import os
from datetime import date, timedelta

import yaml

# ============================================================
# SETTINGS  —  all model knobs live here
# ============================================================

# --- Simulation window (inclusive) --------------------------
START_DATE = date(2024, 1, 1)
END_DATE   = date(2024, 12, 31)

# --- Input / output -----------------------------------------
YAML_FILE  = "nile.yaml"
OUTPUT_DIR = "price_csv"

# --- Solar price model --------------------------------------
# When solar output is high the grid is flooded with cheap electricity.
# Outside of usable solar hours the grid falls back to gas/imports.
SOLAR_DAYTIME_PRICE   = 0.020   # EUR/kWh – marginal cost during solar peak
SOLAR_NIGHTTIME_PRICE = 0.090   # EUR/kWh – fallback (gas / regional import)
SOLAR_CLEAR_SKY       = 0.80    # fraction of daylight hours with useful irradiance

# --- Hydro price model --------------------------------------
# Nile basin: wet-season peak flow around 1 August (day 213).
HYDRO_WET_PRICE    = 0.030   # EUR/kWh – cheap electricity in wet / high-flow season
HYDRO_DRY_PRICE    = 0.080   # EUR/kWh – expensive in low-flow season
HYDRO_PEAK_DOY     = 213     # day-of-year at which river flow peaks (≈ 1 Aug)
HYDRO_SEASONALITY  = 0.85    # seasonal swing amplitude: 1.0 = full wet/dry range,
                             #   < 1.0 compresses the swing around the midpoint

# --- Gas / Coal price model ---------------------------------
GAS_BASE_PRICE        = 0.075   # EUR/kWh – flat fuel-cost baseline
GAS_SEASONAL_AMP      = 0.010   # EUR/kWh – amplitude of demand-driven seasonal swing
GAS_SEASONAL_PEAK_DOY = 15      # day-of-year of peak demand (≈ 15 Jan, winter heating)

# --- Regional energy mix ------------------------------------
# Map each node to (primary_source, secondary_source).
# Valid source strings: 'solar', 'hydro', 'gas'
REGION_ENERGY: dict[str, tuple[str, str]] = {
    "victoria":  ("hydro",  "gas"),    # Owen Falls / Lake Victoria hydropower
    "southwest": ("gas",    "solar"),  # Sudd lowlands – no local dam, gas/import grid
    "karthoum":  ("solar",  "hydro"),  # Khartoum – very sunny; some hydro from upstream
    "merowe":    ("hydro",  "solar"),  # Merowe Dam (Sudan) + desert solar potential
    "aswand":    ("solar",  "hydro"),  # Aswan – extreme sunshine + High Dam hydro
    "cairo":     ("gas",    "solar"),  # Nile Delta – gas-heavy urban/industrial grid
    "singa":     ("hydro",  "gas"),    # Blue Nile middle reaches, run-of-river hydro
    "roseires":  ("hydro",  "gas"),    # Roseires Dam (Blue Nile)
    "gerd":      ("hydro",  "gas"),    # Grand Ethiopian Renaissance Dam
    "tana":      ("hydro",  "gas"),    # Lake Tana / Upper Abay hydropower
    "kashm":     ("hydro",  "solar"),  # Atbara / Kashm el-Girba basin
    "tsengh":    ("hydro",  "solar"),  # Tekeze tributary
    "ozentari":  ("hydro",  "gas"),    # Headwater tributary (small run-of-river)
}

# Fraction of the blended price that comes from the primary source.
PRIMARY_FRACTION = 0.75

# ============================================================
# INTERNAL PRICE MODEL FUNCTIONS
# ============================================================

def _daylight_hours(lat_deg: float, doy: int) -> float:
    """Astronomical day length (hours) at a given latitude and day-of-year."""
    lat  = math.radians(lat_deg)
    # Solar declination angle (radians) – Spencer / simple approximation
    decl = math.radians(23.45 * math.sin(math.radians(360 / 365 * (284 + doy))))
    cos_H = -math.tan(lat) * math.tan(decl)
    cos_H = max(-1.0, min(1.0, cos_H))   # clamp for polar regions
    return 2.0 * math.acos(cos_H) * (12.0 / math.pi)


def _solar_price(lat_deg: float, doy: int) -> float:
    """
    Mean daily price for a solar-dominated grid.

    The day is split into solar hours (cheap) and non-solar hours (fallback).
    Solar hours = daylight hours × SOLAR_CLEAR_SKY.
    """
    solar_hours = _daylight_hours(lat_deg, doy) * SOLAR_CLEAR_SKY
    f_sun = solar_hours / 24.0
    return f_sun * SOLAR_DAYTIME_PRICE + (1.0 - f_sun) * SOLAR_NIGHTTIME_PRICE


def _hydro_price(doy: int) -> float:
    """
    Seasonal hydro price following the Nile wet/dry cycle.

    Uses a cosine to interpolate between the wet-season minimum and the
    dry-season maximum.  HYDRO_SEASONALITY scales the amplitude so that
    values < 1.0 compress the swing around the mid-point price.
    """
    angle = 2.0 * math.pi * (doy - HYDRO_PEAK_DOY) / 365.0
    # wet_factor: centred on 0, ranges ±HYDRO_SEASONALITY/2
    # cos(0) = +1 at wet peak  →  price pulled toward HYDRO_WET_PRICE
    # cos(π) = -1 at dry trough →  price pulled toward HYDRO_DRY_PRICE
    mid      = (HYDRO_WET_PRICE + HYDRO_DRY_PRICE) / 2.0
    half_amp = (HYDRO_DRY_PRICE - HYDRO_WET_PRICE) / 2.0
    return mid - half_amp * HYDRO_SEASONALITY * math.cos(angle)


def _gas_price(doy: int) -> float:
    """
    Near-constant gas / coal price with a small seasonal demand swing.
    Peaks in mid-January (space heating) and has a secondary summer
    trough (minimal cooling demand in mild climates).
    """
    angle = 2.0 * math.pi * (doy - GAS_SEASONAL_PEAK_DOY) / 365.0
    return GAS_BASE_PRICE + GAS_SEASONAL_AMP * math.cos(angle)


def _source_price(source: str, lat_deg: float, doy: int) -> float:
    """Dispatch to the correct price model for a named source."""
    if source == "solar":
        return _solar_price(lat_deg, doy)
    if source == "hydro":
        return _hydro_price(doy)
    if source == "gas":
        return _gas_price(doy)
    raise ValueError(f"Unknown energy source: '{source}'")


def region_daily_price(node_id: str, lat_deg: float, doy: int) -> float:
    """
    Blended daily mean electricity price (EUR/kWh) for a region.

    PRIMARY_FRACTION of the price is attributed to the primary source and
    (1 − PRIMARY_FRACTION) to the secondary source.
    """
    primary_src, secondary_src = REGION_ENERGY[node_id]
    p_primary   = _source_price(primary_src,   lat_deg, doy)
    p_secondary = _source_price(secondary_src, lat_deg, doy)
    return PRIMARY_FRACTION * p_primary + (1.0 - PRIMARY_FRACTION) * p_secondary


# ============================================================
# CSV GENERATION
# ============================================================

def generate_csvs(
    nodes: list[dict],
    output_dir: str = OUTPUT_DIR,
) -> dict[str, list[tuple[date, float]]]:
    """
    Write one CSV per region for the period START_DATE … END_DATE.

    CSV columns: date (ISO 8601), price_eur_kwh

    Returns a dict mapping node_id → list of (date, price) tuples, which
    can be passed directly to plot_prices().
    """
    os.makedirs(output_dir, exist_ok=True)

    # Build the full date sequence once
    all_dates: list[date] = []
    d = START_DATE
    while d <= END_DATE:
        all_dates.append(d)
        d += timedelta(days=1)

    results: dict[str, list[tuple[date, float]]] = {}

    for node in nodes:
        node_id = node["id"]
        lat     = node["latitude"]

        if node_id not in REGION_ENERGY:
            print(f"  [skip] '{node_id}' – no energy-mix entry in REGION_ENERGY")
            continue

        series: list[tuple[date, float]] = [
            (day, region_daily_price(node_id, lat, day.timetuple().tm_yday))
            for day in all_dates
        ]

        csv_path = os.path.join(output_dir, f"{node_id}.csv")
        with open(csv_path, "w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["date", "price_eur_kwh"])
            for day, price in series:
                writer.writerow([day.isoformat(), f"{price:.6f}"])

        print(f"  {csv_path:45s}  ({len(series)} rows, "
              f"min={min(p for _, p in series):.4f}  "
              f"max={max(p for _, p in series):.4f}  EUR/kWh)")
        results[node_id] = series

    return results


# ============================================================
# PLOT
# ============================================================

def plot_prices(
    results: dict[str, list[tuple[date, float]]],
    output_file: str | None = "electricity_prices.png",
) -> None:
    """
    Plot daily electricity price curves for all regions.

    Parameters
    ----------
    results     : dict returned by generate_csvs()
    output_file : path to save the figure (PNG/SVG/PDF);
                  pass None to display interactively instead.
    """
    try:
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not found – skipping plot  (pip install matplotlib)")
        return

    # Group nodes by primary energy source for colour-coding
    source_colours = {"hydro": "steelblue", "solar": "darkorange", "gas": "firebrick"}

    fig, axes = plt.subplots(
        3, 1, figsize=(14, 10), sharex=True,
        gridspec_kw={"hspace": 0.35},
    )
    source_order = ["hydro", "solar", "gas"]
    source_labels = {
        "hydro": "Hydro-dominant regions",
        "solar": "Solar-dominant regions",
        "gas":   "Gas/Coal-dominant regions",
    }

    # Bucket nodes by primary source
    by_source: dict[str, list[str]] = {s: [] for s in source_order}
    for node_id in sorted(results):
        primary = REGION_ENERGY[node_id][0]
        by_source[primary].append(node_id)

    for ax, source in zip(axes, source_order):
        colour = source_colours[source]
        node_ids = by_source[source]
        for i, node_id in enumerate(node_ids):
            series  = results[node_id]
            xs      = [row[0] for row in series]
            ys      = [row[1] for row in series]
            # Slightly vary the shade so overlapping lines are distinguishable
            alpha   = 0.55 + 0.45 * i / max(len(node_ids) - 1, 1)
            ax.plot(xs, ys, label=node_id, linewidth=1.4, alpha=alpha, color=colour)

        ax.set_title(source_labels[source], fontsize=10, fontweight="bold")
        ax.set_ylabel("EUR / kWh", fontsize=9)
        ax.legend(loc="upper right", fontsize=8, ncol=3)
        ax.grid(True, alpha=0.25)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())

    axes[-1].set_xlabel("Date", fontsize=9)
    fig.suptitle(
        f"Estimated daily electricity prices – Nile basin nodes\n"
        f"{START_DATE} → {END_DATE}",
        fontsize=12,
    )

    if output_file:
        fig.savefig(output_file, dpi=150, bbox_inches="tight")
        print(f"Plot saved → {output_file}")
    else:
        plt.show()

    plt.close(fig)


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    with open(YAML_FILE) as fh:
        config = yaml.safe_load(fh)

    nodes: list[dict] = config["nodes"]
    print(f"Loaded {len(nodes)} nodes from '{YAML_FILE}'")
    print(f"Period : {START_DATE} → {END_DATE}  ({(END_DATE - START_DATE).days + 1} days)\n")

    results = generate_csvs(nodes)
    print(f"\nCSV files written to '{OUTPUT_DIR}/'")

    print("\nGenerating plot …")
    plot_prices(results)


if __name__ == "__main__":
    main()
