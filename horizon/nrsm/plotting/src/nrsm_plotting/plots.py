from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from nrsm_plotting.io import ResultBundle


WATER_COLOR = "#276FBF"
RELEASE_COLOR = "#2A9D8F"
LOSS_COLOR = "#C75146"
FOOD_COLOR = "#7A9E3D"
DRINK_COLOR = "#6D597A"
ENERGY_COLOR = "#D9903D"
STORAGE_COLOR = "#374151"
GRID_COLOR = "#E5E7EB"


@dataclass(frozen=True)
class PlotManifest:
    output_dir: Path
    plots: tuple[Path, ...]
    metrics_csv: Path
    manifest_json: Path
    warnings: tuple[str, ...]


def plot_all(
    bundle: ResultBundle,
    output_dir: str | Path,
    *,
    selected_nodes: list[str] | None = None,
    file_format: str = "png",
    dpi: int = 160,
    include_node_plots: bool = True,
) -> PlotManifest:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    node_ids = selected_nodes or bundle.node_ids
    node_ids = [node_id for node_id in node_ids if node_id in bundle.nodes]

    metrics = build_node_metrics(bundle, node_ids)
    metrics_csv = output / "node_metrics.csv"
    metrics.to_csv(metrics_csv, index=False)

    plots: list[Path] = []
    plots.append(_network_water_balance(bundle, output, file_format, dpi))
    plots.append(_network_service_reliability(bundle, output, file_format, dpi))
    plots.append(_network_energy(bundle, output, file_format, dpi))
    plots.append(_node_totals(metrics, output, file_format, dpi))
    plots.append(_node_shortage_heatmap(bundle, node_ids, output, file_format, dpi))

    if include_node_plots:
        node_dir = output / "nodes"
        node_dir.mkdir(exist_ok=True)
        for node_id in node_ids:
            plots.append(_node_detail(node_id, bundle.nodes[node_id], node_dir, file_format, dpi))

    manifest_json = output / "plot_manifest.json"
    manifest = {
        "results_dir": str(bundle.results_dir),
        "output_dir": str(output),
        "node_ids": node_ids,
        "metrics_csv": str(metrics_csv),
        "plots": [str(path) for path in plots],
        "warnings": list(bundle.warnings),
    }
    manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return PlotManifest(
        output_dir=output,
        plots=tuple(plots),
        metrics_csv=metrics_csv,
        manifest_json=manifest_json,
        warnings=bundle.warnings,
    )


def build_node_metrics(bundle: ResultBundle, node_ids: list[str] | None = None) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for node_id in node_ids or bundle.node_ids:
        frame = bundle.nodes[node_id]
        drink_demand = frame["drink_water_met"] + frame["unmet_drink_water"]
        food_demand = frame["food_water_demand"]
        rows.append(
            {
                "node_id": node_id,
                "total_inflow": frame["total_inflow"].sum(),
                "total_evaporation": frame["evaporation"].sum(),
                "total_drink_water_met": frame["drink_water_met"].sum(),
                "total_unmet_drink_water": frame["unmet_drink_water"].sum(),
                "total_food_water_demand": food_demand.sum(),
                "total_food_water_met": frame["food_water_met"].sum(),
                "total_unmet_food_water": frame["unmet_food_water"].sum(),
                "total_production_release": frame["production_release"].sum(),
                "total_spill": frame["spill"].sum(),
                "total_downstream_release": frame["downstream_release"].sum(),
                "total_routing_loss": frame["routing_loss"].sum(),
                "total_energy_value": frame["energy_value"].sum(),
                "mean_action": frame["action"].mean(),
                "min_reservoir_level": frame["reservoir_level"].min(),
                "max_reservoir_level": frame["reservoir_level"].max(),
                "drink_reliability": _safe_ratio(frame["drink_water_met"].sum(), drink_demand.sum()),
                "food_water_reliability": _safe_ratio(
                    frame["food_water_met"].sum(), food_demand.sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _network_water_balance(
    bundle: ResultBundle, output: Path, file_format: str, dpi: int
) -> Path:
    summary = bundle.summary
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    x = summary["mid_day"]

    axes[0].plot(x, summary["total_inflow"], color=WATER_COLOR, label="Inflow")
    axes[0].plot(
        x,
        summary["total_release_for_routing"],
        color=RELEASE_COLOR,
        label="Release for routing",
    )
    axes[0].plot(
        x,
        summary["total_downstream_release"],
        color="#1B998B",
        linestyle="--",
        label="Downstream release",
    )
    axes[0].set_ylabel("Water volume (m3)")
    axes[0].set_title("Network Water Movement")
    axes[0].legend(loc="upper right", ncols=3)

    axes[1].plot(x, summary["total_evaporation"], color=LOSS_COLOR, label="Evaporation")
    axes[1].plot(x, summary["total_drink_water_met"], color=DRINK_COLOR, label="Drinking water met")
    axes[1].plot(
        x,
        summary["total_food_water_demand"],
        color=FOOD_COLOR,
        linestyle=":",
        label="Food-water demand",
    )
    axes[1].plot(x, summary["total_food_water_met"], color=FOOD_COLOR, label="Food-water met")
    axes[1].plot(x, summary["total_routing_loss"], color="#8D3B2D", label="Routing loss")
    axes[1].set_ylabel("Water volume (m3)")
    axes[1].set_xlabel("Simulation day")
    axes[1].set_title("Network Losses And Consumptive Uses")
    axes[1].legend(loc="upper right", ncols=3)

    _finish_axes(axes)
    return _save(fig, output / f"network_water_balance.{file_format}", dpi)


def _network_service_reliability(
    bundle: ResultBundle, output: Path, file_format: str, dpi: int
) -> Path:
    summary = bundle.summary
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    x = summary["mid_day"]

    axes[0].plot(
        x,
        summary["total_unmet_drink_water"],
        color=DRINK_COLOR,
        label="Unmet drinking water",
    )
    axes[0].plot(
        x,
        summary["total_unmet_food_water"],
        color=FOOD_COLOR,
        label="Unmet food water",
    )
    axes[0].fill_between(
        x,
        summary["total_unmet_drink_water"] + summary["total_unmet_food_water"],
        color="#E9C46A",
        alpha=0.25,
        label="Combined shortage",
    )
    axes[0].set_ylabel("Unmet demand (m3)")
    axes[0].set_title("Service Shortfalls")
    axes[0].legend(loc="upper right")

    drink_demand = summary["total_drink_water_met"] + summary["total_unmet_drink_water"]
    food_demand = summary["total_food_water_demand"]
    axes[1].plot(
        x,
        _cumulative_ratio(summary["total_drink_water_met"], drink_demand),
        color=DRINK_COLOR,
        label="Cumulative drinking reliability",
    )
    axes[1].plot(
        x,
        _cumulative_ratio(summary["total_food_water_met"], food_demand),
        color=FOOD_COLOR,
        label="Cumulative food-water reliability",
    )
    axes[1].set_ylim(-0.02, 1.02)
    axes[1].set_ylabel("Delivered / demand")
    axes[1].set_xlabel("Simulation day")
    axes[1].set_title("Cumulative Reliability")
    axes[1].legend(loc="lower right")

    _finish_axes(axes)
    return _save(fig, output / f"network_service_reliability.{file_format}", dpi)


def _network_energy(bundle: ResultBundle, output: Path, file_format: str, dpi: int) -> Path:
    summary = bundle.summary
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    x = summary["mid_day"]

    axes[0].plot(x, summary["total_energy_value"], color=ENERGY_COLOR, label="Energy value")
    axes[0].set_ylabel("Value proxy")
    axes[0].set_title("Network Energy Proxy")
    axes[0].legend(loc="upper right")

    axes[1].plot(
        x,
        summary["total_energy_value"].cumsum(),
        color="#A65F1B",
        label="Cumulative energy value",
    )
    axes[1].set_ylabel("Cumulative value")
    axes[1].set_xlabel("Simulation day")
    axes[1].legend(loc="upper left")

    _finish_axes(axes)
    return _save(fig, output / f"network_energy.{file_format}", dpi)


def _node_totals(metrics: pd.DataFrame, output: Path, file_format: str, dpi: int) -> Path:
    metrics = metrics.sort_values("total_inflow", ascending=False)
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    x = metrics["node_id"]

    axes[0].bar(x, metrics["total_inflow"], color=WATER_COLOR, label="Inflow")
    axes[0].bar(
        x,
        metrics["total_downstream_release"],
        color=RELEASE_COLOR,
        alpha=0.72,
        label="Downstream release",
    )
    axes[0].set_ylabel("m3")
    axes[0].set_title("Per-Node Movement Totals")
    axes[0].legend(loc="upper right")

    axes[1].bar(x, metrics["total_evaporation"], color=LOSS_COLOR, label="Evaporation")
    axes[1].bar(
        x,
        metrics["total_food_water_met"],
        color=FOOD_COLOR,
        alpha=0.72,
        label="Food-water met",
    )
    axes[1].bar(
        x,
        metrics["total_unmet_food_water"],
        bottom=metrics["total_food_water_met"],
        color="#D6A99A",
        label="Unmet food water",
    )
    axes[1].set_ylabel("m3")
    axes[1].set_title("Per-Node Consumptive Uses")
    axes[1].legend(loc="upper right")

    axes[2].bar(x, metrics["total_energy_value"], color=ENERGY_COLOR, label="Energy value")
    axes[2].set_ylabel("Value proxy")
    axes[2].set_title("Per-Node Energy Proxy")
    axes[2].tick_params(axis="x", labelrotation=35)
    axes[2].legend(loc="upper right")

    _finish_axes(axes)
    return _save(fig, output / f"node_totals.{file_format}", dpi)


def _node_shortage_heatmap(
    bundle: ResultBundle,
    node_ids: list[str],
    output: Path,
    file_format: str,
    dpi: int,
) -> Path:
    shortage_by_node: dict[str, pd.Series] = {}
    for node_id in node_ids:
        frame = bundle.nodes[node_id]
        shortage = frame["unmet_drink_water"] + frame["unmet_food_water"]
        shortage_by_node[node_id] = pd.Series(shortage.to_numpy(), index=frame["period_index"])
    data_frame = pd.DataFrame(shortage_by_node).T.fillna(0.0)

    fig, ax = plt.subplots(figsize=(12, max(5, 0.42 * len(node_ids))))
    image = ax.imshow(data_frame.to_numpy(), aspect="auto", interpolation="nearest", cmap="YlOrRd")
    ax.set_title("Node Shortage Heatmap")
    ax.set_ylabel("Node")
    ax.set_xlabel("Output period")
    ax.set_yticks(range(len(node_ids)))
    ax.set_yticklabels(node_ids)
    fig.colorbar(image, ax=ax, label="Unmet water demand (m3)")
    return _save(fig, output / f"node_shortage_heatmap.{file_format}", dpi)


def _node_detail(
    node_id: str, frame: pd.DataFrame, output: Path, file_format: str, dpi: int
) -> Path:
    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    x = frame["mid_day"]

    axes[0].plot(x, frame["reservoir_level"], color=STORAGE_COLOR, label="Reservoir level")
    if frame["action"].abs().sum() > 0:
        action_axis = axes[0].twinx()
        action_axis.plot(x, frame["action"], color="#8F6AC8", alpha=0.65, label="Action")
        action_axis.set_ylim(-0.05, 1.05)
        action_axis.set_ylabel("Action")
    axes[0].set_ylabel("m3")
    axes[0].set_title(f"{node_id}: Storage And Action")
    axes[0].legend(loc="upper left")

    axes[1].plot(x, frame["total_inflow"], color=WATER_COLOR, label="Inflow")
    axes[1].plot(x, frame["production_release"], color=ENERGY_COLOR, label="Production release")
    axes[1].plot(x, frame["downstream_release"], color=RELEASE_COLOR, label="Downstream release")
    axes[1].plot(x, frame["spill"], color="#8D3B2D", linestyle="--", label="Spill")
    axes[1].set_ylabel("m3")
    axes[1].set_title("Movement")
    axes[1].legend(loc="upper right", ncols=2)

    axes[2].plot(x, frame["evaporation"], color=LOSS_COLOR, label="Evaporation")
    axes[2].plot(x, frame["drink_water_met"], color=DRINK_COLOR, label="Drinking water met")
    axes[2].plot(x, frame["food_water_demand"], color=FOOD_COLOR, linestyle=":", label="Food-water demand")
    axes[2].plot(x, frame["food_water_met"], color=FOOD_COLOR, label="Food-water met")
    axes[2].set_ylabel("m3")
    axes[2].set_title("Consumptive Uses")
    axes[2].legend(loc="upper right", ncols=2)

    axes[3].plot(x, frame["unmet_drink_water"], color=DRINK_COLOR, label="Unmet drinking")
    axes[3].plot(x, frame["unmet_food_water"], color=FOOD_COLOR, label="Unmet food water")
    axes[3].plot(x, frame["energy_value"], color=ENERGY_COLOR, label="Energy value")
    axes[3].set_ylabel("m3 / value")
    axes[3].set_xlabel("Simulation day")
    axes[3].set_title("Shortage And Energy")
    axes[3].legend(loc="upper right", ncols=3)

    _finish_axes(axes)
    return _save(fig, output / f"{node_id}.{file_format}", dpi)


def _finish_axes(axes) -> None:
    for ax in axes:
        ax.grid(True, color=GRID_COLOR, linewidth=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)


def _save(fig, path: Path, dpi: int) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 1.0
    return numerator / denominator


def _cumulative_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denom = denominator.cumsum()
    ratio = numerator.cumsum() / denom.where(denom != 0)
    return ratio.fillna(1.0)
