# RDST

**A Nile-focused river systems simulator and visualizer for CASSINI's Space for Water track.**

RDST is a compact digital-twin prototype for exploring water-policy tradeoffs across the Nile basin. It combines a Rust simulation core, a YAML scenario contract, and a React dashboard that turns simulated flows, storage, losses, drinking-water delivery, irrigation, and hydropower into an explorable basin view.

## What Is Here

| Area | Path | Purpose |
| --- | --- | --- |
| Simulator | `horizon/nrsm` | Rust workspace for the Nile River Systems Model MVP. |
| Dataloader | `horizon/nrsm/crates/nrsm-dataloader` | Standalone generator for sourced simulator configs, module CSVs, and staging metadata. |
| Scenario contract | `horizon/nrsm/contracts/scenario.schema.yaml` | Machine-readable YAML schema for scenario files. |
| Demo scenario | `horizon/nrsm/scenarios/nile-mvp/scenario.yaml` | Small Nile-inspired network used by the CLI and visualizer. |
| Visualizer | `nile-visualizer-app` | Vite + React app for inspecting simulator output. |
| Static prototype | `nile-visualizer-plan` | Lightweight HTML/CSS/JS visual plan. |
| Design docs | `docs/superpowers` | Architecture, lane plans, and hackathon scope. |
| Python digital twin draft | `horizon/nile-digital-twin` | Earlier Python/FastAPI/React prototype moved out of the repository root. |

## Project Shape

```text
RDST
|-- horizon/nrsm/              Rust simulator, CLI, contracts, scenarios
|   |-- crates/nrsm-sim-core   Daily engine, graph model, aggregation
|   |-- crates/nrsm-cli        YAML scenario runner
|   |-- crates/nrsm-dataloader Standalone sourced-data generator
|   |-- contracts/             Scenario schema
|   `-- scenarios/nile-mvp/    Demo Nile scenario
|-- horizon/nile-digital-twin/ Python/FastAPI/React draft prototype
|-- nile-visualizer-app/       React dashboard
|-- nile-visualizer-plan/      Static visual prototype
`-- docs/superpowers/          Design notes and implementation plans
```

## Core Idea

The simulator runs a directed acyclic river graph in daily steps, then reports daily or 30-day monthly periods. Nodes can represent rivers or reservoirs, with optional drinking-water demand, irrigation demand, and hydropower behavior. Edges route flow downstream and can model losses.

The visualizer uses the MVP result data to show:

- basin flow and downstream routing
- edge losses and period-to-period deltas
- reservoir storage and release behavior
- drinking-water, irrigation, food, and energy metrics
- a map-like Nile network with selectable nodes and reaches

## Quick Start

Run the simulator demo:

```powershell
cd horizon\nrsm
cargo run -p nrsm-cli -- scenarios\nile-mvp\scenario.yaml --json --pretty
```

Generate dataloader files:

```powershell
cd horizon\nrsm
cargo run -p nrsm-dataloader -- seed --output data\generated --start-date 2020-01-01 --end-date 2020-01-31 --scenarios 3
```

Run the visualizer:

```powershell
cd nile-visualizer-app
npm install
npm run dev
```

Build the visualizer:

```powershell
cd nile-visualizer-app
npm run build
```

## Current Status

RDST is an MVP-scale prototype. The Rust core already provides a serializable scenario model, validation, a CLI runner, 30-day aggregation, and result summaries. The React app is a polished local visualizer using typed demo data copied from the Nile MVP scenario and CLI output.

The next natural integration step is to export scenario and result JSON from the CLI directly into the visualizer's data layer, then replace the copied fixture data with generated payloads.
