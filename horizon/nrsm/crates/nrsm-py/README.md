# nrsm-py

Python bindings for the NRSM optimizer path.

The binding prepares a scenario once, then accepts flat action matrices for
repeated fast rollouts:

```python
import json
import nrsm_py

sim = nrsm_py.PreparedScenario.from_yaml("data/generated/config.yaml")
print(sim.node_ids())

actions = [1.0] * sim.expected_action_len()
summary = json.loads(sim.run_actions_summary_json(actions))
```

`run_actions_summary_json` is the optimizer path: it returns aggregate metrics
without building full per-node traces. Use `run_actions_json` when you need the
complete time series for plotting or debugging.

Action layout is row-major `T x N`:

```text
actions[day * sim.node_count() + node_index]
```

`sim.node_ids()` gives the stable node order. Values outside `[0, 1]` are
clamped in Rust.

Build locally with:

```powershell
maturin develop
```

The file-based CLI path still works separately through `nrsm-cli --actions-dir`.
