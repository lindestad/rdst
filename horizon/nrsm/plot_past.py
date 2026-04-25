"""
Cross-scenario outcome comparison for all past Nile-MVP scenarios.

Runs full (1.0), half (0.5) and none (0.0) production actions across every
scenario YAML found in scenarios/nile-mvp/past/ and produces:

  1. Summary bar charts — key metrics per scenario, grouped by action level.
  2. Time-series overviews — energy value and unmet water for every scenario,
     all three action levels overlaid.
"""

from pathlib import Path

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot import GRID_COLOR, SCENARIO_STYLES, _finish, run_simulation

PAST_DIR = Path(__file__).parent / "scenarios" / "nile-mvp" / "past"
ACTIONS: list[tuple[str, float]] = [
    ("Full (1.0)", 1.0),
    ("Half (0.5)", 0.5),
    ("None (0.0)", 0.0),
]


# ── data loading ──────────────────────────────────────────────────────────────

def load_all_scenarios() -> dict[str, dict[str, tuple]]:
    """
    Returns:
        { scenario_stem: { action_label: (summary_df, nodes_dict) } }
    """
    yaml_files = sorted(PAST_DIR.glob("*.yaml"))
    if not yaml_files:
        raise FileNotFoundError(f"No YAML files found in {PAST_DIR}")

    all_results: dict[str, dict[str, tuple]] = {}
    for yaml_path in yaml_files:
        name = yaml_path.stem
        print(f"  Scenario: {name}")
        scenario_results: dict[str, tuple] = {}
        for label, action in ACTIONS:
            print(f"    {label}")
            scenario_results[label] = run_simulation(yaml_path, action)
        all_results[name] = scenario_results
    return all_results


# ── metric helpers ────────────────────────────────────────────────────────────

def _reliability(met: pd.Series, demand: pd.Series) -> float:
    total = demand.sum()
    return 1.0 if total == 0 else met.sum() / total


def _scenario_totals(summary: pd.DataFrame) -> dict[str, float]:
    """Normalise cumulative volumes to per-day rates for cross-scenario fairness."""
    duration = summary["duration_days"].sum()
    unmet = (summary["total_unmet_drink_water"] + summary["total_unmet_food_water"]).sum()
    drink_demand = summary["total_drink_water_met"] + summary["total_unmet_drink_water"]
    return {
        "duration_days":        duration,
        "energy_per_day":       summary["total_energy_value"].sum() / duration,
        "unmet_water_per_day":  unmet / duration,
        "food_per_day":         summary["total_food_produced"].sum() / duration,
        "drink_reliability":    _reliability(summary["total_drink_water_met"], drink_demand),
        "food_reliability":     _reliability(summary["total_food_water_met"],
                                             summary["total_food_water_demand"]),
    }


# ── plots ─────────────────────────────────────────────────────────────────────

def plot_summary_bars(all_results: dict[str, dict[str, tuple]]) -> None:
    """Grouped bar charts — one row per metric, one group of bars per scenario."""
    scenario_names = list(all_results.keys())
    action_labels  = [a[0] for a in ACTIONS]

    metrics: list[tuple[str, str]] = [
        ("energy_per_day",      "Avg Daily Energy Value"),
        ("unmet_water_per_day", "Avg Daily Unmet Water  (m³/day)"),
        ("food_per_day",        "Avg Daily Food Produced  (units/day)"),
        ("drink_reliability",   "Drinking-Water Reliability  (met / demand)"),
        ("food_reliability",    "Food-Water Reliability  (met / demand)"),
    ]

    # Build data[metric][action_label] = [value per scenario]
    data: dict[str, dict[str, list]] = {
        m: {a: [] for a in action_labels} for m, _ in metrics
    }
    for name in scenario_names:
        for label, _ in ACTIONS:
            summary, _ = all_results[name][label]
            totals = _scenario_totals(summary)
            for m, _ in metrics:
                data[m][label].append(totals[m])

    n  = len(scenario_names)
    w  = 0.25
    xs = np.arange(n)
    short_names = [s[:18] for s in scenario_names]

    fig, axes = plt.subplots(len(metrics), 1, figsize=(max(14, n * 1.4), 4 * len(metrics)))

    for ax, (metric, title) in zip(axes, metrics):
        for i, label in enumerate(action_labels):
            color  = SCENARIO_STYLES[label]["color"]
            offset = (i - 1) * w
            ax.bar(xs + offset, data[metric][label], width=w,
                   color=color, label=label, alpha=0.85)
        ax.set_title(title, fontweight="bold")
        ax.set_xticks(xs)
        ax.set_xticklabels(short_names, rotation=35, ha="right", fontsize=8)
        _finish([ax])

    axes[0].legend(loc="upper right")
    fig.suptitle("Past Scenarios — Outcome Comparison  (Full / Half / None Production)",
                 fontweight="bold")
    fig.tight_layout()


def _legend_handles() -> list:
    return [
        mlines.Line2D([], [], label=label,
                      color=style["color"], linestyle=style["ls"], linewidth=style["lw"])
        for label, style in SCENARIO_STYLES.items()
    ]


def plot_energy_timeseries(all_results: dict[str, dict[str, tuple]]) -> None:
    """Energy value over time — one subplot per past scenario, all actions overlaid."""
    scenario_names = list(all_results.keys())
    n    = len(scenario_names)
    cols = 2
    rows = (n + cols - 1) // cols

    fig, axes_grid = plt.subplots(rows, cols, figsize=(14, 3.5 * rows), squeeze=False)
    flat = [ax for row in axes_grid for ax in row]

    for i, name in enumerate(scenario_names):
        ax = flat[i]
        for label, _ in ACTIONS:
            summary, _ = all_results[name][label]
            sty = SCENARIO_STYLES[label]
            ax.plot(summary["mid_day"], summary["total_energy_value"], **sty)
        ax.set_title(name, fontsize=8)
        ax.set_ylabel("Energy value", fontsize=7)
        ax.tick_params(labelsize=6)
        _finish([ax])

    for ax in flat[n:]:
        ax.set_visible(False)

    flat[0].legend(handles=_legend_handles(), fontsize=7, loc="upper right")
    fig.suptitle("Energy Value Over Time — All Past Scenarios", fontweight="bold")
    fig.tight_layout()


def plot_unmet_timeseries(all_results: dict[str, dict[str, tuple]]) -> None:
    """Total unmet water demand over time — one subplot per past scenario."""
    scenario_names = list(all_results.keys())
    n    = len(scenario_names)
    cols = 2
    rows = (n + cols - 1) // cols

    fig, axes_grid = plt.subplots(rows, cols, figsize=(14, 3.5 * rows), squeeze=False)
    flat = [ax for row in axes_grid for ax in row]

    for i, name in enumerate(scenario_names):
        ax = flat[i]
        for label, _ in ACTIONS:
            summary, _ = all_results[name][label]
            sty   = SCENARIO_STYLES[label]
            unmet = summary["total_unmet_drink_water"] + summary["total_unmet_food_water"]
            ax.plot(summary["mid_day"], unmet, **sty)
        ax.set_title(name, fontsize=8)
        ax.set_ylabel("Unmet water (m³)", fontsize=7)
        ax.tick_params(labelsize=6)
        _finish([ax])

    for ax in flat[n:]:
        ax.set_visible(False)

    flat[0].legend(handles=_legend_handles(), fontsize=7, loc="upper right")
    fig.suptitle("Unmet Water Demand Over Time — All Past Scenarios", fontweight="bold")
    fig.tight_layout()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Running simulations for all past scenarios…")
    all_results = load_all_scenarios()
    print("Plotting…")

    plot_summary_bars(all_results)
    plot_energy_timeseries(all_results)
    plot_unmet_timeseries(all_results)

    plt.show()


if __name__ == "__main__":
    main()
