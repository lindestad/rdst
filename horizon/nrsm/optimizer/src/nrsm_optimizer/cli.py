from __future__ import annotations

import argparse
import json
from pathlib import Path

from nrsm_optimizer.objectives import COMPROMISE_MODES
from nrsm_optimizer.pareto import optimize_pareto
from nrsm_optimizer.periods import read_period_start
from nrsm_optimizer.simulator import NrsmSimulator


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Optimize NRSM action schedules.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--period", type=Path, help="Period YAML assembled from horizon/data.")
    source.add_argument("--config", type=Path, help="Already assembled NRSM config YAML.")
    parser.add_argument("--data-dir", type=Path, help="Canonical horizon/data directory.")
    parser.add_argument("--generated-dir", type=Path, help="Dataloader output directory for --period.")
    parser.add_argument("--output-dir", type=Path, default=Path("runs/latest"))
    parser.add_argument("--interval-days", type=int, default=30)
    parser.add_argument("--generations", type=int, default=40)
    parser.add_argument("--population-size", type=int, default=48)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--compromise-mode",
        choices=COMPROMISE_MODES,
        default="energy_food",
        help=(
            "How to select one candidate from the Pareto frontier. "
            "energy_food favors energy and service reliability, balanced keeps "
            "storage in the mix, storage_safe heavily favors water conservation."
        ),
    )
    parser.add_argument("--nodes", nargs="*", help="Limit optimization to specific node ids.")
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

    result = optimize_pareto(
        simulator,
        interval_days=args.interval_days,
        controlled_nodes=args.nodes,
        population_size=args.population_size,
        generations=args.generations,
        seed=args.seed,
        compromise_mode=args.compromise_mode,
    )
    result.write_outputs(args.output_dir, start_date=start_date)

    manifest = {
        "node_ids": result.action_space.node_ids,
        "controlled_nodes": result.action_space.controlled_node_ids,
        "horizon_days": result.action_space.horizon_days,
        "interval_days": result.action_space.interval_days,
        "objective_names": result.objective_names,
        "compromise_mode": result.compromise_mode,
        "selected_candidate": result.best_index,
        "selected_candidate_label": result.candidate_labels[result.best_index],
        "selected_objectives": {
            name: float(value)
            for name, value in zip(result.objective_names, result.best_objectives, strict=True)
        },
        "selected_summary": result.best_summary,
        "baseline_summary": result.baseline_summary,
    }
    (args.output_dir / "optimizer_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
