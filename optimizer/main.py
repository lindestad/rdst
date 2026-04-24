"""Main script: run the heuristic AND LP global-optimum optimizers for one
year and produce a side-by-side comparison plot.

Run from the optimizer/ directory:

    python3 main.py

Outputs:
    optimizer_results.png  — comparison figure saved next to this script.

Why the LP is the global optimum
---------------------------------
With deterministic (pre-computable) inflows and energy prices, the T-step
optimisation problem has a linear objective and linear constraints.  The
HiGHS LP solver (via scipy.optimize.linprog) finds the exact global optimum
in polynomial time — there are no local optima to escape from.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless environments
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# Allow importing from the sibling node/ package.
NODE_DIR = Path(__file__).parent.parent / "node"
sys.path.insert(0, str(NODE_DIR))

from modules import ConstantInflow, DrinkWaterDemand, FoodProduction
from node import Node, NodeConnection
from simulator import Simulator
from seasonal_modules import SeasonalEnergyPrice, SeasonalInflow
from heuristic import HeuristicOptimizer
from lp_optimizer import LPOptimizer

import datetime

# ---------------------------------------------------------------------------
# Network definition
# ---------------------------------------------------------------------------
# Three-node branching network with seasonal inflow and seasonal energy price:
#
#   upstream_a  (headwater, snowmelt-driven)
#       |
#     65%  35%
#       |    \
#  midstream_b   outlet_c   (leaf nodes)

YEAR_DAYS = 365


def build_simulator() -> Simulator:
    """Construct a three-node simulator with seasonal characteristics."""

    # --- upstream_a ---
    # Snowmelt: high inflow April–June, low in winter.
    inflow_a = SeasonalInflow(base_rate=200.0, amplitude=160.0, peak_day=140)
    price_a = SeasonalEnergyPrice(base_price=0.14, amplitude=0.06)  # peaks in winter

    node_a = Node(
        node_id="upstream_a",
        catchment_inflow=inflow_a,
        reservoir_level=1200.0,
        max_capacity=3000.0,
        max_production=180.0,
        connections=[
            NodeConnection(node_id="midstream_b", fraction=0.65, delay=1),
            NodeConnection(node_id="outlet_c",    fraction=0.35, delay=2),
        ],
        drink_water=DrinkWaterDemand(daily_demand=35.0),
        food_production=FoodProduction(water_coefficient=0.8, max_food_units=60.0),
        energy_price=price_a,
    )

    # --- midstream_b ---
    # Moderate rain-fed inflow, slightly lower seasonal swing.
    inflow_b = SeasonalInflow(base_rate=90.0, amplitude=50.0, peak_day=120)
    price_b = SeasonalEnergyPrice(base_price=0.11, amplitude=0.04)

    node_b = Node(
        node_id="midstream_b",
        catchment_inflow=inflow_b,
        reservoir_level=500.0,
        max_capacity=1500.0,
        max_production=120.0,
        connections=[],
        drink_water=DrinkWaterDemand(daily_demand=20.0),
        food_production=FoodProduction(water_coefficient=0.7, max_food_units=40.0),
        energy_price=price_b,
    )

    # --- outlet_c ---
    # Small, fast-responding catchment.
    inflow_c = SeasonalInflow(base_rate=55.0, amplitude=30.0, peak_day=130)
    price_c = SeasonalEnergyPrice(base_price=0.09, amplitude=0.03)

    node_c = Node(
        node_id="outlet_c",
        catchment_inflow=inflow_c,
        reservoir_level=300.0,
        max_capacity=800.0,
        max_production=70.0,
        connections=[],
        drink_water=DrinkWaterDemand(daily_demand=12.0),
        food_production=FoodProduction(water_coefficient=1.0, max_food_units=25.0),
        energy_price=price_c,
    )

    nodes = {
        "upstream_a":  node_a,
        "midstream_b": node_b,
        "outlet_c":    node_c,
    }
    return Simulator(nodes=nodes, dt_days=1.0)


# ---------------------------------------------------------------------------
# Optimizer setup helpers
# ---------------------------------------------------------------------------

def estimate_max_prices(sim: Simulator, n_steps: int = YEAR_DAYS) -> dict[str, float]:
    """Pre-compute the maximum energy price each node will see over *n_steps*."""
    max_prices: dict[str, float] = {}
    for node_id, node in sim.nodes.items():
        if node.energy_price is None:
            max_prices[node_id] = 1.0
        else:
            prices = [node.energy_price.price(t) for t in range(n_steps)]
            max_prices[node_id] = max(prices)
    return max_prices


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

NODE_COLORS = {
    "upstream_a":  "#1f77b4",
    "midstream_b": "#ff7f0e",
    "outlet_c":    "#2ca02c",
}
NODE_LABELS = {
    "upstream_a":  "Upstream A",
    "midstream_b": "Midstream B",
    "outlet_c":    "Outlet C",
}


def make_date_axis(n_days: int) -> list[datetime.date]:
    """Return a list of calendar dates starting Jan 1 of an arbitrary year."""
    start = datetime.date(2024, 1, 1)
    return [start + datetime.timedelta(days=d) for d in range(n_days)]


def extract_series(history: list[dict], sim: Simulator, node_ids: list[str]) -> dict:
    """Extract per-node time series from a history list."""
    energy_values:  dict[str, list[float]] = {n: [] for n in node_ids}
    energy_prices:  dict[str, list[float]] = {n: [] for n in node_ids}
    reservoir_fill: dict[str, list[float]] = {n: [] for n in node_ids}
    production:     dict[str, list[float]] = {n: [] for n in node_ids}

    for t, step in enumerate(history):
        for nid in node_ids:
            r = step[nid]
            energy_values[nid].append(r.energy_value)
            energy_prices[nid].append(
                sim.nodes[nid].energy_price.price(t)
                if sim.nodes[nid].energy_price else 0.0
            )
            fill = r.reservoir_level / sim.nodes[nid].max_capacity
            reservoir_fill[nid].append(fill * 100.0)
            production[nid].append(r.production_release)

    return dict(
        energy_values=energy_values,
        energy_prices=energy_prices,
        reservoir_fill=reservoir_fill,
        production=production,
    )


def smooth(arr: np.ndarray, w: int = 7) -> np.ndarray:
    """7-day rolling mean."""
    return np.convolve(arr, np.ones(w) / w, mode="same")


def plot_comparison(
    hist_h: list[dict],
    hist_lp: list[dict],
    sim: Simulator,
    node_ids: list[str],
    out_path: Path,
) -> None:
    """Five-panel comparison figure: heuristic vs LP global optimum."""

    dates = make_date_axis(len(hist_h))
    ser_h  = extract_series(hist_h,  sim, node_ids)
    ser_lp = extract_series(hist_lp, sim, node_ids)

    fig, axes = plt.subplots(5, 1, figsize=(14, 20), sharex=True)
    fig.suptitle(
        "Annual Hydro-Optimiser: Heuristic vs LP Global Optimum",
        fontsize=14, y=0.998,
    )

    # ---- Panel 1: Daily energy revenue (total across all nodes) ----
    ax1 = axes[0]
    total_h  = np.array([sum(hist_h[t][n].energy_value  for n in node_ids) for t in range(len(hist_h))])
    total_lp = np.array([sum(hist_lp[t][n].energy_value for n in node_ids) for t in range(len(hist_lp))])
    ax1.plot(dates, smooth(total_h),  color="#e74c3c", label="Heuristic",      linewidth=1.8)
    ax1.plot(dates, smooth(total_lp), color="#2980b9", label="LP (global opt)", linewidth=1.8, linestyle="--")
    ax1.set_ylabel("Total Energy Revenue\n(currency/day)", fontsize=10)
    ax1.set_title("Daily Energy Revenue — all nodes (7-day mean)", fontsize=11)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)

    # ---- Panel 2: Energy price (same for both — just display) ----
    ax2 = axes[1]
    for nid in node_ids:
        ax2.plot(dates, ser_h["energy_prices"][nid],
                 color=NODE_COLORS[nid], label=NODE_LABELS[nid], linewidth=1.5)
    ax2.set_ylabel("Energy Price\n(currency / m³)", fontsize=10)
    ax2.set_title("Energy Price per Node (seasonal — identical for both methods)", fontsize=11)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    # ---- Panel 3: Reservoir fill % (per node, both methods) ----
    ax3 = axes[2]
    for nid in node_ids:
        col = NODE_COLORS[nid]
        ax3.plot(dates, ser_h["reservoir_fill"][nid],
                 color=col, linewidth=1.5, linestyle="-",  alpha=0.7, label=f"{NODE_LABELS[nid]} — Heuristic")
        ax3.plot(dates, ser_lp["reservoir_fill"][nid],
                 color=col, linewidth=1.5, linestyle="--", alpha=0.9, label=f"{NODE_LABELS[nid]} — LP opt")
    ax3.set_ylabel("Reservoir Fill (%)", fontsize=10)
    ax3.set_title("Reservoir Fill Level", fontsize=11)
    ax3.set_ylim(0, 110)
    ax3.legend(fontsize=7, ncol=2, loc="upper right")
    ax3.grid(True, alpha=0.3)

    # ---- Panel 4: Production release (per node, total, smoothed) ----
    ax4 = axes[3]
    for nid in node_ids:
        col = NODE_COLORS[nid]
        ax4.plot(dates, smooth(np.array(ser_h["production"][nid])),
                 color=col, linewidth=1.5, linestyle="-",  alpha=0.7, label=f"{NODE_LABELS[nid]} — Heuristic")
        ax4.plot(dates, smooth(np.array(ser_lp["production"][nid])),
                 color=col, linewidth=1.5, linestyle="--", alpha=0.9, label=f"{NODE_LABELS[nid]} — LP opt")
    ax4.set_ylabel("Production Release\n(m³/day, 7-day mean)", fontsize=10)
    ax4.set_title("Hydropower Production Release per Node", fontsize=11)
    ax4.legend(fontsize=7, ncol=2, loc="upper right")
    ax4.grid(True, alpha=0.3)

    # ---- Panel 5: Cumulative revenue gap (LP − Heuristic) ----
    ax5 = axes[4]
    cum_h  = np.cumsum(total_h)
    cum_lp = np.cumsum(total_lp)
    gap = cum_lp - cum_h
    ax5.fill_between(dates, gap, alpha=0.3, color="#27ae60")
    ax5.plot(dates, gap, color="#27ae60", linewidth=1.8)
    ax5.axhline(0, color="grey", linewidth=0.8, linestyle="--")
    ax5.set_ylabel("Cumulative Revenue Gap\nLP − Heuristic (currency)", fontsize=10)
    ax5.set_title(
        f"Welfare Gain of LP over Heuristic  "
        f"(annual gap: {gap[-1]:+.1f} currency,  "
        f"{gap[-1]/cum_h[-1]*100:+.1f} %)",
        fontsize=11,
    )
    ax5.grid(True, alpha=0.3)

    # X-axis formatting
    ax5.xaxis.set_major_locator(mdates.MonthLocator())
    ax5.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax5.set_xlabel("Month (2024)", fontsize=10)

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Figure saved → {out_path}")


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def print_summary(label: str, history: list[dict], node_ids: list[str]) -> None:
    """Print a simple annual performance summary to stdout."""
    print(f"\n{'=' * 66}")
    print(f"  {label}  ({YEAR_DAYS} daily timesteps)")
    print(f"{'=' * 66}")
    print(f"  {'Node':<14} {'Energy Revenue':>15} {'Production (m³)':>16} {'Food Units':>12}")
    print(f"  {'-' * 62}")

    total_rev = total_food = 0.0
    for nid in node_ids:
        rev  = sum(s[nid].energy_value      for s in history)
        prod = sum(s[nid].production_release for s in history)
        food = sum(s[nid].food_produced      for s in history)
        total_rev  += rev
        total_food += food
        print(f"  {nid:<14} {rev:>15.1f} {prod:>16.1f} {food:>12.1f}")

    print(f"  {'-' * 62}")
    print(f"  {'ALL NODES':<14} {total_rev:>15.1f} {'':>16} {total_food:>12.1f}")
    print(f"{'=' * 66}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # ---- Heuristic optimizer ----------------------------------------
    print("=== Heuristic Optimizer ===")
    sim_h = build_simulator()
    node_ids = list(sim_h.nodes.keys())

    max_prices = estimate_max_prices(sim_h, n_steps=YEAR_DAYS)

    heuristic = HeuristicOptimizer(
        simulator=sim_h,
        spill_threshold=0.80,
        drought_threshold=0.15,
        min_action=0.05,
    )
    for node_id, mp in max_prices.items():
        heuristic.set_max_price(node_id, mp)

    print(f"Running heuristic for {YEAR_DAYS} days …")
    hist_h = heuristic.run(YEAR_DAYS)
    print_summary("Heuristic", hist_h, node_ids)

    # ---- LP global-optimum optimizer ---------------------------------
    print("\n=== LP Global-Optimum Optimizer ===")
    sim_lp = build_simulator()  # fresh simulator (LP reads initial state only)

    lp = LPOptimizer(
        simulator=sim_lp,
        T=YEAR_DAYS,
        energy_weight=1.0,
        food_weight=0.08,  # currency per food unit
        dt=1.0,
    )
    hist_lp, lp_info = lp.solve()
    print(f"  Optimal social welfare: {lp_info['optimal_welfare']:.2f} currency")
    print(f"  LP size: {lp_info['n_vars']} vars, {lp_info['n_constraints']} constraints")
    print_summary("LP Global Optimum", hist_lp, node_ids)

    # ---- Comparison plot ---------------------------------------------
    out_path = Path(__file__).parent / "optimizer_results.png"
    print("\nGenerating comparison plot …")
    plot_comparison(hist_h, hist_lp, sim_lp, node_ids, out_path)
    print("Done.")


if __name__ == "__main__":
    main()
