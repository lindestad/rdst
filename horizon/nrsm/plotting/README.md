# NRSM Plotting

Small Python plotting module for NRSM simulator result folders. It is managed
with `uv` and reads the CSVs written by:

```powershell
cargo run -p nrsm-cli -- data\generated\config.yaml --results-dir data\results\run-a
```

Run it from this directory:

```powershell
uv run nrsm-plots --results-dir ..\data\generated-hydmod\results --output-dir ..\data\generated-hydmod\plots
```

Or run it as a module:

```powershell
uv run python -m nrsm_plotting --results-dir ..\data\generated-hydmod\results --output-dir ..\data\generated-hydmod\plots
```

## Output

The plotter writes:

- `network_water_balance.png`: basin-wide inflow, routed release, evaporation,
  drinking water, food-water demand, food-water served, and routing loss.
- `system_water_accounting.png`: whole-system water accounting over time,
  including accounted outflows, storage change, and balance residual.
- `network_service_reliability.png`: unmet drinking and food-water demand over
  time, plus cumulative reliability.
- `network_energy.png`: energy-value proxy over time and cumulative energy
  value.
- `node_totals.png`: per-node totals for inflow, release, evaporation, food
  water, shortages, and energy value.
- `node_water_balance.png`: per-node water-balance residuals over time.
- `node_shortage_heatmap.png`: per-node shortage intensity over time.
- `nodes/<node_id>.png`: node-level storage, action, inflow/release, sector
  water, shortage, and energy diagnostics.
- `nodes/<node_id>.water_balance.png`: node-level accounting terms and balance
  residual over time.
- `node_metrics.csv`: per-node totals and simple reliability ratios used by the
  plots.
- `plot_manifest.json`: paths and metadata for downstream visualization tools.

The plotting code accepts both the current CSV contract and older result folders
that predate explicit food-water columns. Missing optional fields are treated as
zero, and the manifest records warnings so stale result folders are visible.

## Useful Options

```powershell
uv run nrsm-plots `
  --results-dir ..\data\generated-hydmod\results `
  --output-dir ..\data\generated-hydmod\plots `
  --nodes victoria gerd aswand cairo `
  --format png `
  --dpi 180
```

- `--nodes`: restrict per-node plots and node-level rollups to named nodes.
- `--no-node-plots`: only write network and comparison plots.
- `--format`: `png`, `svg`, or `pdf`.
- `--dpi`: raster output resolution.

## Why CSV First?

CSV output is the reproducible path used by the CLI and by non-Rust consumers.
Keeping plots on the CSV contract makes them useful for validation meetings,
debugging old runs, and comparing action scenarios. The Python bindings remain
the right path for optimizers that need fast repeated simulation, and this
package can later add a `simulate-and-plot` command that calls `nrsm_py`
directly.
