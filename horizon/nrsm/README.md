# NRSM

NRSM is a Nile-focused river systems simulator MVP implemented as a dedicated Rust
workspace under `horizon/` so it can grow cleanly inside a larger monorepo.

## Current Scope

- Daily simulation engine with monthly 30-day reporting support
- Directed acyclic river graph with edge losses
- Explicit reservoir nodes with minimal storage and release behavior
- Soft constraints for drinking water, irrigation, and hydropower
- Stable serializable scenario and result types for future Python and ML usage

## Workspace Layout

- `crates/nrsm-sim-core`: public simulation API and domain model
- `crates/nrsm-cli`: command-line runner for JSON scenarios
- `crates/nrsm-dataloader`: normalized data bundle schema and CSV exporter for hackathon ingestion
- `scenarios/nile-mvp`: small Nile-inspired demo scenario
- `docs/nile-dataloader-plan.md`: dataset research and visual loading plan

## MVP Assumptions

- The execution time step is always daily
- Monthly support is handled through 30-day aggregation and optional monthly input series
- Drinking water and irrigation are treated as consumptive uses in v1
- Hydropower is modeled as a non-consumptive linear conversion on routed outflow
- Sector allocation priority is drinking water first, then irrigation, then storage/release

Those choices keep the first implementation compact while leaving room for:

- head-based hydropower
- crop and region-specific agriculture modules
- explicit optimization layers on top of the simulator
- Python bindings and training workflows
- richer data loading and scenario assembly from Copernicus and supplemental datasets

## Run The CLI

```powershell
cargo run -p nrsm-cli -- <path-to-scenario.yaml> --pretty
```
