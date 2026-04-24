"""YAML loader for the water resource simulator.

Reads a YAML configuration file, instantiates all Node objects with their
modules, wires the connection graph, and returns a ready-to-use Simulator.

Expected YAML schema
--------------------
See ``config.yaml`` for a full annotated example.  Top-level keys::

    settings:
      timestep_days: 1.0          # optional, default 1.0

    nodes:
      - id: <str>
        catchment_inflow:
          type: constant           # or "timeseries"
          rate: <float>            # m3/day  (constant only)
          values: [<float>, ...]   # m3/day per timestep (timeseries only)
        reservoir:
          initial_level: <float>   # m3
          max_capacity: <float>    # m3
        max_production: <float>    # m3/day
        connections:               # list, may be empty
          - node_id: <str>
            fraction: <float>      # 0–1
            delay: <int>           # timesteps, default 0
        modules:
          drink_water:
            daily_demand: <float>  # m3/day
          food_production:
            water_coefficient: <float>   # m3 per food unit
            max_food_units: <float>      # food units/day
          energy:
            price_per_unit: <float>      # currency per m3 released
"""
from __future__ import annotations

from pathlib import Path

import yaml

from modules import (
    ConstantInflow, CSVInflow, TimeSeriesInflow,
    DrinkWaterDemand, TimeSeriesDrinkWater, CSVDrinkWater,
    FoodProduction, TimeSeriesFoodProduction, CSVFoodProduction,
    EnergyPrice, TimeSeriesEnergyPrice, CSVEnergyPrice,
)
from node import Node, NodeConnection


def load_simulator(yaml_path: str | Path) -> "Simulator":  # noqa: F821
    """Parse *yaml_path* and return a configured :class:`~simulator.Simulator`.

    Parameters
    ----------
    yaml_path:
        Path to the YAML configuration file.

    Returns
    -------
    Simulator
        A simulator instance ready to call ``step()``.

    Raises
    ------
    ValueError
        If connection fractions for a single node exceed 1.0, or if a
        connection references an unknown node ID.
    FileNotFoundError
        If *yaml_path* does not exist.
    """
    # Import here to avoid circular dependency (simulator imports loader API).
    from simulator import Simulator  # noqa: PLC0415

    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {yaml_path}")

    with yaml_path.open() as fh:
        config = yaml.safe_load(fh)

    settings = config.get("settings", {})
    dt_days = float(settings.get("timestep_days", 1.0))

    nodes: dict[str, Node] = {}

    for node_cfg in config.get("nodes", []):
        node_id = node_cfg["id"]
        reservoir_cfg = node_cfg.get("reservoir", {})
        modules_cfg = node_cfg.get("modules", {})

        # --- Catchment inflow module ---
        ci_cfg = node_cfg["catchment_inflow"]
        ci_type = ci_cfg.get("type", "constant")
        if ci_type == "constant":
            catchment_inflow = ConstantInflow(rate=float(ci_cfg["rate"]))
        elif ci_type == "timeseries":
            catchment_inflow = TimeSeriesInflow(values=[float(v) for v in ci_cfg["values"]])
        elif ci_type == "csv":
            catchment_inflow = CSVInflow(
                filepath=ci_cfg["filepath"],
                column=ci_cfg["column"],
            )
        else:
            raise ValueError(f"Node '{node_id}': unknown catchment_inflow type '{ci_type}'.")

        # --- Modules ---
        dw_cfg = modules_cfg.get("drink_water", {})
        if dw_cfg:
            dw_type = dw_cfg.get("type", "constant")
            if dw_type == "constant":
                drink_water = DrinkWaterDemand(daily_demand=float(dw_cfg["daily_demand"]))
            elif dw_type == "timeseries":
                drink_water = TimeSeriesDrinkWater(values=[float(v) for v in dw_cfg["values"]])
            elif dw_type == "csv":
                drink_water = CSVDrinkWater(filepath=dw_cfg["filepath"], column=dw_cfg["column"])
            else:
                raise ValueError(f"Node '{node_id}': unknown drink_water type '{dw_type}'.")
        else:
            drink_water = None

        fp_cfg = modules_cfg.get("food_production", {})
        if fp_cfg:
            fp_type = fp_cfg.get("type", "constant")
            wc = float(fp_cfg["water_coefficient"])
            if fp_type == "constant":
                food_production = FoodProduction(water_coefficient=wc, max_food_units=float(fp_cfg["max_food_units"]))
            elif fp_type == "timeseries":
                food_production = TimeSeriesFoodProduction(water_coefficient=wc, max_food_units_values=[float(v) for v in fp_cfg["values"]])
            elif fp_type == "csv":
                food_production = CSVFoodProduction(water_coefficient=wc, filepath=fp_cfg["filepath"], column=fp_cfg["column"])
            else:
                raise ValueError(f"Node '{node_id}': unknown food_production type '{fp_type}'.")
        else:
            food_production = None

        en_cfg = modules_cfg.get("energy", {})
        if en_cfg:
            en_type = en_cfg.get("type", "constant")
            if en_type == "constant":
                energy_price = EnergyPrice(price_per_unit=float(en_cfg["price_per_unit"]))
            elif en_type == "timeseries":
                energy_price = TimeSeriesEnergyPrice(values=[float(v) for v in en_cfg["values"]])
            elif en_type == "csv":
                energy_price = CSVEnergyPrice(filepath=en_cfg["filepath"], column=en_cfg["column"])
            else:
                raise ValueError(f"Node '{node_id}': unknown energy type '{en_type}'.")
        else:
            energy_price = None

        # --- Connections (node_id strings; validated after all nodes are built) ---
        raw_connections = node_cfg.get("connections") or []
        connections = [
            NodeConnection(
                node_id=c["node_id"],
                fraction=float(c["fraction"]),
                delay=int(c.get("delay", 0)),
            )
            for c in raw_connections
        ]

        total_fraction = sum(c.fraction for c in connections)
        if total_fraction > 1.0 + 1e-9:
            raise ValueError(
                f"Node '{node_id}': connection fractions sum to {total_fraction:.4f} > 1.0"
            )

        nodes[node_id] = Node(
            node_id=node_id,
            catchment_inflow=catchment_inflow,
            reservoir_level=float(reservoir_cfg.get("initial_level", 0.0)),
            max_capacity=float(reservoir_cfg.get("max_capacity", float("inf"))),
            max_production=float(node_cfg.get("max_production", 0.0)),
            connections=connections,
            drink_water=drink_water,
            food_production=food_production,
            energy_price=energy_price,
        )

    # Validate that every connection target exists
    for nid, node in nodes.items():
        for conn in node.connections:
            if conn.node_id not in nodes:
                raise ValueError(
                    f"Node '{nid}' references unknown downstream node '{conn.node_id}'."
                )

    return Simulator(nodes=nodes, dt_days=dt_days)
