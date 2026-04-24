# NRSM Schema Notes

This note captures a recommended schema and data-structure direction for NRSM so
the simulator, loader, future optimizer, and possible Python bindings can all
share a stable contract.

## Design Goals

- Keep one canonical domain schema for the river system model
- Make the simulator consume plain serializable structs, not loader-specific types
- Separate scenario input from simulation output
- Make node- and edge-level trajectories easy to extract for ML and Python
- Support simple v1 sector models without blocking richer v2 models
- Allow backward-compatible schema evolution through explicit versioning

## Recommended Boundary

I recommend three layers:

1. Raw source layer
   - CSV, parquet, shapefiles, spreadsheets, APIs, etc.
   - Owned by the loader/data-ingest work

2. Canonical NRSM scenario layer
   - Clean, validated, serialization-friendly domain objects
   - This should be the contract between the loader and the simulator

3. Engine/runtime layer
   - Compiled graph indexes, cached topological order, dense vectors, etc.
   - Internal to Rust and optimized for simulation speed

The key point is that the loader should not construct engine-specific runtime
state. It should emit the canonical scenario model.

## Recommended Top-Level Schema

The canonical scenario should be YAML and have a stable top-level envelope like
this:

```yaml
schema_version: 0.1.0
metadata: {}
simulation: {}
network: {}
policies: {}
extensions: {}
```

Suggested meaning:

- `schema_version`
  - Version of the scenario contract, not the software build
  - Current supported value: `0.1.0`
- `metadata`
  - Human context such as name, description, author, source set, provenance
- `simulation`
  - Horizon length, time-step semantics, reporting mode, calendars
- `network`
  - Nodes, edges, static topology, sector capabilities
- `policies`
  - Allocation priorities, reservoir operating rules, optional scenario overrides
- `extensions`
  - Non-core namespaced data for future modules without breaking the base schema

## Recommended Core Entities

### Scenario

This is the canonical object handed to the simulator:

```text
Scenario
- schema_version
- metadata
- simulation
- network
- policies
- extensions
```

### SimulationConfig

Recommended fields:

- `engine_time_step`
  - For now always `daily`
- `horizon_days`
- `reporting`
  - `daily`, `monthly30_day`, later calendar-month support if needed
- `start_date`
  - Optional in v1, but useful if real calendars matter later

Important recommendation:

- Keep the engine time step fixed and explicit
- Treat monthly support as reporting/input expansion logic, not as a separate
  simulation engine

### Network

Recommended fields:

- `nodes: []`
- `edges: []`
- `basin_outlets: []`
  - Optional, but useful later if there can be multiple exits

### Node

Each node should have:

- `id`
  - Stable machine identifier, never derived from display name
- `name`
- `kind`
  - `river`, `reservoir`, later maybe `junction`, `diversion`, `sink`
- `location`
  - Optional lat/lon or region reference
- `local_inflow`
- `sectors`
  - Nested capabilities rather than many top-level optional fields
- `state`
  - Initial state only, such as reservoir storage
- `attributes`
  - Optional scalar metadata for future modules

Suggested shape:

```yaml
id: aswan
name: High Aswan
kind: reservoir
local_inflow: {}
state:
  storage: 900.0
sectors:
  drinking_water: {}
  hydropower: {}
attributes:
  country: EGY
```

Why I prefer `sectors` over flat optional fields:

- cleaner evolution when agriculture becomes crop-specific
- easier to attach module-specific configs
- easier for Python clients to inspect available behaviors at a node

### Edge

Each edge should have:

- `id`
- `from`
- `to`
- `routing`

Suggested shape:

```yaml
id: aswan_to_delta
from: aswan
to: nile_delta
routing:
  flow_share: 1.0
  loss_fraction: 0.03
```

Later this can expand to:

- travel time / lag
- seasonal loss functions
- capacity limits
- sediment or quality transport

## Sector Schema

I recommend sector configs be namespaced and intentionally small in v1.

### Drinking Water

```yaml
minimum_delivery: {}
target_delivery: {}
```

### Irrigation

```yaml
minimum_delivery: {}
target_delivery: {}
production_model:
  kind: linear
  food_per_unit_water: 1.8
```

This is better than storing `food_per_unit_water` directly at the node because it
creates an obvious place to later swap in:

- crop mixes
- region-specific response curves
- yield saturation models
- economic valuation models

### Hydropower

```yaml
minimum_energy: {}
target_energy: {}
generation_model:
  kind: linear
  energy_per_unit_water: 0.59
  max_turbine_flow: {}
```

That makes the v2 upgrade path clearer:

- `kind: linear`
- later `kind: reservoir_head`

## Reservoir Schema

Reservoirs should be explicit and separate from generic node fields:

```yaml
storage_model:
  capacity: 1600.0
  min_storage: 500.0
  initial_storage: 900.0
operating_policy:
  target_release: {}
```

Why separate storage model from operating policy:

- storage is physical system state
- release behavior is a decision rule and may later be replaced by an optimizer

That separation becomes very valuable later.

## Time Series Schema

This is the part most worth standardizing early.

I recommend a tagged union with explicit semantics:

```yaml
kind: constant
value: 25.0
```

```yaml
kind: daily
values: [...]
```

```yaml
kind: monthly30_day
values: [...]
```

Later additions could be:

- `monthly_calendar`
- `piecewise_linear`
- `external_ref`
- `scenario_override`

Important recommendation:

- Do not encode time series implicitly through column names or loose tables at the
  canonical schema boundary
- Convert raw tables into an explicit tagged time-series object before simulation

## Outputs

The simulator should expose a stable result schema distinct from the input schema.

Recommended levels:

- Run summary
- Period results
- Node results per period
- Edge results per period
- Optional daily trajectory stream for training/export

Suggested shape:

```text
SimulationResult
- metadata
- engine_time_step
- reporting
- summary
- periods[]
```

Node-level outputs should include:

- incoming flow
- local inflow
- available water
- storage start/end
- deliveries by sector
- production outcomes
- downstream outflow
- exit flow

For ML and Python work, I strongly recommend preserving explicit node trajectories
instead of only aggregated summaries.

## Public Rust Interface Recommendation

I recommend the simulator core expose:

- `Scenario`
- `SimulationResult`
- `simulate(&Scenario) -> Result<SimulationResult, SimulationError>`

And separately keep internal runtime types like:

- `CompiledNetwork`
- dense node indexes
- adjacency lists
- cached evaluation plans

This keeps the public API stable even if the engine internals change a lot.

## Loader Contract Recommendation

The loader module should ideally output one of these:

1. Canonical `Scenario` directly
2. A loader DTO that is trivially mapped into `Scenario`

I prefer option 1 unless the loader has a strong need for a richer ingest-only
representation.

If the loader must carry extra metadata, keep that in:

- `metadata`
- `attributes`
- `extensions`

Avoid requiring the simulator to understand raw ingest structures.

## Validation Rules Worth Enforcing Early

The canonical schema should validate at load time. The current machine-readable
contract lives at `contracts/scenario.schema.yaml`.

Validation should cover:

- supported `schema_version`
- unique node ids
- unique edge ids
- all edge endpoints exist
- graph is acyclic in the MVP if the engine assumes DAG routing
- edge flow shares from a node sum to 1.0 when outgoing edges exist
- loss fractions are within `[0, 1]`
- reservoir storage bounds are valid
- required sector fields exist when the sector is enabled
- time series are non-empty and semantically compatible with the run horizon

## Recommended Evolution Strategy

To avoid pain later:

- include `schema_version` now
- prefer additive changes over renames
- avoid flattening sector-specific fields into the node root
- keep optimizer policy/config separate from physical system definition
- keep room for namespaced `extensions`

## Concrete Recommendation For The Loader

If your colleague is building the loader now, I would suggest they target this
responsibility split:

- parse raw data sources
- normalize IDs and references
- build canonical nodes/edges/time-series objects
- run schema validation
- output canonical scenario YAML

And let NRSM own:

- graph compilation
- topological ordering
- runtime storage vectors
- simulation math
- result generation

## My Bottom-Line Recommendation

If we want to scale well, the best long-term shape is:

- canonical YAML scenario schema with explicit versioning
- nested sector configs
- explicit tagged time series
- separate physical system config from operating policy
- stable public input/output structs
- internal compiled graph/runtime state hidden behind the simulator API

That gives us a clean path from:

- simulator MVP
- to richer hydrology and crop models
- to optimizer integration
- to Python bindings and ML workflows
