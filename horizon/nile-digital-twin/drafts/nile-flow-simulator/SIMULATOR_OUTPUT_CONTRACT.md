# NRSM Visualizer Output Contract

The visualizer treats Rust simulator output as a replaceable data source. The UI
consumes a normalized `VisualizerDataset`; only the adapter needs to change when
the Rust file format changes.

## Current Rust output

The current integration target is the CLI `--results-dir` output:

```bash
cd horizon/nrsm
cargo run -p nrsm-cli -- scenarios/nile-mvp/scenario.yaml --json --results-dir data/results/nile-mvp
```

That writes one `<node_id>.csv` per node plus `summary.csv`. The visualizer's
**Load CSVs** control accepts those node CSVs directly. Required per-node
columns are:

- `period_index`
- `start_day`
- `end_day_exclusive`
- `node_id`
- `reservoir_level`
- `total_inflow`
- `evaporation`
- `drink_water_met`
- `unmet_drink_water`
- `food_produced`
- `production_release`
- `spill`
- `release_for_routing`
- `downstream_release`
- `routing_loss`
- `energy_value`

The app currently ignores `summary.csv` because it can compute the plotted
network state from the node files.

## Optional JSON envelope

```json
{
  "schema_version": "nrsm-viz-1",
  "metadata": {
    "name": "Nile run name",
    "source": "nrsm-cli",
    "horizon": "12 monthly periods",
    "reporting": "monthly30_day",
    "units": "model units per reporting period"
  },
  "graph": {
    "nodes": [
      {
        "id": "gerd",
        "name": "GERD",
        "shortName": "GERD",
        "kind": "reservoir",
        "x": 430,
        "y": 365,
        "country": "ETH",
        "capacity": 950,
        "initialStorage": 500
      }
    ],
    "edges": [
      {
        "id": "gerd_to_khartoum",
        "from": "gerd",
        "to": "khartoum",
        "label": "GERD to Khartoum",
        "lossFraction": 0.015
      }
    ]
  },
  "result": {
    "engine_time_step": "daily",
    "timestep_days": 1,
    "reporting": "monthly30_day",
    "summary": {},
    "periods": [
      {
        "period_index": 0,
        "start_day": 0,
        "end_day_exclusive": 30,
        "node_results": [
          {
            "node_id": "gerd",
            "reservoir_level": 500,
            "production_release": 220,
            "energy_value": 4500,
            "evaporation": 0,
            "food_produced": 0,
            "drink_water_met": 0,
            "unmet_drink_water": 0,
            "spill": 0,
            "downstream_release": 220,
            "total_inflow": 260
          }
        ]
      }
    ]
  }
}
```

The app also accepts the current raw `nrsm-cli --json --pretty` result directly.
Without `graph`, it falls back to the built-in Nile MVP graph and infers edge
flows from each node's `downstream_release`.

## Frontend integration

The active framework is in `nile-visualizer-app`:

- `src/adapters/nrsm.ts` maps raw Rust JSON to UI data.
- `src/types.ts` defines the stable UI dataset shape.
- `src/data/nile.ts` contains the packaged sample run.
- `src/App.tsx` provides file loading, period playback, plots, and graph
  visualization.

Keep Rust export changes isolated to the adapter unless the simulator starts
emitting genuinely new concepts that need new UI controls.
