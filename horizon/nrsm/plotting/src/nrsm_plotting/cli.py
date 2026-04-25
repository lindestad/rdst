from __future__ import annotations

import argparse
from pathlib import Path

from nrsm_plotting.io import load_results
from nrsm_plotting.plots import plot_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create diagnostic plots from NRSM simulator CSV outputs."
    )
    parser.add_argument(
        "--results-dir",
        required=True,
        type=Path,
        help="Directory containing summary.csv and one <node_id>.csv per node.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to write plots. Defaults to <results-dir>/plots.",
    )
    parser.add_argument(
        "--nodes",
        nargs="+",
        help="Optional node ids to include in node-level plots and rollups.",
    )
    parser.add_argument(
        "--format",
        choices=("png", "svg", "pdf"),
        default="png",
        help="Plot file format.",
    )
    parser.add_argument("--dpi", type=int, default=160, help="Raster plot DPI.")
    parser.add_argument(
        "--no-node-plots",
        action="store_true",
        help="Skip per-node detail plots.",
    )

    args = parser.parse_args(argv)
    output_dir = args.output_dir or args.results_dir / "plots"
    bundle = load_results(args.results_dir, nodes=args.nodes)
    manifest = plot_all(
        bundle,
        output_dir,
        selected_nodes=args.nodes,
        file_format=args.format,
        dpi=args.dpi,
        include_node_plots=not args.no_node_plots,
    )

    print(f"Wrote {len(manifest.plots)} plots to {manifest.output_dir}")
    print(f"Wrote metrics to {manifest.metrics_csv}")
    print(f"Wrote manifest to {manifest.manifest_json}")
    if manifest.warnings:
        print("Warnings:")
        for warning in manifest.warnings:
            print(f"  - {warning}")
    return 0

