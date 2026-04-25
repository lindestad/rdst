"""
Interactive plotting for the NRSM simulator.

Compares three action scenarios (full / half / no production) on the base scenario.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import pandas as pd
import nrsm_py

# ── colour palette (matches nrsm_plotting) ────────────────────────────────────
WATER_COLOR   = "#276FBF"
RELEASE_COLOR = "#2A9D8F"
LOSS_COLOR    = "#C75146"
FOOD_COLOR    = "#7A9E3D"
DRINK_COLOR   = "#6D597A"
ENERGY_COLOR  = "#D9903D"
STORAGE_COLOR = "#374151"
GRID_COLOR    = "#E5E7EB"

# One colour + linestyle per scenario
SCENARIO_STYLES: dict[str, dict] = {
    "Full (1.0)": {"color": "#1D6FA4", "ls": "-",  "lw": 2.0},
    "Half (0.5)": {"color": "#E07B39", "ls": "--", "lw": 1.8},
    "None (0.0)": {"color": "#7B2D8B", "ls": ":",  "lw": 1.8},
}

SCENARIO_YAML = Path(__file__).parent / "scenarios" / "nile-annual-daily" / "scenario.yaml"

# Type alias for a dict of label → (summary_df, nodes_dict)
Scenarios = dict[str, tuple[pd.DataFrame, dict[str, pd.DataFrame]]]


# ── data loading ──────────────────────────────────────────────────────────────

def run_scenarios() -> Scenarios:
    """Run all comparison scenarios and return results keyed by label."""
    scenarios = {}
    for label, action in [("Full (1.0)", 1.0), ("Half (0.5)", 0.5), ("None (0.0)", 0.0)]:
        print(f"  Running scenario: {label}…")
        scenarios[label] = run_simulation(SCENARIO_YAML, action)
    return scenarios


def run_simulation(yaml_path: Path, action: float | list[float] = 1.0) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Run the scenario and return (summary_df, nodes_dict).

    action may be a scalar (applied uniformly) or a pre-built list of floats
    whose length matches sim.expected_action_len().
    """
    sim = nrsm_py.PreparedScenario.from_yaml(str(yaml_path))
    actions = action if isinstance(action, list) else [action] * sim.expected_action_len()
    result = json.loads(sim.run_actions_json(actions))

    summary_rows = []
    nodes_by_id: dict[str, list[dict]] = {}

    for period in result["periods"]:
        pi   = period["period_index"]
        s    = period["start_day"]
        e    = period["end_day_exclusive"]
        dur  = e - s
        mid  = (s + e) / 2.0

        period_totals: dict[str, float] = {
            "period_index": pi, "start_day": s, "end_day_exclusive": e,
            "duration_days": dur, "mid_day": mid,
            "total_inflow": 0, "total_evaporation": 0,
            "total_drink_water_met": 0, "total_unmet_drink_water": 0,
            "total_food_water_demand": 0, "total_food_water_met": 0,
            "total_unmet_food_water": 0, "total_food_produced": 0,
            "total_production_release": 0, "total_spill": 0,
            "total_release_for_routing": 0, "total_downstream_release": 0,
            "total_routing_loss": 0, "total_energy_value": 0,
        }

        for nr in period["node_results"]:
            node_id = nr["node_id"]
            row = {
                "period_index": pi, "start_day": s, "end_day_exclusive": e,
                "duration_days": dur, "mid_day": mid,
                "action": nr.get("action", 0),
                "reservoir_level": nr.get("reservoir_level", 0),
                "total_inflow": nr.get("total_inflow", 0),
                "evaporation": nr.get("evaporation", 0),
                "drink_water_met": nr.get("drink_water_met", 0),
                "unmet_drink_water": nr.get("unmet_drink_water", 0),
                "food_water_demand": nr.get("food_water_demand", 0),
                "food_water_met": nr.get("food_water_met", 0),
                "unmet_food_water": nr.get("unmet_food_water", 0),
                "food_produced": nr.get("food_produced", 0),
                "production_release": nr.get("production_release", 0),
                "spill": nr.get("spill", 0),
                "downstream_release": nr.get("downstream_release", 0),
                "routing_loss": nr.get("routing_loss", 0),
                "energy_value": nr.get("energy_value", 0),
            }
            row["release_for_routing"] = row["production_release"] + row["spill"]
            nodes_by_id.setdefault(node_id, []).append(row)

            period_totals["total_inflow"]              += row["total_inflow"]
            period_totals["total_evaporation"]         += row["evaporation"]
            period_totals["total_drink_water_met"]     += row["drink_water_met"]
            period_totals["total_unmet_drink_water"]   += row["unmet_drink_water"]
            period_totals["total_food_water_demand"]   += row["food_water_demand"]
            period_totals["total_food_water_met"]      += row["food_water_met"]
            period_totals["total_unmet_food_water"]    += row["unmet_food_water"]
            period_totals["total_food_produced"]       += row["food_produced"]
            period_totals["total_production_release"]  += row["production_release"]
            period_totals["total_spill"]               += row["spill"]
            period_totals["total_release_for_routing"] += row["release_for_routing"]
            period_totals["total_downstream_release"]  += row["downstream_release"]
            period_totals["total_routing_loss"]        += row["routing_loss"]
            period_totals["total_energy_value"]        += row["energy_value"]

        summary_rows.append(period_totals)

    summary_df = pd.DataFrame(summary_rows).sort_values("period_index").reset_index(drop=True)
    nodes: dict[str, pd.DataFrame] = {
        nid: pd.DataFrame(rows).sort_values("period_index").reset_index(drop=True)
        for nid, rows in nodes_by_id.items()
    }
    return summary_df, nodes


# ── helpers ───────────────────────────────────────────────────────────────────

def _finish(axes) -> None:
    for ax in (axes if hasattr(axes, "__iter__") else [axes]):
        ax.grid(True, color=GRID_COLOR, linewidth=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)


def _scenario_legend(ax) -> None:
    """Add a legend entry for each scenario using its colour + linestyle."""
    handles = [
        mlines.Line2D([], [], label=label, **{k: v for k, v in style.items() if k != "lw"},
                      linewidth=style["lw"])
        for label, style in SCENARIO_STYLES.items()
    ]
    ax.legend(handles=handles, loc="upper right")


def _safe_ratio(num: float, den: float) -> float:
    return 1.0 if den == 0 else num / den


def _cumulative_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    d = den.cumsum()
    return (num.cumsum() / d.where(d != 0)).fillna(1.0)


# ── plots ─────────────────────────────────────────────────────────────────────

def plot_network_water_balance(scenarios: Scenarios) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    for label, (summary, _) in scenarios.items():
        sty = SCENARIO_STYLES[label]
        x   = summary["mid_day"]
        axes[0].plot(x, summary["total_inflow"],              **sty)
        axes[1].plot(x, summary["total_drink_water_met"],     **sty)
        axes[1].plot(x, summary["total_food_water_met"],      **sty, alpha=0.6)
        axes[1].plot(x, summary["total_evaporation"],         **sty, alpha=0.4)

    axes[0].set_ylabel("Total inflow (m³)")
    axes[0].set_title("Total Network Inflow")
    axes[1].set_ylabel("Water volume (m³)")
    axes[1].set_xlabel("Simulation day (period midpoint)")
    axes[1].set_title("Consumptive Uses  (solid=drinking, dashed-alpha=food, faint=evaporation)")

    _scenario_legend(axes[0])
    _finish(axes)
    fig.suptitle("Network Water Balance", fontweight="bold")
    fig.tight_layout()


def plot_service_reliability(scenarios: Scenarios) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    for label, (summary, _) in scenarios.items():
        sty = SCENARIO_STYLES[label]
        x   = summary["mid_day"]
        total_unmet = summary["total_unmet_drink_water"] + summary["total_unmet_food_water"]
        axes[0].plot(x, total_unmet, **sty)

        drink_demand = summary["total_drink_water_met"] + summary["total_unmet_drink_water"]
        axes[1].plot(
            x, _cumulative_ratio(summary["total_drink_water_met"], drink_demand),
            **sty,
        )
        axes[1].plot(
            x, _cumulative_ratio(summary["total_food_water_met"], summary["total_food_water_demand"]),
            **{**sty, "alpha": 0.55},
        )

    axes[0].set_ylabel("Unmet demand (m³)")
    axes[0].set_title("Total Unmet Water Demand")
    axes[1].set_ylim(-0.02, 1.05)
    axes[1].set_ylabel("Delivered / demand")
    axes[1].set_xlabel("Simulation day (period midpoint)")
    axes[1].set_title("Cumulative Reliability  (solid=drinking, faint=food)")

    _scenario_legend(axes[0])
    _finish(axes)
    fig.suptitle("Service Reliability", fontweight="bold")
    fig.tight_layout()


def plot_energy(scenarios: Scenarios) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)

    for label, (summary, _) in scenarios.items():
        sty = SCENARIO_STYLES[label]
        x   = summary["mid_day"]
        axes[0].plot(x, summary["total_energy_value"],            **sty)
        axes[1].plot(x, summary["total_energy_value"].cumsum(),   **sty)

    axes[0].set_ylabel("Energy value proxy")
    axes[0].set_title("Energy Value per Period")
    axes[1].set_ylabel("Cumulative value")
    axes[1].set_xlabel("Simulation day (period midpoint)")
    axes[1].set_title("Cumulative Energy Value")

    _scenario_legend(axes[0])
    _finish(axes)
    fig.suptitle("Network Energy Proxy", fontweight="bold")
    fig.tight_layout()


def plot_node_totals(scenarios: Scenarios) -> None:
    """Bar chart per node — grouped bars for each scenario."""
    import numpy as np

    labels = list(scenarios)
    all_node_ids: list[str] = list(next(iter(scenarios.values()))[1].keys())

    def _node_metrics(nodes: dict[str, pd.DataFrame]) -> pd.DataFrame:
        rows = []
        for node_id in all_node_ids:
            frame = nodes[node_id]
            drink_demand = frame["drink_water_met"] + frame["unmet_drink_water"]
            rows.append({
                "node_id":       node_id,
                "total_inflow":  frame["total_inflow"].sum(),
                "total_downstream": frame["downstream_release"].sum(),
                "total_food_met":   frame["food_water_met"].sum(),
                "total_unmet_food": frame["unmet_food_water"].sum(),
                "total_energy":     frame["energy_value"].sum(),
            })
        return pd.DataFrame(rows)

    # Sort nodes by full-production inflow
    base_metrics = _node_metrics(scenarios[labels[0]][1])
    order = base_metrics.sort_values("total_inflow", ascending=False)["node_id"].tolist()

    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    n  = len(order)
    w  = 0.25
    xs = np.arange(n)
    colours = [SCENARIO_STYLES[l]["color"] for l in labels]

    for i, label in enumerate(labels):
        m = _node_metrics(scenarios[label][1]).set_index("node_id").loc[order]
        offset = (i - 1) * w
        axes[0].bar(xs + offset, m["total_inflow"],      width=w, color=colours[i], label=label, alpha=0.85)
        axes[1].bar(xs + offset, m["total_food_met"],    width=w, color=colours[i], alpha=0.85)
        axes[1].bar(xs + offset, m["total_unmet_food"],  width=w, color=colours[i], alpha=0.35,
                    bottom=m["total_food_met"])
        axes[2].bar(xs + offset, m["total_energy"],      width=w, color=colours[i], alpha=0.85)

    axes[0].set_ylabel("m³")
    axes[0].set_title("Total Inflow per Node")
    axes[0].legend()
    axes[1].set_ylabel("m³")
    axes[1].set_title("Food Water Met (solid) + Unmet (faded) per Node")
    axes[2].set_ylabel("Value proxy")
    axes[2].set_title("Energy Value per Node")
    axes[2].set_xticks(xs)
    axes[2].set_xticklabels(order, rotation=35, ha="right")

    _finish(axes)
    fig.suptitle("Per-Node Totals", fontweight="bold")
    fig.tight_layout()


def plot_shortage_heatmap(scenarios: Scenarios) -> None:
    """One heatmap row per scenario, side by side."""
    labels    = list(scenarios)
    node_ids  = sorted(next(iter(scenarios.values()))[1].keys())
    n_periods = len(next(iter(scenarios.values()))[0])

    fig, axes = plt.subplots(1, len(labels), figsize=(5 * len(labels), max(5, 0.4 * len(node_ids))),
                             sharey=True)

    for ax, label in zip(axes, labels):
        _, nodes = scenarios[label]
        data = {}
        for nid in node_ids:
            frame = nodes[nid]
            shortage = frame["unmet_drink_water"] + frame["unmet_food_water"]
            data[nid] = pd.Series(shortage.to_numpy(), index=frame["period_index"])
        df = pd.DataFrame(data).T.fillna(0.0)
        img = ax.imshow(df.to_numpy(), aspect="auto", cmap="YlOrRd", interpolation="nearest",
                        vmin=0)
        ax.set_title(label, fontweight="bold")
        ax.set_xticks(range(n_periods))
        ax.set_xticklabels([f"P{i}" for i in range(n_periods)])
        ax.set_xlabel("Period")
        fig.colorbar(img, ax=ax, label="Unmet (m³)", shrink=0.8)

    axes[0].set_yticks(range(len(node_ids)))
    axes[0].set_yticklabels(node_ids)
    fig.suptitle("Node Shortage Heatmap — Scenario Comparison", fontweight="bold")
    fig.tight_layout()


def plot_reservoir_levels(scenarios: Scenarios) -> None:
    """Reservoir storage for every node, one subplot each, all scenarios overlaid."""
    all_node_ids = list(next(iter(scenarios.values()))[1].keys())

    cols = 3
    rows = (len(all_node_ids) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(7 * cols, 3.5 * rows),
                             sharex=True, squeeze=False)
    flat = [ax for row in axes for ax in row]

    for ax, node_id in zip(flat, all_node_ids):
        for label, (_, nodes) in scenarios.items():
            sty   = SCENARIO_STYLES[label]
            frame = nodes[node_id]
            ax.plot(frame["mid_day"], frame["reservoir_level"], **sty, label=label)
        ax.set_title(node_id, fontsize=9)
        ax.set_ylabel("m³", fontsize=8)
        ax.tick_params(labelsize=7)
        _finish([ax])

    for ax in flat[len(all_node_ids):]:
        ax.set_visible(False)

    # Shared x-label on bottom row
    for ax in flat[len(all_node_ids) - cols: len(all_node_ids)]:
        ax.set_xlabel("Day", fontsize=8)

    flat[0].legend(fontsize=8)
    fig.suptitle("Reservoir Levels — All Nodes, Scenario Comparison", fontweight="bold")
    fig.tight_layout()


def plot_simulation_flows(scenarios: Scenarios) -> None:
    """
    Time-series of the key physical flows in the basin, one subplot each.

    Volumes are converted to average daily rates (m³/day) for comparability
    across periods of different length.

    Panels:
      • Natural inflow rate  – external water entering the system
                               (≈ total_inflow − total_downstream_release)
      • Upstream routing     – inter-node water passing (total_downstream_release)
      • Evaporation rate
      • Drinking-water usage – demand (dashed) vs met (solid)
      • Spillage rate
      • Energy production
    """
    fig, axes = plt.subplots(3, 2, figsize=(14, 11), sharex=True)
    ax_nat, ax_route, ax_evap, ax_drink, ax_spill, ax_energy = axes.flat

    for label, (summary, _) in scenarios.items():
        sty  = SCENARIO_STYLES[label]
        x    = summary["mid_day"]
        dur  = summary["duration_days"]

        # convert volumes to average daily rates
        nat_inflow  = (summary["total_inflow"] - summary["total_downstream_release"]) / dur
        routing     = summary["total_downstream_release"] / dur
        evap        = summary["total_evaporation"] / dur
        drink_met   = summary["total_drink_water_met"] / dur
        drink_dem   = (summary["total_drink_water_met"] + summary["total_unmet_drink_water"]) / dur
        spill       = summary["total_spill"] / dur
        energy      = summary["total_energy_value"] / dur

        ax_nat.plot(x,   nat_inflow,           **sty)
        ax_route.plot(x, routing,              **sty)
        ax_evap.plot(x,  evap,                 **sty)
        ax_drink.plot(x, drink_dem,            **{**sty, "ls": "--", "alpha": 0.55})
        ax_drink.plot(x, drink_met,            **sty)
        ax_spill.plot(x, spill,                **sty)
        ax_energy.plot(x, energy,              **sty)

    ax_nat.set_title("Natural inflow\n(inflow − inter-node routing)")
    ax_nat.set_ylabel("m³/day")

    ax_route.set_title("Upstream routing flow\n(total inter-node release)")
    ax_route.set_ylabel("m³/day")

    ax_evap.set_title("Evaporation")
    ax_evap.set_ylabel("m³/day")

    ax_drink.set_title("Drinking-water demand (dashed) vs met (solid)")
    ax_drink.set_ylabel("m³/day")
    ax_drink.set_xlabel("Simulation day (period midpoint)")

    ax_spill.set_title("Spillage")
    ax_spill.set_ylabel("m³/day")
    ax_spill.set_xlabel("Simulation day (period midpoint)")

    ax_energy.set_title("Energy production value")
    ax_energy.set_ylabel("value/day")
    ax_energy.set_xlabel("Simulation day (period midpoint)")

    _scenario_legend(ax_nat)
    _finish(axes.flat)
    fig.suptitle("Basin Physical Flows Over Time", fontweight="bold")
    fig.tight_layout()


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("Running simulations…")
    scenarios = run_scenarios()
    print("Plotting…")

    plot_network_water_balance(scenarios)
    plot_service_reliability(scenarios)
    plot_energy(scenarios)
    plot_node_totals(scenarios)
    plot_shortage_heatmap(scenarios)
    plot_reservoir_levels(scenarios)
    plot_simulation_flows(scenarios)

    plt.show()


if __name__ == "__main__":
    main()
