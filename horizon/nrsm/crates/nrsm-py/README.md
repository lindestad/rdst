# nrsm-py

Python bindings for the NRSM optimizer path. This crate is intentionally thin:
it exposes the Rust simulator's prepared, in-memory API so Python policy code
can run many action rollouts without rewriting YAML or CSV files between runs.

Use this path for training, policy search, and loss-function evaluation. Use
`nrsm-cli --actions-dir` when you want a reproducible file-based run for
debugging, visualization, or handoff to another process.

## Build

From this directory:

```powershell
python -m pip install maturin
python -m maturin develop
```

`maturin develop` builds the Rust extension and installs it into the active
Python environment as `nrsm_py`.

You can also build the Rust side from the workspace root:

```powershell
cd ..\..\..
cargo build -p nrsm-py
```

Cargo build verifies the binding crate compiles, but it does not install the
Python module for `import nrsm_py`.

## Basic Usage: Real Data By Default

Use `from_period` when you want Python to run a named scenario window with the
real CSV-backed data path. The period file only supplies
`settings.start_date`, `settings.end_date`, and optional `settings.node_ids`;
node inputs are assembled from `horizon/data` before the simulator is prepared.

From `horizon/nrsm`:

```python
import json
from pathlib import Path

import nrsm_py

sim = nrsm_py.PreparedScenario.from_period(
    Path("scenarios/nile-mvp/past/1963-september-30d.yaml")
)

actions = [1.0] * sim.expected_action_len()
summary = json.loads(sim.run_actions_summary_json(actions))
```

By default this writes the generated simulator files to
`data/generated/<period-file-name>/` and loads that generated `config.yaml`.
The generated config references CSV module files produced by the dataloader.

If you run from another working directory, pass explicit paths:

```python
sim = nrsm_py.PreparedScenario.from_period(
    r"C:\Users\danie\dev\cassini\horizon\nrsm\scenarios\nile-mvp\past\1963-september-30d.yaml",
    data_dir=r"C:\Users\danie\dev\cassini\horizon\data",
    output_dir=r"C:\Users\danie\dev\cassini\horizon\nrsm\data\generated\1963-september-30d",
)
```

Historical windows must be covered by the source CSVs in `horizon/data`.
Future windows will need an explicit extrapolation step before they can be
assembled through this real-data path.

## Loading Existing YAML

Prepare the scenario once, then reuse it for many rollouts:

```python
import json
from pathlib import Path

import nrsm_py

sim = nrsm_py.PreparedScenario.from_yaml(Path("data/generated/config.yaml"))

actions = [1.0] * sim.expected_action_len()
summary = json.loads(sim.run_actions_summary_json(actions))
```

`from_yaml` reads the YAML config, loads any CSV-backed modules relative to the
config file directory, validates the node graph, and compiles the DAG once.
Use it for an already assembled `data/generated/.../config.yaml`.

Do not call `from_yaml` with a catalog period file such as
`scenarios/nile-mvp/past/1963-september-30d.yaml`; those files intentionally do
not contain simulator nodes. Use `from_period` so Python assembles the real
CSV-backed config first.

## Action Matrix

Action layout is row-major `T x N`:

```text
actions[day * sim.node_count() + node_index]
```

Where:

- `T == sim.horizon_days()`
- `N == sim.node_count()`
- `len(actions) == sim.expected_action_len()`
- `node_index` follows `sim.node_ids()`

Example:

```python
node_ids = sim.node_ids()
gerd_index = node_ids.index("gerd")

horizon = sim.horizon_days()
nodes = sim.node_count()
actions = [1.0] * (horizon * nodes)

for day in range(horizon):
    actions[day * nodes + gerd_index] = 0.5
```

Action values are production-level fractions. Values outside `[0, 1]` are
clamped in Rust. Matrix actions override any `actions.production_level` series
already present in the scenario YAML.

## Methods

`PreparedScenario.from_yaml(path)`

Loads and prepares a simulator from a YAML file. For real-data runs this should
usually be a generated `data/generated/.../config.yaml`.

`PreparedScenario.from_period(path, data_dir=None, output_dir=None)`

Assembles a real-data scenario from a period YAML, then loads the generated
config. `path` must contain `settings.start_date` and `settings.end_date`.
`data_dir` defaults to the repository's `horizon/data` folder when it can be
inferred. `output_dir` defaults to
`horizon/nrsm/data/generated/<period-file-name>/`.

`node_ids() -> list[str]`

Returns the stable node order used by the flat action matrix.

`node_count() -> int`

Returns the number of nodes.

`horizon_days() -> int`

Returns the number of daily timesteps inferred from the scenario settings or
loaded CSV lengths.

`expected_action_len() -> int`

Returns `horizon_days * node_count`.

`run_actions_summary_json(actions) -> str`

Fast optimizer path. Runs the simulator with a flat action matrix and returns
only aggregate summary metrics as JSON. This avoids building the full per-node
time series.

`run_actions_json(actions) -> str`

Debug/visualization path. Runs the simulator with a flat action matrix and
returns the full `SimulationResult` as JSON, including per-node period traces.

`run_configured_json() -> str`

Runs the scenario using actions configured in YAML/CSV, without passing an
override action matrix.

## Optimizer Sketch

```python
import json
import random

import nrsm_py

sim = nrsm_py.PreparedScenario.from_period(
    "scenarios/nile-mvp/past/1963-september-30d.yaml"
)

def evaluate(actions: list[float]) -> float:
    summary = json.loads(sim.run_actions_summary_json(actions))
    energy = summary["total_energy_value"]
    unmet = summary["total_unmet_drink_water"]
    return energy - 1000.0 * unmet

best_actions = None
best_score = float("-inf")

for _ in range(1000):
    candidate = [random.random() for _ in range(sim.expected_action_len())]
    score = evaluate(candidate)
    if score > best_score:
        best_score = score
        best_actions = candidate
```

This interface is simulator-as-environment, not differentiable simulation.
It is suitable for policy search, reinforcement learning environments,
evolutionary search, Bayesian optimization, and neural policies that emit an
action matrix and receive a scalar loss/reward.

## Current Limitations

- Inputs and outputs cross the Python boundary as Python lists and JSON strings.
  That is good enough for the MVP and simple optimizers, but a future version
  should accept NumPy arrays directly and return typed Python objects.
- The simulator is not differentiable through PyTorch/JAX autograd. Treat it as
  a black-box environment.
- `run_actions_json` can allocate a lot for long horizons because it returns
  full per-node traces. Prefer `run_actions_summary_json` inside training loops.
