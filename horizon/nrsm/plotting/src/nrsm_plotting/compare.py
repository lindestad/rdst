from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from nrsm_plotting.io import ResultBundle, load_results
from nrsm_plotting.plots import (
    DRINK_COLOR,
    ENERGY_COLOR,
    FOOD_COLOR,
    GRID_COLOR,
    LOSS_COLOR,
    RELEASE_COLOR,
    STORAGE_COLOR,
    WATER_COLOR,
)


@dataclass(frozen=True)
class NamedRun:
    label: str
    bundle: ResultBundle


@dataclass(frozen=True)
class CompareManifest:
    output_dir: Path
    plots: tuple[Path, ...]
    summary_csv: Path
    manifest_json: Path
    warnings: tuple[str, ...]


def parse_run_specs(specs: Iterable[str]) -> list[tuple[str, Path]]:
    runs: list[tuple[str, Path]] = []
    for spec in specs:
        if "=" in spec:
            label, path = spec.split("=", 1)
            label = label.strip()
        else:
            path = spec
            label = Path(path).name
        if not label:
            raise ValueError(f"empty run label in `{spec}`")
        runs.append((label, Path(path)))
    return runs


def runs_from_benchmark_dir(benchmark_dir: str | Path) -> list[tuple[str, Path]]:
    base = Path(benchmark_dir)
    manifest_path = base / "benchmark_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return [
            (policy["name"], _resolve_benchmark_path(base, Path(policy["results_dir"])))
            for policy in manifest.get("policies", [])
        ]

    policies_dir = base / "policies"
    if not policies_dir.exists():
        raise FileNotFoundError(f"{base} has no benchmark_manifest.json or policies/ directory")
    return [
        (path.name, path / "results")
        for path in sorted(policies_dir.iterdir())
        if path.is_dir() and (path / "results" / "summary.csv").exists()
    ]


def _resolve_benchmark_path(benchmark_dir: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    candidates = [Path.cwd() / path, benchmark_dir / path]
    candidates.extend(parent / path for parent in benchmark_dir.parents)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return path


def load_named_runs(
    run_specs: Iterable[tuple[str, Path]],
    *,
    nodes: list[str] | None = None,
) -> list[NamedRun]:
    runs = [
        NamedRun(label, load_results(path, nodes=nodes))
        for label, path in run_specs
    ]
    if len(runs) < 2:
        raise ValueError("comparison plotting needs at least two runs")
    return runs


def plot_comparison(
    runs: list[NamedRun],
    output_dir: str | Path,
    *,
    file_format: str = "png",
    dpi: int = 160,
) -> CompareManifest:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    summary = build_comparison_summary(runs)
    summary_csv = output / "comparison_summary.csv"
    summary.to_csv(summary_csv, index=False)

    plots = [
        _plot_metric_bars(summary, output, file_format, dpi),
        _plot_reliability(summary, output, file_format, dpi),
        _plot_energy_storage(summary, output, file_format, dpi),
        _plot_shortages_over_time(runs, output, file_format, dpi),
        _plot_actions_over_time(runs, output, file_format, dpi),
    ]

    warnings = tuple(
        f"{run.label}: {warning}"
        for run in runs
        for warning in run.bundle.warnings
    )
    manifest_json = output / "comparison_manifest.json"
    manifest = {
        "output_dir": str(output),
        "runs": [
            {
                "label": run.label,
                "results_dir": str(run.bundle.results_dir),
                "node_ids": run.bundle.node_ids,
            }
            for run in runs
        ],
        "summary_csv": str(summary_csv),
        "plots": [str(path) for path in plots],
        "warnings": list(warnings),
    }
    manifest_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return CompareManifest(
        output_dir=output,
        plots=tuple(plots),
        summary_csv=summary_csv,
        manifest_json=manifest_json,
        warnings=warnings,
    )


def build_comparison_summary(runs: list[NamedRun]) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    baseline = run_totals(runs[0])
    for run in runs:
        totals = run_totals(run)
        row: dict[str, float | str] = {
            "run": run.label,
            "results_dir": str(run.bundle.results_dir),
        }
        row.update(totals)
        for key, value in totals.items():
            if isinstance(value, (float, int)):
                row[f"delta_{key}"] = float(value) - float(baseline.get(key, 0.0))
        rows.append(row)
    return pd.DataFrame(rows)


def run_totals(run: NamedRun) -> dict[str, float]:
    summary = run.bundle.summary
    totals = {
        "total_energy_value": summary["total_energy_value"].sum(),
        "total_generated_electricity_mwh": summary["total_generated_electricity_mwh"].sum(),
        "total_unmet_drink_water": summary["total_unmet_drink_water"].sum(),
        "total_unmet_food_water": summary["total_unmet_food_water"].sum(),
        "total_food_water_demand": summary["total_food_water_demand"].sum(),
        "total_food_water_met": summary["total_food_water_met"].sum(),
        "total_spill": summary["total_spill"].sum(),
        "total_production_release": summary["total_production_release"].sum(),
        "total_downstream_release": summary["total_downstream_release"].sum(),
        "total_routing_loss": summary["total_routing_loss"].sum(),
    }
    if "terminal_reservoir_storage" in summary.columns:
        totals["terminal_reservoir_storage"] = summary["terminal_reservoir_storage"].iloc[-1]
        totals["minimum_reservoir_storage"] = summary["terminal_reservoir_storage"].min()
    else:
        terminal_storage = sum(
            frame["reservoir_level"].iloc[-1]
            for frame in run.bundle.nodes.values()
            if not frame.empty
        )
        min_storage = min(
            sum(frame.iloc[index]["reservoir_level"] for frame in run.bundle.nodes.values())
            for index in range(len(summary))
        )
        totals["terminal_reservoir_storage"] = terminal_storage
        totals["minimum_reservoir_storage"] = min_storage
    totals["drink_water_reliability"] = _safe_ratio(
        summary["total_drink_water_met"].sum(),
        summary["total_drink_water_met"].sum() + summary["total_unmet_drink_water"].sum(),
    )
    totals["food_water_reliability"] = _safe_ratio(
        totals["total_food_water_met"],
        totals["total_food_water_demand"],
    )
    return totals


def _plot_metric_bars(
    summary: pd.DataFrame, output: Path, file_format: str, dpi: int
) -> Path:
    metrics = [
        ("total_energy_value", "Energy Value"),
        ("total_unmet_food_water", "Unmet Food Water"),
        ("total_unmet_drink_water", "Unmet Drinking Water"),
        ("total_spill", "Spill"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    axes_flat = axes.ravel()
    for ax, (column, title) in zip(axes_flat, metrics, strict=True):
        ax.bar(summary["run"], summary[column], color=_color_for_metric(column))
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", color=GRID_COLOR, linewidth=0.8)
    fig.tight_layout()
    return _save(fig, output / f"policy_metric_totals.{file_format}", dpi)


def _plot_reliability(
    summary: pd.DataFrame, output: Path, file_format: str, dpi: int
) -> Path:
    x = range(len(summary))
    width = 0.38
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(
        [value - width / 2 for value in x],
        summary["drink_water_reliability"],
        width=width,
        color=DRINK_COLOR,
        label="Drinking water",
    )
    ax.bar(
        [value + width / 2 for value in x],
        summary["food_water_reliability"],
        width=width,
        color=FOOD_COLOR,
        label="Food water",
    )
    ax.set_xticks(list(x), summary["run"], rotation=25, ha="right")
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("Reliability")
    ax.set_title("Service Reliability By Policy")
    ax.legend()
    ax.grid(axis="y", color=GRID_COLOR, linewidth=0.8)
    fig.tight_layout()
    return _save(fig, output / f"policy_reliability.{file_format}", dpi)


def _plot_energy_storage(
    summary: pd.DataFrame, output: Path, file_format: str, dpi: int
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))
    scatter = ax.scatter(
        summary["terminal_reservoir_storage"],
        summary["total_energy_value"],
        c=summary["total_unmet_food_water"],
        cmap="YlOrRd",
        s=100,
        edgecolor="#111827",
    )
    for _, row in summary.iterrows():
        ax.annotate(str(row["run"]), (row["terminal_reservoir_storage"], row["total_energy_value"]))
    ax.set_xlabel("Terminal Reservoir Storage (m3)")
    ax.set_ylabel("Energy Value")
    ax.set_title("Energy Value Versus Remaining Storage")
    ax.grid(color=GRID_COLOR, linewidth=0.8)
    fig.colorbar(scatter, ax=ax, label="Unmet food water")
    fig.tight_layout()
    return _save(fig, output / f"energy_storage_tradeoff.{file_format}", dpi)


def _plot_shortages_over_time(
    runs: list[NamedRun], output: Path, file_format: str, dpi: int
) -> Path:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for run in runs:
        summary = run.bundle.summary
        x = summary["mid_day"]
        axes[0].plot(x, summary["total_unmet_drink_water"], label=run.label)
        axes[1].plot(x, summary["total_unmet_food_water"], label=run.label)
    axes[0].set_title("Unmet Drinking Water Over Time")
    axes[0].set_ylabel("m3")
    axes[1].set_title("Unmet Food Water Over Time")
    axes[1].set_ylabel("m3")
    axes[1].set_xlabel("Simulation day")
    for ax in axes:
        ax.grid(color=GRID_COLOR, linewidth=0.8)
        ax.legend(loc="upper right")
    fig.tight_layout()
    return _save(fig, output / f"shortages_over_time.{file_format}", dpi)


def _plot_actions_over_time(
    runs: list[NamedRun], output: Path, file_format: str, dpi: int
) -> Path:
    fig, ax = plt.subplots(figsize=(12, 5))
    for run in runs:
        action = pd.concat(
            [frame[["mid_day", "action"]] for frame in run.bundle.nodes.values()],
            ignore_index=True,
        ).groupby("mid_day", as_index=False)["action"].mean()
        ax.plot(action["mid_day"], action["action"], label=run.label)
    ax.set_title("Mean Action Over Time")
    ax.set_xlabel("Simulation day")
    ax.set_ylabel("Mean production action")
    ax.set_ylim(-0.05, 1.05)
    ax.grid(color=GRID_COLOR, linewidth=0.8)
    ax.legend(loc="upper right")
    fig.tight_layout()
    return _save(fig, output / f"mean_actions_over_time.{file_format}", dpi)


def _color_for_metric(column: str) -> str:
    return {
        "total_energy_value": ENERGY_COLOR,
        "total_unmet_food_water": FOOD_COLOR,
        "total_unmet_drink_water": DRINK_COLOR,
        "total_spill": LOSS_COLOR,
        "total_production_release": RELEASE_COLOR,
        "total_inflow": WATER_COLOR,
        "terminal_reservoir_storage": STORAGE_COLOR,
    }.get(column, WATER_COLOR)


def _save(fig, path: Path, dpi: int) -> Path:
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        return 1.0
    return float(numerator) / float(denominator)
