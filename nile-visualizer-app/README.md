# Fairwater

TypeScript React website for exploring river-basin simulation output.

The site has three hash-routed pages:

- `#/visualization` - the interactive simulator visualization.
- `#/pitch` - general idea, product framing, and project pitch.
- `#/team` - team structure and delivery responsibilities.

The visualization page uses a geography-based Nile map. Nodes are placed from
basin topology coordinates where available, river width follows simulated
release, and decision-impact overlays highlight:

- red/yellow agricultural zones when food-water delivery or production drops,
- red/yellow municipal rings when drinking-water delivery is stressed,
- red/yellow reservoir rings when storage is low,
- red/yellow downstream zones when Delta outflow is reduced.

## Run

```bash
npm install
npm run dev
```

The visualization ships with packaged NRSM scenario results under
`src/data/results/scenarios`. Use the **Run** selector on `#/visualization` to
switch between the default, past, future, extreme, and smoke-test runs without
uploading files.

To refresh the packaged catalog after editing scenarios, run this from the repo
root:

```bash
cd horizon/nrsm
for file in scenarios/nile-mvp/scenario.yaml scenarios/nile-mvp/past/*.yaml scenarios/nile-mvp/future/*.yaml scenarios/nile-mvp/extremes/*.yaml scenarios/nile-mvp/few-nodes/*.yaml; do
  rel=${file#scenarios/nile-mvp/}
  id=${rel%.yaml}
  id=${id//\//__}
  cargo run -q -p nrsm-cli -- "$file" --json --results-dir "../../nile-visualizer-app/src/data/results/scenarios/$id" > "/tmp/nrsm-${id//__/-}.json"
done
```

You can also load ad-hoc saved CSV output from the Rust CLI:

```bash
cd horizon/nrsm
cargo run -p nrsm-cli -- scenarios/nile-mvp/scenario.yaml --json --results-dir data/results/nile-mvp
```

Then use **Load CSVs** and select the generated node CSV files from
`data/results/nile-mvp`. Selecting the whole directory works in browsers that
support directory file inputs; otherwise select all `*.csv` files manually. The
adapter ignores `summary.csv` and builds the period plots from the per-node CSVs.

Use **Load JSON** to load either:

- a current `nrsm-cli --json --pretty <scenario.yaml>` result, using a fallback
  Nile graph, or
- the richer visualizer envelope below, which lets Rust provide topology,
  coordinates, scenario labels, and result data in one file.

```json
{
  "schema_version": "nrsm-viz-1",
  "metadata": {
    "name": "Nile drought stress test",
    "source": "nrsm-cli",
    "horizon": "12 monthly periods",
    "reporting": "monthly30_day",
    "units": "model units per reporting period"
  },
  "graph": {
    "nodes": [
      { "id": "gerd", "name": "GERD", "shortName": "GERD", "kind": "reservoir", "x": 430, "y": 365, "country": "ETH", "capacity": 950, "initialStorage": 500 },
      { "id": "khartoum", "name": "Khartoum", "shortName": "Khartoum", "kind": "river", "x": 465, "y": 255, "country": "SDN" }
    ],
    "edges": [
      { "id": "gerd_to_khartoum", "from": "gerd", "to": "khartoum", "label": "GERD to Khartoum", "lossFraction": 0.015 }
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

The adapter lives in `src/adapters/nrsm.ts`. It currently supports both
`--results-dir` CSVs and raw JSON `SimulationResult`.

## Build

```bash
npm run build
```

## GitHub Pages

The repository includes `.github/workflows/deploy-nile-visualizer.yml`. It builds
this subdirectory and deploys `nile-visualizer-app/dist` to GitHub Pages on
pushes to `main` or `master`, or manually through `workflow_dispatch`.

Before the first deploy, enable GitHub Pages in the repository settings and set
the source to **GitHub Actions**. When the custom domain is ready, add it in the
Pages settings. If the domain needs to be committed instead, add
`nile-visualizer-app/public/CNAME` with the domain name.
