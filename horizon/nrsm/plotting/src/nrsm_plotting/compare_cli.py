from __future__ import annotations

import argparse
from pathlib import Path

from nrsm_plotting.compare import (
    benchmark_summary_path,
    load_named_runs,
    parse_run_specs,
    plot_comparison,
    runs_from_benchmark_dir,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create comparison plots across NRSM result folders."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--runs",
        nargs="+",
        help="Run specs as label=RESULTS_DIR, or bare RESULTS_DIR using folder name.",
    )
    source.add_argument(
        "--benchmark-dir",
        type=Path,
        help="Benchmark output directory containing benchmark_manifest.json or policies/.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write comparison plots.",
    )
    parser.add_argument(
        "--nodes",
        nargs="+",
        help="Optional node ids to include while loading each result folder.",
    )
    parser.add_argument(
        "--format",
        choices=("png", "svg", "pdf"),
        default="png",
        help="Plot file format.",
    )
    parser.add_argument("--dpi", type=int, default=160, help="Raster plot DPI.")
    args = parser.parse_args(argv)

    run_specs = (
        runs_from_benchmark_dir(args.benchmark_dir)
        if args.benchmark_dir
        else parse_run_specs(args.runs)
    )
    benchmark_summary = (
        benchmark_summary_path(args.benchmark_dir)
        if args.benchmark_dir
        else None
    )
    runs = load_named_runs(run_specs, nodes=args.nodes)
    manifest = plot_comparison(
        runs,
        args.output_dir,
        file_format=args.format,
        dpi=args.dpi,
        benchmark_summary=benchmark_summary,
    )

    print(f"Wrote {len(manifest.plots)} comparison plots to {manifest.output_dir}")
    print(f"Wrote comparison summary to {manifest.summary_csv}")
    print(f"Wrote manifest to {manifest.manifest_json}")
    if manifest.warnings:
        print("Warnings:")
        for warning in manifest.warnings:
            print(f"  - {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
