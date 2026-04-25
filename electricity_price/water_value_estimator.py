#!/usr/bin/env python3
"""
water_value_estimator.py

Converts per-node electricity prices (EUR/kWh) to water opportunity-cost
prices (EUR/m³) by multiplying by the hydroelectric energy equivalent of
one cubic metre of water at each dam's effective fall height.

────────────────────────────────────────────────────────────────────────────
PHYSICS
────────────────────────────────────────────────────────────────────────────
  The gravitational potential energy released when 1 m³ of water drops
  through a head of h metres is:

      E  =  η · ρ · g · h        [J / m³]

  where
      ρ = 1 000  kg / m³   (water density)
      g =     9.81  m / s²  (standard gravity)
      h =     effective fall height  [m]
      η =     overall plant efficiency  (turbine × generator × penstock)

  Converting to kWh (1 kWh = 3 600 000 J):

      E_kWh  =  η · ρ · g · h  /  3 600 000    [kWh / m³]

  The water price in EUR/m³ is then:

      price_EUR_m3  =  price_EUR_kWh  ×  E_kWh

────────────────────────────────────────────────────────────────────────────
FALL HEIGHTS  (effective hydraulic head per node)
────────────────────────────────────────────────────────────────────────────
  Estimated from publicly available dam / weir data and elevation surveys:

  Node         Head  Source / basis
  ──────────── ───── ──────────────────────────────────────────────────────
  victoria      30 m  Nalubaale / Owen Falls Dam, Uganda
  southwest      5 m  Sudd floodplain – no major dam; notional weir head
  karthoum      20 m  Jebel Aulia Dam (~10 m) + Sennar influence (~20 m)
  merowe        68 m  Merowe Dam (Hamdab), Sudan
  aswand       111 m  Aswan High Dam (Sadd al-Ali), Egypt
  cairo         10 m  Naga Hammadi Barrage – low-head delta structure
  singa         40 m  Sennar Dam on the Blue Nile
  roseires      68 m  Roseires (Damazin) Dam, Sudan/Ethiopia border
  gerd         145 m  Grand Ethiopian Renaissance Dam
  tana          18 m  Tis Abbay small-head weir / Chara Chara weir
  kashm         53 m  Khashm el Girba (Halfa) Dam, Sudan
  tsengh       185 m  Tekeze Dam (Tekezze), Ethiopia
  ozentari      35 m  Headwater tributary – estimated small-dam head

────────────────────────────────────────────────────────────────────────────
INPUTS / OUTPUTS
────────────────────────────────────────────────────────────────────────────
  Reads  : price_csv/<node>.csv   (date, price_eur_kwh)
  Writes : water_value_csv/<node>.csv   (date, price_eur_m3)
           water_value.png

Usage:
  python3 water_value_estimator.py
  python3 water_value_estimator.py --no-plot
"""

import argparse
import csv
import math
import os
from datetime import date
from pathlib import Path

# ============================================================
# PHYSICS CONSTANTS
# ============================================================

WATER_DENSITY_KG_M3 = 1_000.0   # kg / m³
GRAVITY_M_S2        =     9.81   # m / s²
J_PER_KWH           = 3_600_000.0  # J / kWh

# Overall plant efficiency: turbine (~0.90) × generator (~0.98) × penstock (~0.97)
HYDRO_EFFICIENCY = 0.90 * 0.98 * 0.97   # ≈ 0.856

# ============================================================
# NODE FALL HEIGHTS  (effective hydraulic head, metres)
# ============================================================

NODE_FALL_HEIGHT_M: dict[str, float] = {
    "victoria":   30.0,   # Nalubaale / Owen Falls Dam, Uganda
    "southwest":   5.0,   # Sudd / White Nile floodplain – no major dam
    "karthoum":   20.0,   # Jebel Aulia Dam; Sennar influence
    "merowe":     68.0,   # Merowe Dam (Hamdab), Sudan
    "aswand":    111.0,   # Aswan High Dam (Sadd al-Ali), Egypt
    "cairo":      10.0,   # Naga Hammadi Barrage (low-head delta)
    "singa":      40.0,   # Sennar Dam on the Blue Nile
    "roseires":   68.0,   # Roseires (Damazin) Dam
    "gerd":      145.0,   # Grand Ethiopian Renaissance Dam
    "tana":       18.0,   # Tis Abbay / Chara Chara weir
    "kashm":      53.0,   # Khashm el Girba Dam
    "tsengh":    185.0,   # Tekeze Dam, Ethiopia
    "ozentari":   35.0,   # Headwater tributary, estimated
}


def energy_kwh_per_m3(fall_height_m: float) -> float:
    """
    Energy yield (kWh) from releasing 1 m³ through *fall_height_m* metres,
    accounting for overall plant efficiency.
    """
    return HYDRO_EFFICIENCY * WATER_DENSITY_KG_M3 * GRAVITY_M_S2 * fall_height_m / J_PER_KWH


# ============================================================
# I/O HELPERS
# ============================================================

INPUT_DIR  = "price_csv"
OUTPUT_DIR = "water_value_csv"


def read_price_csv(node_id: str) -> list[tuple[date, float]]:
    """Read price_csv/<node_id>.csv → [(date, price_eur_kwh), ...]."""
    path = Path(INPUT_DIR) / f"{node_id}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")
    result: list[tuple[date, float]] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row["price_eur_kwh"] == "":
                continue
            result.append((date.fromisoformat(row["date"]), float(row["price_eur_kwh"])))
    return result


def write_water_value_csv(node_id: str, series: list[tuple[date, float]]) -> None:
    """Write water_value_csv/<node_id>.csv with columns date, price_eur_m3."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = Path(OUTPUT_DIR) / f"{node_id}.csv"
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "price_eur_m3"])
        for day, price in series:
            if math.isnan(price):
                writer.writerow([day.isoformat(), ""])
            else:
                writer.writerow([day.isoformat(), f"{price:.8f}"])


# ============================================================
# CONVERSION
# ============================================================

def convert_node(node_id: str) -> list[tuple[date, float]]:
    """
    Load EUR/kWh series for *node_id*, apply the fall-height conversion,
    write to output CSV, and return [(date, price_eur_m3), ...].
    """
    kwh_series = read_price_csv(node_id)
    h          = NODE_FALL_HEIGHT_M[node_id]
    factor     = energy_kwh_per_m3(h)            # kWh / m³

    m3_series  = [(day, price * factor) for day, price in kwh_series]
    write_water_value_csv(node_id, m3_series)

    prices = [p for _, p in m3_series]
    mean_kwh = sum(p for _, p in kwh_series) / len(kwh_series)
    print(
        f"  {node_id:12s}  h={h:5.0f} m  "
        f"factor={factor:.5f} kWh/m³  "
        f"mean_input={mean_kwh:.5f} EUR/kWh  "
        f"mean_output={sum(prices)/len(prices):.6f} EUR/m³  "
        f"[{min(prices):.6f} – {max(prices):.6f}]"
    )
    return m3_series


# ============================================================
# PLOT
# ============================================================

# Visual grouping mirrors electricity_price_estimator.py
_SOURCE_ORDER = ["hydro", "solar", "gas", "diesel"]
_SOURCE_LABELS = {
    "hydro":  "Hydro-dominant",
    "solar":  "Solar-dominant",
    "gas":    "Gas / Pipeline",
    "diesel": "Diesel / Off-grid",
}
_REGION_ENERGY: dict[str, tuple[str, str]] = {
    "victoria":  ("hydro",  "gas"),
    "southwest": ("diesel", "solar"),
    "karthoum":  ("hydro",  "gas"),
    "merowe":    ("hydro",  "solar"),
    "aswand":    ("solar",  "hydro"),
    "cairo":     ("gas",    "solar"),
    "singa":     ("hydro",  "gas"),
    "roseires":  ("hydro",  "gas"),
    "gerd":      ("hydro",  "gas"),
    "tana":      ("hydro",  "gas"),
    "kashm":     ("hydro",  "solar"),
    "tsengh":    ("hydro",  "solar"),
    "ozentari":  ("hydro",  "gas"),
}
_SOURCE_PALETTES = {
    "hydro":  ["#1f77b4", "#17becf", "#2ca02c", "#9467bd",
               "#8c564b", "#e377c2", "#bcbd22", "#d62728", "#aec7e8"],
    "solar":  ["#ff7f0e", "#ffbb78", "#d62728", "#f7b6d2"],
    "gas":    ["#2ca02c", "#98df8a", "#c5b0d5", "#7f7f7f"],
    "diesel": ["#8c564b", "#c49c94"],
}
_LINE_STYLES = ["-", "--", "-.", ":", (0, (3, 1, 1, 1))]


def plot_water_values(
    results: dict[str, list[tuple[date, float]]],
    output_file: str | None = "water_value.png",
) -> None:
    """
    Four-panel figure (one per energy-source group) showing the converted
    water opportunity-cost prices in EUR/m³, with a seasonal inset.
    """
    try:
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed – skipping plot  (pip install matplotlib)")
        return

    by_source: dict[str, list[str]] = {s: [] for s in _SOURCE_ORDER}
    for nid in sorted(results):
        by_source[_REGION_ENERGY[nid][0]].append(nid)

    active   = [s for s in _SOURCE_ORDER if by_source[s]]
    n_panels = len(active)

    fig, axes = plt.subplots(
        n_panels, 1, figsize=(18, 4 * n_panels),
        sharex=True, gridspec_kw={"hspace": 0.50},
    )
    if n_panels == 1:
        axes = [axes]

    # ERA5-equivalent date window for the zoom inset
    zoom_start = date(2023, 1, 1)
    zoom_end   = date(2024, 12, 31)

    for ax, source in zip(axes, active):
        node_ids = by_source[source]
        palette  = _SOURCE_PALETTES[source]
        for i, nid in enumerate(node_ids):
            series = results[nid]
            xs = [r[0] for r in series]
            ys = [r[1] for r in series]
            colour = palette[i % len(palette)]
            ls     = _LINE_STYLES[i % len(_LINE_STYLES)]
            h      = NODE_FALL_HEIGHT_M[nid]
            ax.plot(xs, ys, label=f"{nid} (h={h:.0f} m)",
                    linewidth=0.7, alpha=0.85, color=colour, linestyle=ls)

        ax.set_title(f"{_SOURCE_LABELS[source]} regions", fontsize=10, fontweight="bold")
        ax.set_ylabel("EUR / m³", fontsize=9)
        ax.legend(fontsize=8, ncol=4, loc="upper left", framealpha=0.8, borderpad=0.4)
        ax.grid(True, alpha=0.20)
        ax.xaxis.set_major_locator(mdates.YearLocator(10))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

        # Seasonal inset
        ax_in = ax.inset_axes([0.70, 0.50, 0.28, 0.44])
        for i, nid in enumerate(node_ids):
            series = results[nid]
            xs_z = [r[0] for r in series if zoom_start <= r[0] <= zoom_end]
            ys_z = [r[1] for r in series if zoom_start <= r[0] <= zoom_end]
            colour = palette[i % len(palette)]
            ls     = _LINE_STYLES[i % len(_LINE_STYLES)]
            ax_in.plot(xs_z, ys_z, linewidth=1.0, alpha=0.85,
                       color=colour, linestyle=ls, label=nid)
        ax_in.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
        ax_in.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
        ax_in.tick_params(labelsize=6)
        ax_in.set_title("2023–2024", fontsize=7, pad=2)
        ax_in.grid(True, alpha=0.20)

    axes[-1].set_xlabel("Year", fontsize=9)
    fig.suptitle(
        "Water opportunity-cost prices – Nile basin nodes\n"
        "Converted from EUR/kWh using effective dam fall heights  "
        f"(η = {HYDRO_EFFICIENCY:.3f},  E = η·ρ·g·h / 3.6 MJ·kWh⁻¹)",
        fontsize=10,
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
    parser = argparse.ArgumentParser(
        description=(
            "Convert Nile-basin electricity prices (EUR/kWh) to water "
            "opportunity-cost prices (EUR/m³) using effective dam fall heights."
        ),
    )
    parser.add_argument(
        "--no-plot", action="store_true",
        help="Skip plot generation.",
    )
    args = parser.parse_args()

    print(
        f"Physics: η={HYDRO_EFFICIENCY:.4f}, ρ={WATER_DENSITY_KG_M3:.0f} kg/m³, "
        f"g={GRAVITY_M_S2} m/s², 1 kWh = {J_PER_KWH:.0f} J\n"
        f"Conversion: price_EUR_m3 = price_EUR_kWh × (η·ρ·g·h / {J_PER_KWH:.0f})\n"
    )
    print(f"── Reading EUR/kWh CSVs from '{INPUT_DIR}/' ──")

    results: dict[str, list[tuple[date, float]]] = {}
    for node_id in sorted(NODE_FALL_HEIGHT_M):
        try:
            results[node_id] = convert_node(node_id)
        except FileNotFoundError as exc:
            print(f"  [skip] {exc}")

    print(f"\n{len(results)} CSV files written to '{OUTPUT_DIR}/'.\n")

    if not args.no_plot:
        print("── Generating water-value plot ──")
        plot_water_values(results)


if __name__ == "__main__":
    main()
