"""
Shared infrastructure for weather-year scenario plots.

Imported by plot_weather.py (baseline reservoirs) and
plot_weather_half.py (half-empty reservoirs).

Action levels
-------------
  0.0 – 1.0  — fixed production fraction, 0.1 steps (11 levels)
  Random      — uniform-random action per period, seeded by start year
                (deterministic and reproducible across runs)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import nrsm_py as _nrsm
from plot import _finish, run_simulation

# ── action / style definitions ────────────────────────────────────────────────

# 0.0, 0.1, … 1.0 mapped through RdYlGn (red=none → yellow=half → green=full)
_cmap = plt.colormaps["RdYlGn"]

_NUMERIC: list[tuple[str, float]] = [(f"{v / 10:.1f}", v / 10) for v in range(11)]

ACTIONS: list[tuple[str, float | str]] = _NUMERIC + [("Random", "random")]
ACTION_LABELS = [a[0] for a in ACTIONS]

SCENARIO_STYLES: dict[str, dict] = {
    label: {"color": mcolors.to_hex(_cmap(val)), "ls": "-", "lw": 1.4}
    for label, val in _NUMERIC
}
SCENARIO_STYLES["Random"] = {"color": "#1F78B4", "ls": "-.", "lw": 1.8}


# ── simulation runner ─────────────────────────────────────────────────────────

def _run(yaml_path: Path, action: float | str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Run a scenario for one action level; handles the 'random' special case."""
    if action == "random":
        sim  = _nrsm.PreparedScenario.from_yaml(str(yaml_path))
        seed = int(yaml_path.stem.split("-")[0])
        rng  = np.random.default_rng(seed)
        actions_list = rng.random(sim.expected_action_len()).tolist()
        return run_simulation(yaml_path, actions_list)
    return run_simulation(yaml_path, action)


# ── data loading ──────────────────────────────────────────────────────────────

def load_scenarios(directory: Path) -> dict[int, dict[str, tuple]]:
    """
    Load and run all scenarios in directory for every action level.

    Returns:
        { start_year: { action_label: (summary_df, nodes_dict) } }
    """
    yaml_files = sorted(directory.glob("*.yaml"))
    if not yaml_files:
        raise FileNotFoundError(f"No YAML files found in {directory}")

    results: dict[int, dict[str, tuple]] = {}
    for yaml_path in yaml_files:
        start_year = int(yaml_path.stem.split("-")[0])
        print(f"  {yaml_path.stem}")
        results[start_year] = {
            label: _run(yaml_path, action) for label, action in ACTIONS
        }
    return results


# ── metric helpers ─────────────────────────────────────────────────────────────

def _reliability(met: pd.Series, demand: pd.Series) -> float:
    total = demand.sum()
    return 1.0 if total == 0 else float(met.sum() / total)


def _totals(summary: pd.DataFrame) -> dict[str, float]:
    duration     = summary["duration_days"].sum()
    drink_demand = summary["total_drink_water_met"] + summary["total_unmet_drink_water"]
    return {
        "energy_per_day":      summary["total_energy_value"].sum() / duration,
        "unmet_water_per_day": (
            summary["total_unmet_drink_water"] + summary["total_unmet_food_water"]
        ).sum() / duration,
        "food_per_day":        summary["total_food_produced"].sum() / duration,
        "drink_reliability":   _reliability(summary["total_drink_water_met"], drink_demand),
        "food_reliability":    _reliability(
            summary["total_food_water_met"], summary["total_food_water_demand"]
        ),
    }


def _build_metric_table(results: dict) -> dict[str, dict[str, pd.Series]]:
    start_years = sorted(results.keys())
    metrics = ["energy_per_day", "unmet_water_per_day", "food_per_day",
               "drink_reliability", "food_reliability"]
    table: dict[str, dict[str, pd.Series]] = {m: {} for m in metrics}
    for label in ACTION_LABELS:
        rows: dict[str, list] = {m: [] for m in metrics}
        for y in start_years:
            summary, _ = results[y][label]
            t = _totals(summary)
            for m in metrics:
                rows[m].append(t[m])
        for m in metrics:
            table[m][label] = pd.Series(rows[m], index=start_years)
    return table


# ── node helpers ──────────────────────────────────────────────────────────────

def _node_ids(results: dict) -> list[str]:
    first = next(iter(results.values()))
    return list(first[ACTION_LABELS[0]][1].keys())


def _n_periods(results: dict) -> int:
    first = next(iter(results.values()))
    return len(first[ACTION_LABELS[0]][0])


def _node_traj(results: dict, label: str, node_id: str, field: str) -> np.ndarray:
    """Return (n_scenarios, n_periods) array for one node field and action label."""
    start_years = sorted(results.keys())
    n_p = _n_periods(results)
    out = np.zeros((len(start_years), n_p))
    for i, y in enumerate(start_years):
        _, nodes = results[y][label]
        if node_id in nodes:
            vals = nodes[node_id][field].to_numpy()
            out[i, : len(vals)] = vals
    return out


# ── legend helper ─────────────────────────────────────────────────────────────

def _legend_handles() -> list:
    return [
        mlines.Line2D([], [], label=label,
                      color=style["color"], linestyle=style["ls"],
                      linewidth=style["lw"])
        for label, style in SCENARIO_STYLES.items()
    ]


# ── drawing primitives ────────────────────────────────────────────────────────

def _draw_fan(
    ax,
    x: np.ndarray,
    trajectories: np.ndarray,
    color: str,
    *,
    alpha_lines: float = 0.04,
    lw_lines: float = 0.4,
    alpha_outer: float = 0.12,
    alpha_inner: float = 0.22,
    lw_median: float = 1.8,
    label: str | None = None,
) -> None:
    """Individual scenario lines (thin, translucent) + percentile bands + median."""
    for traj in trajectories:
        ax.plot(x, traj, color=color, alpha=alpha_lines, linewidth=lw_lines, zorder=1)
    p10 = np.percentile(trajectories, 10, axis=0)
    p25 = np.percentile(trajectories, 25, axis=0)
    p50 = np.percentile(trajectories, 50, axis=0)
    p75 = np.percentile(trajectories, 75, axis=0)
    p90 = np.percentile(trajectories, 90, axis=0)
    ax.fill_between(x, p10, p90, alpha=alpha_outer, color=color, zorder=2)
    ax.fill_between(x, p25, p75, alpha=alpha_inner, color=color, zorder=3)
    ax.plot(x, p50, color=color, linewidth=lw_median, label=label, zorder=4)


def _node_grid(n_nodes: int, cols: int = 3) -> tuple:
    rows = (n_nodes + cols - 1) // cols
    fig, axes_grid = plt.subplots(rows, cols,
                                  figsize=(6.5 * cols, 3.5 * rows),
                                  squeeze=False)
    flat = [ax for row in axes_grid for ax in row]
    for ax in flat[n_nodes:]:
        ax.set_visible(False)
    return fig, flat


# ── plot functions ────────────────────────────────────────────────────────────

def plot_outcome_trends(results: dict, tag: str = "") -> None:
    """Key metrics vs scenario start year, one line + scatter per action level."""
    start_years = sorted(results.keys())
    table       = _build_metric_table(results)

    metric_info = [
        ("energy_per_day",      "Avg daily energy value"),
        ("unmet_water_per_day", "Avg daily unmet water  (m3/day)"),
        ("food_per_day",        "Avg daily food produced  (units/day)"),
        ("drink_reliability",   "Drinking-water reliability"),
        ("food_reliability",    "Food-water reliability"),
    ]

    fig, axes = plt.subplots(len(metric_info), 1,
                             figsize=(14, 3.8 * len(metric_info)), sharex=True)

    for ax, (metric, title) in zip(axes, metric_info):
        for label in ACTION_LABELS:
            sty = SCENARIO_STYLES[label]
            ax.plot(start_years, table[metric][label],
                    color=sty["color"], linestyle=sty["ls"], linewidth=sty["lw"],
                    marker="o", markersize=2.5, label=label)
        ax.set_title(title, fontweight="bold")
        if "reliability" in metric:
            ax.set_ylim(-0.02, 1.05)
        _finish([ax])

    axes[0].legend(handles=_legend_handles(), loc="upper right", fontsize=8)
    axes[-1].set_xlabel("Scenario start year")
    suffix = f"  [{tag}]" if tag else ""
    fig.suptitle(f"Weather-Year Outcome Trends{suffix}", fontweight="bold")
    fig.tight_layout()


def plot_seasonal_inflow_envelope(results: dict, tag: str = "") -> None:
    """Weekly inflow envelope — fan chart with individual scenario lines."""
    WEEKS_PER_YEAR = 52
    start_years    = sorted(results.keys())
    color          = SCENARIO_STYLES["1.0"]["color"]

    profiles = np.zeros((len(start_years), WEEKS_PER_YEAR))
    for i, y in enumerate(start_years):
        summary, _ = results[y]["1.0"]
        profiles[i] = summary["total_inflow"].to_numpy().reshape(5, WEEKS_PER_YEAR).mean(axis=0)

    week_idx = np.arange(WEEKS_PER_YEAR)
    fig, ax  = plt.subplots(figsize=(13, 5))
    _draw_fan(ax, week_idx, profiles, color)

    ax.legend(handles=[
        mlines.Line2D([], [], color=color, linewidth=1.8, label="Median"),
        plt.Rectangle((0, 0), 1, 1, fc=color, alpha=0.43, label="25-75th pct"),
        plt.Rectangle((0, 0), 1, 1, fc=color, alpha=0.15, label="10-90th pct"),
        mlines.Line2D([], [], color=color, alpha=0.35, linewidth=0.5,
                      label="Individual scenarios"),
    ], loc="upper left", fontsize=8)

    ax.set_xlabel("Week of year")
    ax.set_ylabel("Total network inflow per period  (m3)")
    suffix = f"  [{tag}]" if tag else ""
    ax.set_title(f"Seasonal Inflow Envelope — 60 Weather Scenarios{suffix}",
                 fontweight="bold")
    _finish([ax])
    fig.tight_layout()


def plot_reliability_fan(results: dict, tag: str = "") -> None:
    """Cumulative drinking-water reliability fan, one panel per action level."""
    start_years = sorted(results.keys())
    n_p = _n_periods(results)
    x   = np.arange(n_p)

    fig, axes = plt.subplots(1, len(ACTIONS),
                             figsize=(5.5 * len(ACTIONS), 5), sharey=True)

    for ax, (label, _) in zip(axes, ACTIONS):
        sty  = SCENARIO_STYLES[label]
        traj = np.zeros((len(start_years), n_p))
        for i, y in enumerate(start_years):
            summary, _ = results[y][label]
            met    = summary["total_drink_water_met"].cumsum().to_numpy()
            demand = (summary["total_drink_water_met"]
                      + summary["total_unmet_drink_water"]).cumsum().to_numpy()
            with np.errstate(invalid="ignore", divide="ignore"):
                traj[i] = np.where(demand > 0, met / demand, 1.0)
        _draw_fan(ax, x, traj, sty["color"])
        ax.set_title(label, fontweight="bold")
        ax.set_xlabel("Period (week)")
        ax.set_ylim(-0.02, 1.05)
        _finish([ax])

    axes[0].set_ylabel("Cumulative drinking-water reliability")
    suffix = f"  [{tag}]" if tag else ""
    fig.suptitle(f"Reliability Fan — Inter-Scenario Spread{suffix}", fontweight="bold")
    fig.tight_layout()


def plot_reservoir_levels_fan(results: dict, tag: str = "") -> None:
    """Reservoir level per node — fan chart, all action levels overlaid."""
    node_ids = _node_ids(results)
    n_p      = _n_periods(results)
    x        = np.arange(n_p)

    fig, flat = _node_grid(len(node_ids))

    for ax, node_id in zip(flat, node_ids):
        for label, _ in ACTIONS:
            sty  = SCENARIO_STYLES[label]
            traj = _node_traj(results, label, node_id, "reservoir_level")
            _draw_fan(ax, x, traj, sty["color"], label=label)
        ax.set_title(node_id, fontsize=9, fontweight="bold")
        ax.set_ylabel("Reservoir level (m3)", fontsize=7)
        ax.tick_params(labelsize=6)
        _finish([ax])

    flat[0].legend(handles=_legend_handles(), fontsize=7, loc="upper right")
    suffix = f"  [{tag}]" if tag else ""
    fig.suptitle(f"Reservoir Level per Node{suffix}", fontweight="bold")
    fig.tight_layout()


def plot_inflow_per_node_fan(results: dict, tag: str = "") -> None:
    """Total inflow per node — fan chart (action-independent; Full results used)."""
    node_ids = _node_ids(results)
    n_p      = _n_periods(results)
    x        = np.arange(n_p)
    color    = SCENARIO_STYLES["1.0"]["color"]

    fig, flat = _node_grid(len(node_ids))

    for ax, node_id in zip(flat, node_ids):
        traj = _node_traj(results, "1.0", node_id, "total_inflow")
        if traj.max() > 0:
            _draw_fan(ax, x, traj, color)
        else:
            ax.text(0.5, 0.5, "no inflow", transform=ax.transAxes,
                    ha="center", va="center", fontsize=8, color="grey")
        ax.set_title(node_id, fontsize=9, fontweight="bold")
        ax.set_ylabel("Total inflow (m3)", fontsize=7)
        ax.tick_params(labelsize=6)
        _finish([ax])

    suffix = f"  [{tag}]" if tag else ""
    fig.suptitle(f"Total Inflow per Node{suffix}", fontweight="bold")
    fig.tight_layout()


def plot_water_demand_fan(results: dict, tag: str = "") -> None:
    """Water demand met vs total per node — drink (solid) and food (faint), all actions."""
    node_ids = _node_ids(results)
    n_p      = _n_periods(results)
    x        = np.arange(n_p)

    def _has_demand(node_id: str) -> bool:
        for label in ACTION_LABELS:
            for field in ("drink_water_met", "food_water_met"):
                if _node_traj(results, label, node_id, field).max() > 0:
                    return True
        return False

    demand_nodes = [n for n in node_ids if _has_demand(n)]
    if not demand_nodes:
        return

    fig, flat = _node_grid(len(demand_nodes))

    for ax, node_id in zip(flat, demand_nodes):
        for label, _ in ACTIONS:
            sty   = SCENARIO_STYLES[label]
            color = sty["color"]

            met   = _node_traj(results, label, node_id, "drink_water_met")
            unmet = _node_traj(results, label, node_id, "unmet_drink_water")
            dem   = met + unmet
            if dem.max() > 0:
                _draw_fan(ax, x, dem,  color, alpha_lines=0.04,
                          alpha_outer=0.08, alpha_inner=0.16, lw_median=1.4)
                _draw_fan(ax, x, met,  color, alpha_lines=0.04,
                          alpha_outer=0.12, alpha_inner=0.24, lw_median=1.8)

            fmet  = _node_traj(results, label, node_id, "food_water_met")
            funm  = _node_traj(results, label, node_id, "unmet_food_water")
            fdem  = fmet + funm
            if fdem.max() > 0:
                _draw_fan(ax, x, fdem, color, alpha_lines=0.02,
                          alpha_outer=0.05, alpha_inner=0.10,
                          lw_lines=0.3, lw_median=1.0)
                _draw_fan(ax, x, fmet, color, alpha_lines=0.02,
                          alpha_outer=0.05, alpha_inner=0.10,
                          lw_lines=0.3, lw_median=1.0)

        ax.set_title(node_id, fontsize=9, fontweight="bold")
        ax.set_ylabel("Water volume (m3)", fontsize=7)
        ax.tick_params(labelsize=6)
        _finish([ax])

    flat[0].legend(handles=_legend_handles(), fontsize=7, loc="upper right")
    suffix = f"  [{tag}]" if tag else ""
    fig.suptitle(f"Water Demand met vs total  (solid=drink, faint=food){suffix}",
                 fontweight="bold")
    fig.tight_layout()


def plot_energy_per_node_fan(results: dict, tag: str = "") -> None:
    """Energy value per node — fan chart, all action levels overlaid."""
    node_ids = _node_ids(results)

    def _has_energy(node_id: str) -> bool:
        return _node_traj(results, "1.0", node_id, "energy_value").max() > 0

    energy_nodes = [n for n in node_ids if _has_energy(n)]
    if not energy_nodes:
        return

    n_p = _n_periods(results)
    x   = np.arange(n_p)

    fig, flat = _node_grid(len(energy_nodes))

    for ax, node_id in zip(flat, energy_nodes):
        for label, _ in ACTIONS:
            sty  = SCENARIO_STYLES[label]
            traj = _node_traj(results, label, node_id, "energy_value")
            _draw_fan(ax, x, traj, sty["color"], label=label)
        ax.set_title(node_id, fontsize=9, fontweight="bold")
        ax.set_ylabel("Energy value proxy", fontsize=7)
        ax.tick_params(labelsize=6)
        _finish([ax])

    flat[0].legend(handles=_legend_handles(), fontsize=7, loc="upper right")
    suffix = f"  [{tag}]" if tag else ""
    fig.suptitle(f"Energy Value per Node{suffix}", fontweight="bold")
    fig.tight_layout()


def run_all_plots(results: dict, tag: str = "") -> None:
    """Run all seven plot functions for a loaded results dict."""
    plot_outcome_trends(results, tag)
    plot_seasonal_inflow_envelope(results, tag)
    plot_reliability_fan(results, tag)
    plot_reservoir_levels_fan(results, tag)
    plot_inflow_per_node_fan(results, tag)
    plot_water_demand_fan(results, tag)
    plot_energy_per_node_fan(results, tag)
