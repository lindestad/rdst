from __future__ import annotations

import argparse
import json
from pathlib import Path

from nrsm_optimizer.benchmarks import run_benchmarks
from nrsm_optimizer.periods import read_period_start
from nrsm_optimizer.simulator import NrsmSimulator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run benchmark NRSM action policies.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--period", type=Path, help="Period YAML assembled from horizon/data.")
    source.add_argument("--config", type=Path, help="Already assembled NRSM config YAML.")
    parser.add_argument("--data-dir", type=Path, help="Canonical horizon/data directory.")
    parser.add_argument("--generated-dir", type=Path, help="Dataloader output directory for --period.")
    parser.add_argument("--output-dir", type=Path, default=Path("runs/benchmarks/latest"))
    parser.add_argument("--optimized-actions", type=Path, help="Optional optimizer action CSV directory.")
    parser.add_argument("--optimized-action-column", default="optimized")
    parser.add_argument("--nodes", nargs="*", help="Limit heuristic policies to specific controlled node ids.")
    args = parser.parse_args(argv)

    if args.period:
        simulator = NrsmSimulator.from_period(
            args.period,
            data_dir=args.data_dir,
            output_dir=args.generated_dir,
        )
        start_date = read_period_start(args.period)
    else:
        simulator = NrsmSimulator.from_yaml(args.config)
        start_date = None

    runs = run_benchmarks(
        simulator,
        args.output_dir,
        optimized_actions_dir=args.optimized_actions,
        optimized_action_column=args.optimized_action_column,
        start_date=start_date,
        controlled_nodes=args.nodes,
    )

    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "policies": [run.name for run in runs],
                "benchmark_summary": str(args.output_dir / "benchmark_summary.csv"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
