# Dataloader Node Generation Plan

## Goal

Build the dataloader around the simulator's `node.md` / `module.md` contract:

- generate node configuration from sourced topology, reservoirs, demand zones,
  and routing assumptions
- generate daily module CSVs for each node and scenario column
- keep CASSINI/Copernicus data prominent, with Galileo/GNSS included as a
  defensible EU-space source lane
- supplement with Nile-specific and FAO data where Copernicus does not provide
  dams, population demand, crop coefficients, or operational rules

The loader should produce a simulator-ready snapshot, not a generic data lake.

```text
source catalog
  -> raw fetch / source manifest
  -> staging tables
  -> node attribution
  -> module CSV generation
  -> generated config.yaml
```

## Output Contract

Target the markdown simulator contract directly:

```text
horizon/nrsm/data/generated/
  config.yaml
  modules/
    lake_victoria_outlet.catchment_inflow.csv
    lake_victoria_outlet.evaporation.csv
    gerd.catchment_inflow.csv
    gerd.evaporation.csv
    gerd.drink_water.csv
    gerd.food_production.csv
    gerd.energy.csv
    ...
  staging/
    source_manifest.csv
    source_catalog.csv
    node_sources.csv
    reservoir_sources.csv
    station_sources.csv
```

`config.yaml` should follow `node.md`:

- `settings.timestep_days`
- `nodes[].id`
- `nodes[].reservoir.initial_level`
- `nodes[].reservoir.max_capacity`
- `nodes[].max_production`
- `nodes[].catchment_inflow`
- `nodes[].connections`
- `nodes[].modules.evaporation`
- `nodes[].modules.drink_water`
- `nodes[].modules.food_production`
- `nodes[].modules.energy`

Every generated scalar or CSV should carry provenance through a staging table.

## Source Stack

### CASSINI / Copernicus First

| Node need | Primary source | Output |
| --- | --- | --- |
| River discharge baseline | Copernicus CEMS GloFAS historical river discharge | `catchment_inflow` CSV for river/reservoir nodes |
| Rainfall and runoff | ERA5-Land hourly/time-series data | fallback `catchment_inflow`, climate scenario columns |
| Evaporation / ET | Copernicus Land Monitoring Service Evapotranspiration 300 m and ERA5-Land evaporation/PET variables | `evaporation` CSV |
| Farmland mask | Copernicus Global Dynamic Land Cover / land-cover fractions | farmland node area and crop-demand attribution |
| Water bodies/reservoir masks | Copernicus Land Monitoring Service Water Bodies and JRC surface water | reservoir surface-area sanity checks |
| NDVI validation | Sentinel-2 L2A or CLMS vegetation products | validation overlay, not required for first sim input |

### Galileo / GNSS Lane

Galileo is not a direct hydrology raster. Treat it as a GNSS sourcing lane:

| Node need | Primary source | Output |
| --- | --- | --- |
| EU-space Galileo provenance | European GNSS Service Centre / ESA GSSC / IGS MGEX | `source_catalog.csv` entries |
| Nearby GNSS station availability | IGS MGEX / CDDIS daily GNSS data | `station_sources.csv`, optional node QA feature |
| Atmospheric water proxy | IGS tropospheric zenith path delay products | optional `gnss_zenith_path_delay_mm` staging feature |
| PWV / IWV proxy | ZPD plus ERA5 pressure/temperature | stretch `gnss_precipitable_water_mm` module/overlay |

Do not block the loader on credentialed GNSS archives. The MVP should support a
dry-run manifest with archive URLs and access notes.

### Supplemental Sources

| Node need | Source | Output |
| --- | --- | --- |
| Sub-basin topology | HydroBASINS / HydroATLAS | node geometry, routing skeleton |
| Reservoir/dam metadata | NBI dams database, GRanD, operator factsheets | reservoir capacity, initial storage assumptions |
| Irrigation demand and productivity | FAO WaPOR, AQUASTAT | food-production water coefficient and capacity |
| Municipal demand | WorldPop, AQUASTAT/JMP ratios | drinking-water module CSV |
| Hydropower inventory | NBI, WRI Global Power Plant Database, operator factsheets | `max_production`, energy price/value assumptions |

## Node Generation Strategy

For the hackathon, generate a pragmatic graph first and improve attribution
later.

### Phase 1: Curated Graph Skeleton

Use a checked-in seed list of 12-18 Nile nodes:

- Lake Victoria outlet
- White Nile / Sudd
- Malakal
- Lake Tana / Blue Nile headwater
- GERD
- Roseires / Sennar if time permits
- Gezira irrigation
- Khartoum
- Atbara headwater / confluence
- Merowe
- Aswan
- Cairo municipal demand
- Egypt agricultural demand
- Nile Delta sink

Each node should be a simulator node even when conceptually it is a demand zone.
The node's modules express local demand and production.

### Phase 2: Source-Attached Node Table

Build a staging table:

```text
node_id
name
node_role
lat
lon
country_code
subbasin_id
primary_discharge_source
primary_evaporation_source
primary_demand_source
primary_reservoir_source
confidence
notes
```

The config generator should consume this table, not the raw source adapters.

### Phase 3: Module CSVs

Generate one daily CSV per node module. Keep scenario columns simple:

- `scenario_1`: historical/baseline
- `scenario_2`: dry or conservative low-inflow variant
- `scenario_3`: wet or optimistic high-inflow variant

For hackathon speed, derive scenario columns by perturbing the same historical
series with transparent multipliers until richer climate scenarios land.

## Field Mapping

| Simulator field | Source derivation |
| --- | --- |
| `reservoir.initial_level` | reservoir source if known; otherwise `0.5 * max_capacity` |
| `reservoir.max_capacity` | NBI/GRanD/operator capacity converted to m3 |
| `max_production` | turbine max flow if known; otherwise estimate from MW, head, efficiency |
| `catchment_inflow` | GloFAS discharge at nearest/grid-representative river cell converted to m3/day |
| `connections[].fraction` | curated topology, normally `1.0` |
| `connections[].delay` | travel time from reach length or fixed hackathon assumption |
| `evaporation.rate` | ET/PET depth times reservoir surface area; fallback constant |
| `drink_water.daily_demand` | population times per-capita liters/day converted to m3/day |
| `food_production.water_coefficient` | WaPOR/AQUASTAT crop-water productivity inverse |
| `food_production.max_food_units` | irrigated area and seasonal crop calendar |
| `energy.price_per_unit` | normalized value proxy; constant unless policy layer adds pricing |

## Source Adapters

Organize adapters around outputs, not provider names:

```text
crates/rsm-dataloader/src/
  catalog.rs
  node_seed.rs
  generated_config.rs
  module_csv.rs
  sources/
    copernicus_glofas.rs
    copernicus_era5_land.rs
    copernicus_land.rs
    galileo_gnss.rs
    fao_wapor.rs
    fao_aquastat.rs
    nile_basin_initiative.rs
  transform/
    date_range.rs
    unit_conversion.rs
    nearest_node.rs
    scenario_columns.rs
```

For the first implementation, most adapters can emit planned source records and
stubbed deterministic data. The important thing is that the generator writes
valid config/module files with clear provenance.

## Implementation Slices

### Slice 1: Generated Snapshot Schema

Add dataloader structs for:

- `SourceRecord`
- `GeneratedNode`
- `GeneratedConnection`
- `ModuleRef`
- `GeneratedConfig`

Write tests that confirm a two-node generated config matches `node.md`.

### Slice 2: Source Catalog

Seed the source catalog with:

- CASSINI Space for Water
- CEMS GloFAS historical discharge
- ERA5-Land
- CLMS evapotranspiration
- CLMS global dynamic land cover
- CLMS water bodies
- FAO WaPOR
- FAO AQUASTAT
- NBI information systems / dams database
- Galileo RINEX navigation parameters
- IGS MGEX data/products
- IGS / CDDIS GNSS daily data and troposphere products

Write `source_catalog.csv` and `source_manifest.csv`.

### Slice 3: Curated Nile Node Seed

Create a small seed graph with coordinates, countries, connections, and source
ids. This unblocks config generation before full source fetches work.

### Slice 4: Deterministic Module CSV Writer

Generate daily module CSVs for a requested date range:

- catchment inflow in `m3/day`
- evaporation in `m3/day`
- drink-water demand in `m3/day`
- food-production capacity in `food_units/day`
- energy price in `currency/m3`

Start with deterministic seasonal curves and source labels. Replace individual
curves with real adapters as source fetches mature.

### Slice 5: GloFAS / ERA5 Real Fetch Path

Implement the first real data path for river-node inflow:

1. select node coordinates / catchment bounding box
2. fetch or accept downloaded GloFAS/ERA5 files
3. aggregate to daily
4. convert units to `m3/day`
5. write catchment module CSV

Prefer file-input mode first so teammates can drop downloaded NetCDF/GRIB files
into `data/raw/` without needing credentials on every laptop.

### Slice 6: Reservoir and Demand Sources

Attach real or curated values for:

- reservoir capacity and surface area
- population demand
- irrigated area
- crop-water productivity
- hydropower max flow/value proxy

This is enough to generate useful nodes.

### Slice 7: Galileo/GNSS Dry Run

Add `galileo_gnss` source records and archive URL builders for date ranges.
Write station/source availability to staging. Normalize ZPD only if a nearby
station product is accessible quickly.

## First 24-Hour Cut

1. Generate `config.yaml` plus module CSVs from a 6-node seed graph.
2. Include a CASSINI/Copernicus source catalog and manifest.
3. Include a Galileo/GNSS source manifest with dry-run archive URLs.
4. Use deterministic seasonal baseline data so the simulator can run.
5. Replace at least `catchment_inflow` for one or two nodes with real GloFAS or
   ERA5-derived values if source access behaves.

## First API Smoke Test

Use the Python CDS API client through `uv`; keep Rust focused on generated
simulator inputs.

```powershell
uv run horizon\nrsm\scripts\fetch_glofas_smoke.py --dry-run
uv run horizon\nrsm\scripts\fetch_glofas_smoke.py --submit
```

This hits the EWDS `cems-glofas-historical` dataset with a one-day GloFAS v4
request and writes the raw GRIB2 file under `horizon/nrsm/data/raw/glofas/`.
Before `--submit`, manually accept the GloFAS dataset Terms of Use on the EWDS
dataset page while logged in with the same account that owns the API token.

## Validation

- Config YAML parses and has unique node ids.
- Connection targets exist and outgoing fractions are `<= 1`.
- Every CSV module has `date,scenario_1,scenario_2,scenario_3`.
- Module units match `module.md`.
- All generated values are non-negative.
- Each generated value has a source id or an explicit `stub_assumption` note.

## Open Decisions

- Should generated modules be daily from the start, or monthly expanded to daily?
- Which branch owns the final `config.yaml` schema if simulator changes again?
- Are raw NetCDF/GRIB fetches implemented in Rust, or do we accept files produced
  by Python/notebooks and keep Rust responsible for normalization?
- Do we have Earthdata credentials for CDDIS, or should Galileo stay dry-run for
  the demo?

## Official Source References

- CASSINI Space for Water:
  https://www.euspa.europa.eu/newsroom-events/events/cassini-hackathon-space-water
- GloFAS historical river discharge:
  https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical
- ERA5-Land:
  https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries
- CLMS Copernicus services documentation:
  https://documentation.dataspace.copernicus.eu/Data/CopernicusServices/CLMS.html
- CLMS Global Dynamic Land Cover:
  https://land.copernicus.eu/en/products/global-dynamic-land-cover
- CLMS Water Bodies:
  https://land.copernicus.eu/en/products/water-bodies
- FAO WaPOR:
  https://www.fao.org/in-action/remote-sensing-for-water-productivity/wapor-data/
- FAO AQUASTAT water use:
  https://www.fao.org/aquastat/en/overview/methodology/water-use/index.html
- Nile Basin Information Systems:
  https://nilebasin.org/nile-basin-information-systems
- Galileo RINEX navigation parameters:
  https://www.gsc-europa.eu/gsc-products/galileo-rinex-navigation-parameters
- IGS MGEX data and products:
  https://igs.org/mgex/data-products/
- NASA Earthdata CDDIS daily GNSS data:
  https://www.earthdata.nasa.gov/data/space-geodesy-techniques/gnss/daily-30-second-data-collection
