#!/usr/bin/env python3
"""Generate diagnostic plots from nrsm-cli --results-dir CSV output."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Callable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-nrsm")

import matplotlib.pyplot as plt


Row = dict[str, float | str]


def main() -> None:
    args = parse_args()
    results_dir = args.results_dir
    output_dir = args.output_dir or results_dir / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = read_csv(results_dir / "summary.csv")
    node_rows = read_node_results(results_dir)
    if not summary:
        raise SystemExit(f"No summary rows found in {results_dir / 'summary.csv'}")
    if not node_rows:
        raise SystemExit(f"No per-node result CSVs found in {results_dir}")

    plt.style.use("seaborn-v0_8-whitegrid")
    outputs = [
        plot_basin_balance(summary, output_dir),
        plot_key_node_flows(node_rows, output_dir, args.top_nodes),
        plot_reservoir_storage(node_rows, output_dir),
        plot_sector_outputs(summary, node_rows, output_dir),
    ]
    write_index(output_dir, outputs)

    print(f"Wrote {len(outputs)} plots to {output_dir}")
    for path in outputs:
        print(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate matplotlib plots from an NRSM results directory.",
    )
    parser.add_argument(
        "results_dir",
        type=Path,
        help="Directory produced by nrsm-cli --results-dir.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for PNG plots. Defaults to <results_dir>/plots.",
    )
    parser.add_argument(
        "--top-nodes",
        type=int,
        default=8,
        help="Number of highest-release nodes to include in the node-flow plot.",
    )
    return parser.parse_args()


def read_node_results(results_dir: Path) -> dict[str, list[Row]]:
    rows_by_node: dict[str, list[Row]] = {}
    for path in sorted(results_dir.glob("*.csv")):
        if path.name == "summary.csv":
            continue
        rows = read_csv(path)
        if not rows:
            continue
        node_id = str(rows[0].get("node_id") or path.stem)
        rows_by_node[node_id] = rows
    return rows_by_node


def read_csv(path: Path) -> list[Row]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [coerce_row(row) for row in reader]


def coerce_row(row: dict[str, str]) -> Row:
    out: Row = {}
    for key, value in row.items():
        if value is None:
            out[key] = ""
            continue
        try:
            out[key] = float(value)
        except ValueError:
            out[key] = value
    return out


def plot_basin_balance(summary: list[Row], output_dir: Path) -> Path:
    x = period_labels(summary)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    fig.suptitle("NRSM basin-level run summary", fontsize=15, fontweight="bold")

    ax = axes[0][0]
    ax.plot(x, values(summary, "total_inflow"), marker="o", label="Inflow")
    ax.plot(x, values(summary, "total_downstream_release"), marker="o", label="Downstream release")
    ax.plot(x, values(summary, "total_evaporation"), marker="o", label="Evaporation")
    ax.plot(x, values(summary, "total_routing_loss"), marker="o", label="Routing loss")
    style_axis(ax, "Water balance", "model water units")
    ax.legend(fontsize=8)

    ax = axes[0][1]
    ax.bar(x, values(summary, "total_production_release"), label="Production release")
    ax.bar(
        x,
        values(summary, "total_spill"),
        bottom=values(summary, "total_production_release"),
        label="Spill",
    )
    style_axis(ax, "Release composition", "model water units")
    ax.legend(fontsize=8)

    ax = axes[1][0]
    ax.bar(x, values(summary, "total_food_produced"), color="#2f8f5b")
    style_axis(ax, "Food production", "food units")

    ax = axes[1][1]
    ax.plot(x, values(summary, "total_energy_value"), marker="o", color="#b17621")
    style_axis(ax, "Hydropower value proxy", "energy value")

    return save(fig, output_dir / "basin_summary.png")


def plot_key_node_flows(
    node_rows: dict[str, list[Row]],
    output_dir: Path,
    top_nodes: int,
) -> Path:
    ranked = sorted(
        node_rows,
        key=lambda node_id: max(values(node_rows[node_id], "downstream_release") or [0.0]),
        reverse=True,
    )[:top_nodes]

    fig, ax = plt.subplots(figsize=(13, 6), constrained_layout=True)
    for node_id in ranked:
        rows = node_rows[node_id]
        ax.plot(
            period_labels(rows),
            values(rows, "downstream_release"),
            marker="o",
            label=label_from_id(node_id),
        )

    style_axis(ax, "Key node downstream releases", "model water units")
    ax.legend(ncols=2, fontsize=8)
    return save(fig, output_dir / "key_node_releases.png")


def plot_reservoir_storage(node_rows: dict[str, list[Row]], output_dir: Path) -> Path:
    reservoirs = [
        node_id
        for node_id, rows in node_rows.items()
        if max(values(rows, "reservoir_level") or [0.0]) > 0
    ]

    fig, ax = plt.subplots(figsize=(13, 6), constrained_layout=True)
    if reservoirs:
        for node_id in reservoirs:
            rows = node_rows[node_id]
            ax.plot(
                period_labels(rows),
                values(rows, "reservoir_level"),
                marker="o",
                label=label_from_id(node_id),
            )
        ax.legend(ncols=2, fontsize=8)
    else:
        ax.text(0.5, 0.5, "No non-zero reservoir storage in these results", ha="center", va="center")

    style_axis(ax, "Reservoir end-of-period storage", "storage volume")
    return save(fig, output_dir / "reservoir_storage.png")


def plot_sector_outputs(
    summary: list[Row],
    node_rows: dict[str, list[Row]],
    output_dir: Path,
) -> Path:
    x = period_labels(summary)
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), constrained_layout=True)
    fig.suptitle("Sector-relevant outputs", fontsize=15, fontweight="bold")

    ax = axes[0]
    met = values(summary, "total_drink_water_met")
    unmet = values(summary, "total_unmet_drink_water")
    ax.bar(x, met, label="Met")
    ax.bar(x, unmet, bottom=met, label="Unmet")
    style_axis(ax, "Drinking water delivery", "model water units")
    ax.legend(fontsize=8)

    ax = axes[1]
    food_nodes = nodes_with_signal(node_rows, "food_produced")
    plot_stacked_by_node(ax, food_nodes, node_rows, "food_produced", x)
    style_axis(ax, "Food production by node", "food units")
    ax.legend(ncols=3, fontsize=8)

    ax = axes[2]
    energy_nodes = nodes_with_signal(node_rows, "energy_value")
    plot_stacked_by_node(ax, energy_nodes, node_rows, "energy_value", x)
    style_axis(ax, "Hydropower value by node", "energy value")
    ax.legend(ncols=3, fontsize=8)

    return save(fig, output_dir / "sector_outputs.png")


def plot_stacked_by_node(
    ax: plt.Axes,
    node_ids: list[str],
    node_rows: dict[str, list[Row]],
    field: str,
    x: list[str],
) -> None:
    bottom = [0.0] * len(x)
    for node_id in node_ids:
        series = values(node_rows[node_id], field)
        ax.bar(x, series, bottom=bottom, label=label_from_id(node_id))
        bottom = [left + right for left, right in zip(bottom, series)]
    if not node_ids:
        ax.text(0.5, 0.5, f"No non-zero {field}", ha="center", va="center")


def nodes_with_signal(node_rows: dict[str, list[Row]], field: str) -> list[str]:
    return [
        node_id
        for node_id, rows in node_rows.items()
        if sum(values(rows, field)) > 0
    ]


def period_labels(rows: list[Row]) -> list[str]:
    labels = []
    for row in rows:
        start = int(value(row, "start_day"))
        end = int(value(row, "end_day_exclusive"))
        labels.append(f"{start}-{end}")
    return labels


def values(rows: list[Row], field: str) -> list[float]:
    return [value(row, field) for row in rows]


def value(row: Row, field: str) -> float:
    raw = row.get(field, 0.0)
    return raw if isinstance(raw, float) else 0.0


def label_from_id(node_id: str) -> str:
    return node_id.replace("_", " ").title()


def style_axis(ax: plt.Axes, title: str, ylabel: str) -> None:
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("day window")
    ax.tick_params(axis="x", rotation=0)
    ax.grid(True, axis="y", alpha=0.25)
    ax.grid(False, axis="x")


def save(fig: plt.Figure, path: Path) -> Path:
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def write_index(output_dir: Path, paths: list[Path]) -> None:
    cards = "\n".join(
        f'<section><h2>{path.stem.replace("_", " ").title()}</h2><img src="{path.name}" alt="{path.stem}"></section>'
        for path in paths
    )
    (output_dir / "index.html").write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NRSM result plots</title>
  <style>
    body {{ margin: 0; padding: 24px; font-family: system-ui, sans-serif; background: #f3f5f7; color: #1f2732; }}
    main {{ display: grid; gap: 18px; max-width: 1280px; margin: 0 auto; }}
    section {{ padding: 16px; border: 1px solid #d6dde3; border-radius: 8px; background: white; }}
    h1, h2 {{ margin: 0 0 12px; }}
    h1 {{ font-size: 24px; }}
    h2 {{ font-size: 17px; }}
    img {{ display: block; width: 100%; height: auto; }}
  </style>
</head>
<body>
  <main>
    <h1>NRSM result plots</h1>
    {cards}
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
