# NRSM Optimizer

`optimizer/` is a small uv-managed Python package for searching NRSM action
schedules through the fast `nrsm_py` binding.

The first optimizer is multi-objective Pareto search with NSGA-II. That is a
good fit for NRSM because the operating question is inherently a tradeoff:
hydropower value, drinking-water reliability, irrigation reliability, spill,
and storage preservation should be visible separately before a policy is chosen.

## Method

The simulator action contract is one production-release fraction per node per
day. Directly optimizing every daily value is too large for the MVP, so the
optimizer uses a compressed piecewise-constant schedule:

```text
decision variables = ceil(horizon_days / interval_days) * controlled_node_count
```

Each variable is in `[0, 1]`. The optimizer expands that vector into the flat
daily matrix expected by `nrsm_py`:

```text
actions[day * node_count + node_index]
```

The objectives are minimized:

| Objective | Meaning |
| --- | --- |
| `energy_regret` | Baseline full-production energy value minus candidate energy value. |
| `unmet_drink_water` | Total drinking-water shortage. |
| `unmet_food_water` | Total irrigation water shortage. |
| `spill` | Total uncontrolled spill. |
| `terminal_storage_regret` | Baseline terminal reservoir storage minus candidate terminal storage. |

The selected compromise is the Pareto candidate with the smallest normalized
sum of these objectives. The full frontier is written so humans can choose a
different policy afterwards.

## Setup

First build the simulator Python extension:

```powershell
cd ..\crates\nrsm-py
python -m pip install maturin
python -m maturin develop
```

Then run the optimizer package:

```powershell
cd ..\..\optimizer
uv run nrsm-optimize `
  --period ..\scenarios\nile-mvp\past\2005-q1-90d-baseline.yaml `
  --data-dir ..\..\data `
  --generated-dir ..\data\generated\optimizer-2005-q1 `
  --output-dir runs\2005-q1-pareto `
  --interval-days 14 `
  --generations 30 `
  --population-size 48
```

For a faster smoke run, use fewer generations and a smaller population:

```powershell
uv run nrsm-optimize `
  --period ..\scenarios\nile-mvp\past\2005-jan-7d-baseline.yaml `
  --data-dir ..\..\data `
  --generated-dir ..\data\generated\optimizer-smoke `
  --output-dir runs\smoke `
  --interval-days 7 `
  --generations 3 `
  --population-size 12
```

## Outputs

The output directory contains:

- `pareto_candidates.csv`: objective values and simulator summaries for every
  candidate on the final frontier.
- `selected_action_segments.csv`: compressed actions for the selected
  compromise candidate.
- `actions/<node_id>.actions.csv`: daily action CSVs compatible with
  `nrsm-cli --actions-dir`.
- `optimizer_manifest.json`: node order, objective names, baseline metrics, and
  selected candidate metrics.

You can replay the selected policy through the CLI:

```powershell
cargo run -p nrsm-cli -- ..\data\generated\optimizer-smoke\config.yaml `
  --json `
  --results-dir runs\smoke\results `
  --actions-dir runs\smoke\actions `
  --action-column optimized
```

## Benchmark Policies

Use `nrsm-benchmark` to compare simple policies against an optimizer run. It
uses the same `nrsm_py` fast path as the optimizer, then writes standard
simulator CSV result folders that the separate plotting package can read.

```powershell
uv run nrsm-benchmark `
  --period ..\scenarios\nile-mvp\past\2005-jan-7d-baseline.yaml `
  --data-dir ..\..\data `
  --generated-dir ..\data\generated\benchmark-smoke `
  --optimized-actions runs\smoke\actions `
  --output-dir runs\benchmarks\smoke `
  --nodes gerd aswand
```

The benchmark writes:

- `benchmark_summary.csv`: one row per policy with summary metrics,
  reliability ratios, and deltas versus `full_production`.
- `benchmark_manifest.json`: machine-readable paths and summaries.
- `policies/<policy>/actions`: replayable action CSVs.
- `policies/<policy>/results`: standard NRSM result CSVs for plotting.

Built-in policies:

- `full_production`: action `1.0` at every node.
- `no_production`: action `0.0` at every node.
- `constant_50`: action `0.5` at every node.
- `inflow_proxy`: action follows full-production inflow divided by observed
  maximum release.
- `storage_guardrail`: action is reduced where full-production storage falls
  below guardrail levels.
- `optimized`: optional action CSVs from `nrsm-optimize`.

Benchmarking deliberately stays separate from plotting. The benchmark produces
run folders and CSV contracts; `horizon/nrsm/plotting` should own comparison
figures and dashboards.

## Why Not CMA-ES First?

CMA-ES is a strong option once we agree on a single scalar loss. For the current
hackathon stage, Pareto search gives a better review artifact: it lets us show
the cost of more hydropower in drinking-water, irrigation, and spill terms
instead of hiding those choices inside penalty weights.
