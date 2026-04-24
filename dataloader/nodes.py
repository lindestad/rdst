"""Curated Nile basin node list. Manually assembled from public sources
(Wikipedia, FAO AquaStat, dam databases). Hand-editable."""
from __future__ import annotations

import json
from typing import Any

import yaml

from dataloader import config

# Each node is a dict; see tests for required fields.
NODES: list[dict[str, Any]] = [
    # --- White Nile branch ---
    {
        "id": "lake_victoria_outlet", "name": "Lake Victoria outlet (Jinja)",
        "type": "source", "country": "UG", "lat": 0.42, "lon": 33.19,
        "upstream": [], "downstream": ["white_nile_to_sudd"],
        "params": {"catchment_area_km2": 195000, "catchment_scale": 1.0},
    },
    {
        "id": "white_nile_to_sudd", "name": "White Nile reach to Sudd",
        "type": "reach", "country": "SS", "lat": 5.0, "lon": 31.5,
        "upstream": ["lake_victoria_outlet"], "downstream": ["sudd"],
        "params": {"travel_time_months": 1.0, "muskingum_k": 1.0, "muskingum_x": 0.2},
    },
    {
        "id": "sudd", "name": "Sudd wetland",
        "type": "wetland", "country": "SS", "lat": 7.5, "lon": 30.5,
        "upstream": ["white_nile_to_sudd"], "downstream": ["malakal"],
        "params": {"evap_loss_fraction_baseline": 0.5},
    },
    {
        "id": "malakal", "name": "Malakal (post-Sudd)",
        "type": "confluence", "country": "SS", "lat": 9.53, "lon": 31.65,
        "upstream": ["sudd"], "downstream": ["khartoum"],
        "params": {},
    },
    # --- Blue Nile branch ---
    {
        "id": "lake_tana_outlet", "name": "Lake Tana outlet",
        "type": "source", "country": "ET", "lat": 11.60, "lon": 37.38,
        "upstream": [], "downstream": ["blue_nile_to_gerd"],
        "params": {"catchment_area_km2": 15000, "catchment_scale": 1.0},
    },
    {
        "id": "blue_nile_to_gerd", "name": "Blue Nile reach to GERD",
        "type": "reach", "country": "ET", "lat": 11.0, "lon": 35.1,
        "upstream": ["lake_tana_outlet"], "downstream": ["gerd"],
        "params": {"travel_time_months": 0.5, "muskingum_k": 0.5, "muskingum_x": 0.2},
    },
    {
        "id": "gerd", "name": "Grand Ethiopian Renaissance Dam",
        "type": "reservoir", "country": "ET", "lat": 11.22, "lon": 35.09,
        "upstream": ["blue_nile_to_gerd"], "downstream": ["blue_nile_to_khartoum"],
        "params": {
            "storage_capacity_mcm": 74000, "storage_min_mcm": 14800,
            "surface_area_km2_at_full": 1874, "initial_storage_mcm": 14800,
            "hep": {"nameplate_mw": 6450, "head_m": 133, "efficiency": 0.9},
        },
    },
    {
        "id": "blue_nile_to_khartoum", "name": "Blue Nile reach (Roseires → Khartoum)",
        "type": "reach", "country": "SD", "lat": 13.5, "lon": 34.0,
        "upstream": ["gerd"], "downstream": ["gezira_irr"],
        "params": {"travel_time_months": 1.0, "muskingum_k": 1.0, "muskingum_x": 0.2},
    },
    {
        "id": "gezira_irr", "name": "Gezira irrigation scheme",
        "type": "demand_irrigation", "country": "SD", "lat": 14.4, "lon": 33.0,
        "upstream": ["blue_nile_to_khartoum"], "downstream": ["khartoum"],
        "params": {"area_ha_baseline": 900000, "crop_water_productivity_kg_per_m3": 1.2},
    },
    {
        "id": "khartoum", "name": "Khartoum confluence",
        "type": "confluence", "country": "SD", "lat": 15.60, "lon": 32.53,
        "upstream": ["malakal", "gezira_irr"],
        "downstream": ["khartoum_muni", "atbara_confluence"],
        "params": {},
    },
    {
        "id": "khartoum_muni", "name": "Khartoum municipal demand",
        "type": "demand_municipal", "country": "SD", "lat": 15.58, "lon": 32.53,
        "upstream": ["khartoum"], "downstream": ["atbara_confluence"],
        "params": {"population_baseline": 5500000, "per_capita_l_day": 150},
    },
    # --- Atbara tributary ---
    {
        "id": "atbara_source", "name": "Atbara River (Ethiopian highlands)",
        "type": "source", "country": "ET", "lat": 13.5, "lon": 37.0,
        "upstream": [], "downstream": ["atbara_confluence"],
        "params": {"catchment_area_km2": 112000, "catchment_scale": 1.0},
    },
    {
        "id": "atbara_confluence", "name": "Atbara confluence",
        "type": "confluence", "country": "SD", "lat": 17.67, "lon": 33.97,
        "upstream": ["khartoum_muni", "atbara_source"], "downstream": ["merowe"],
        "params": {},
    },
    # --- Main stem Sudan ---
    {
        "id": "merowe", "name": "Merowe Dam",
        "type": "reservoir", "country": "SD", "lat": 18.68, "lon": 31.93,
        "upstream": ["atbara_confluence"], "downstream": ["main_nile_to_aswan"],
        "params": {
            "storage_capacity_mcm": 12500, "storage_min_mcm": 2500,
            "surface_area_km2_at_full": 800, "initial_storage_mcm": 8000,
            "hep": {"nameplate_mw": 1250, "head_m": 67, "efficiency": 0.88},
        },
    },
    {
        "id": "main_nile_to_aswan", "name": "Main Nile reach to Aswan",
        "type": "reach", "country": "EG", "lat": 22.0, "lon": 32.0,
        "upstream": ["merowe"], "downstream": ["aswan"],
        "params": {"travel_time_months": 1.0, "muskingum_k": 1.0, "muskingum_x": 0.2},
    },
    # --- Aswan + Egypt ---
    {
        "id": "aswan", "name": "Aswan High Dam / Lake Nasser",
        "type": "reservoir", "country": "EG", "lat": 23.97, "lon": 32.88,
        "upstream": ["main_nile_to_aswan"], "downstream": ["egypt_ag"],
        "params": {
            "storage_capacity_mcm": 162000, "storage_min_mcm": 31600,
            "surface_area_km2_at_full": 5250, "initial_storage_mcm": 100000,
            "hep": {"nameplate_mw": 2100, "head_m": 70, "efficiency": 0.88},
        },
    },
    {
        "id": "egypt_ag", "name": "Egypt agriculture (Delta + Valley)",
        "type": "demand_irrigation", "country": "EG", "lat": 30.0, "lon": 31.0,
        "upstream": ["aswan"], "downstream": ["cairo_muni"],
        "params": {"area_ha_baseline": 3500000, "crop_water_productivity_kg_per_m3": 1.5},
    },
    {
        "id": "cairo_muni", "name": "Cairo municipal demand",
        "type": "demand_municipal", "country": "EG", "lat": 30.05, "lon": 31.25,
        "upstream": ["egypt_ag"], "downstream": ["delta"],
        "params": {"population_baseline": 20000000, "per_capita_l_day": 200},
    },
    {
        "id": "delta", "name": "Nile Delta / Mediterranean",
        "type": "sink", "country": "EG", "lat": 31.5, "lon": 31.5,
        "upstream": ["cairo_muni"], "downstream": [],
        "params": {"min_environmental_flow_m3s": 500},
    },
]

# Reaches with their own routing params (separate from the reach *nodes* above
# because the spec's `node_config.yaml` uses a top-level `reaches:` block).
REACHES: dict[str, dict[str, float]] = {
    n["id"]: n["params"]
    for n in NODES
    if n["type"] == "reach"
}


def build(stub: bool = False) -> None:
    """Write nodes.geojson + node_config.yaml."""
    nodes = _stub_nodes() if stub else NODES
    reaches = _stub_reaches() if stub else REACHES
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _write_geojson(nodes, config.NODES_GEOJSON)
    _write_yaml(nodes, reaches, config.NODE_CONFIG_YAML)


def _write_geojson(nodes: list[dict[str, Any]], path) -> None:
    features = []
    for n in nodes:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [n["lon"], n["lat"]]},
            "properties": {
                "id": n["id"], "name": n["name"], "type": n["type"],
                "country": n["country"],
                "upstream": n["upstream"], "downstream": n["downstream"],
            },
        })
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, indent=2))


def _write_yaml(nodes: list[dict[str, Any]], reaches: dict[str, dict[str, float]], path) -> None:
    node_block = {n["id"]: {"type": n["type"], **n["params"]} for n in nodes}
    out = {"nodes": node_block, "reaches": reaches}
    path.write_text(yaml.safe_dump(out, sort_keys=False))


def _stub_nodes() -> list[dict[str, Any]]:
    """Minimal 4-node line graph for Sat-morning L2/L3 unblock."""
    return [
        {"id": "stub_source", "name": "Stub source", "type": "source", "country": "XX",
         "lat": 0.0, "lon": 33.0, "upstream": [], "downstream": ["stub_reach"],
         "params": {"catchment_area_km2": 100000, "catchment_scale": 1.0}},
        {"id": "stub_reach", "name": "Stub reach", "type": "reach", "country": "XX",
         "lat": 10.0, "lon": 32.0, "upstream": ["stub_source"], "downstream": ["stub_reservoir"],
         "params": {"travel_time_months": 1.0, "muskingum_k": 1.0, "muskingum_x": 0.2}},
        {"id": "stub_reservoir", "name": "Stub reservoir", "type": "reservoir", "country": "XX",
         "lat": 20.0, "lon": 32.0, "upstream": ["stub_reach"], "downstream": ["stub_sink"],
         "params": {"storage_capacity_mcm": 10000, "storage_min_mcm": 1000,
                    "surface_area_km2_at_full": 100, "initial_storage_mcm": 5000,
                    "hep": {"nameplate_mw": 1000, "head_m": 50, "efficiency": 0.9}}},
        {"id": "stub_sink", "name": "Stub sink", "type": "sink", "country": "XX",
         "lat": 30.0, "lon": 31.0, "upstream": ["stub_reservoir"], "downstream": [],
         "params": {"min_environmental_flow_m3s": 100}},
    ]


def _stub_reaches() -> dict[str, dict[str, float]]:
    return {"stub_reach": {"travel_time_months": 1.0, "muskingum_k": 1.0, "muskingum_x": 0.2}}
