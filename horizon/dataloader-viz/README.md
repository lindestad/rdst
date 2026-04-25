# Dataloader Bundle Visualizer

Standalone browser tool for inspecting the NRSM dataloader's normalized CSV bundle:

- `nodes.csv`
- `edges.csv`
- `time_series.csv`

The app runs entirely in the browser. Use **Load CSVs** to select all three files together, or use the bundled sample Nile dataset to inspect the expected shape.

## Commands

```bash
npm install
npm run dev
npm run build
```

## What It Shows

- Topology coverage for nodes and directed reaches
- Metric and interval lenses from `time_series.csv`
- Reference diagnostics for missing node or edge IDs
- Non-numeric value checks
- Quality flag review counts
- Source and transform provenance for selected entities
