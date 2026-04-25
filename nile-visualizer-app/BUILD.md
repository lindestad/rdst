# Nile Visualizer — Build & Run

The app lives in `nile-visualizer-app/` (Vite + React + TypeScript). Simulation
data comes from the Rust `nrsm-cli` in `horizon/nrsm/`.

## Prerequisites
- Node.js (with `npm`) — for the web app
- Rust toolchain (`cargo`) — for generating simulation data

## 1. Generate simulation data (Rust)

From the repo root:

```bash
cd horizon/nrsm
cargo run -p nrsm-cli -- scenarios/nile-mvp/scenario.yaml \
    --json --pretty \
    --results-dir data/results/nile-mvp
```

CLI usage:

```
nrsm-cli <SCENARIO_PATH> [--output yaml|json] [--json] [--yaml] [--pretty]
                         [--results-dir DIR] [--actions-dir DIR]
                         [--action-column COLUMN]
```

- `--results-dir DIR` writes per-node CSVs (plus `summary.csv`) to `DIR`. The
  visualizer's **Load CSVs** button consumes this directory.
- `--json --pretty` (without `--results-dir`) prints a single JSON
  `SimulationResult` to stdout — redirect it to a file and load it via
  **Load JSON**.
- For a release-speed run, swap `cargo run` for `cargo run --release`.

Other scenarios live under `horizon/nrsm/scenarios/`.

## 2. Run the visualizer dev server

```bash
cd nile-visualizer-app
npm install
npm run dev
```
Open the URL Vite prints (default `http://127.0.0.1:5173`).

## 3. Production build

```bash
cd nile-visualizer-app
npm install        # first time only
npm run build      # outputs to nile-visualizer-app/dist
npm run preview    # optional: serve the built bundle locally
```

## Loading data in the UI

The site has three hash routes: `#/visualization`, `#/pitch`, `#/team`.

On `#/visualization`, load simulator output via either button:

- **Load CSVs** — select the directory written by `--results-dir` (or all
  `*.csv` files in it). `summary.csv` is ignored; period plots are built from
  the per-node CSVs.
- **Load JSON** — either a raw `nrsm-cli --json --pretty <scenario.yaml>`
  result, or the richer `schema_version: "nrsm-viz-1"` envelope (graph +
  result in one file). Adapter: `src/adapters/nrsm.ts`.

## Deploy
Pushes to `main`/`master` trigger `.github/workflows/deploy-nile-visualizer.yml`, which builds this subdirectory and publishes `nile-visualizer-app/dist` to GitHub Pages. Enable Pages → "GitHub Actions" once before the first deploy.
