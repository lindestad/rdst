"""Node model for the water resource simulator.

Each node represents a catchment with one reservoir.  At every timestep the
node receives natural inflow from its catchment plus any water routed from
upstream nodes.  An *action* (fraction ∈ [0, 1]) controls how much of the
maximum production capacity is released as hydropower.  After honouring
drinking-water and food-production withdrawals, the reservoir level is
updated and excess water is reported as spill.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from modules import CatchmentInflow, DrinkWaterDemand, EnergyPrice, FoodProduction

logger = logging.getLogger(__name__)


@dataclass
class NodeStepResult:
    """Outcome of a single timestep for one node.

    Attributes
    ----------
    reservoir_level:
        Reservoir volume (m3) at the *end* of the timestep.
    production_release:
        Water (m3) released for hydropower production.
    energy_value:
        Monetary value of hydropower produced (price × production_release).
    food_produced:
        Food units produced this timestep.
    drink_water_met:
        Actual drinking-water volume (m3) withdrawn (≤ demand if reservoir ran dry).
    unmet_drink_water:
        Unmet drinking-water demand (m3) = demand − drink_water_met.
    spill:
        Water (m3) that overflowed the reservoir this timestep.
    downstream_release:
        Total water (m3) routed to downstream nodes; includes both production
        release and spill.
    total_inflow:
        Total water (m3) that entered the reservoir this timestep
        (catchment + upstream contributions).
    """
    reservoir_level: float
    production_release: float
    energy_value: float
    food_produced: float
    drink_water_met: float
    unmet_drink_water: float
    spill: float
    downstream_release: float
    total_inflow: float


@dataclass
class NodeConnection:
    """Directed edge to a downstream node.

    Attributes
    ----------
    node_id:
        Identifier of the downstream node.
    fraction:
        Share (0–1) of the production release routed to that node.
    delay:
        Number of timesteps the routed water takes to travel from this node to
        the downstream node.  0 means the water arrives within the same
        timestep (default).
    """
    node_id: str
    fraction: float
    delay: int = 0


@dataclass
class Node:
    """A catchment node with a single reservoir.

    Parameters
    ----------
    node_id:
        Unique identifier.
    catchment_inflow:
        Inflow module providing natural inflow (m3/day) from the local catchment.
    reservoir_level:
        Current reservoir level (m3); updated in-place after each step.
    max_capacity:
        Maximum reservoir volume (m3).
    max_production:
        Maximum water release rate for hydropower (m3/day).
    connections:
        List of downstream connections with routing fractions.
    drink_water:
        Drinking-water demand module.
    food_production:
        Food-production module.
    energy_price:
        Energy-price module.
    """
    node_id: str
    catchment_inflow: "CatchmentInflow"
    reservoir_level: float
    max_capacity: float
    max_production: float
    connections: list[NodeConnection] = field(default_factory=list)
    drink_water: "DrinkWaterDemand | None" = None
    food_production: "FoodProduction | None" = None
    energy_price: "EnergyPrice | None" = None
    # Stored at construction so reset() can restore the original level.
    _initial_level: float = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._initial_level = self.reservoir_level

    def reset(self) -> None:
        """Restore reservoir level to its initial value."""
        self.reservoir_level = self._initial_level

    def step(
        self,
        action: float,
        external_inflow: float = 0.0,
        timestep: int = 0,
        dt_days: float = 1.0,
        debug: bool = False,
    ) -> NodeStepResult:
        """Advance the node by one timestep.

        Water balance (in order of priority):
        1. Add catchment inflow + upstream inflow to reservoir.
        2. Release water for hydropower (action × max_production × dt), capped
           by available water.
        3. Withdraw drinking-water demand (capped by remaining water).
        4. Allocate water for food production (capped by remaining water).
        5. Clamp reservoir to [0, max_capacity]; excess becomes spill.
        6. Route production release downstream according to connection fractions.

        Parameters
        ----------
        action:
            Production fraction ∈ [0, 1].  Values outside this range are clamped.
        external_inflow:
            Water (m3) received from upstream nodes this timestep.
        timestep:
            Current timestep index (passed to time-aware modules).
        dt_days:
            Duration of this timestep in days.  All rate-based quantities
            (inflow, demand, max production) are multiplied by this value.
        debug:
            If True, verify the water balance and emit a warning if it does
            not close to within floating-point tolerance.

        Returns
        -------
        NodeStepResult
            State and flux values after this timestep.
        """
        action = max(0.0, min(1.0, action))
        level_before = self.reservoir_level

        # --- 1. Total inflow ---
        catchment_vol = self.catchment_inflow.inflow(timestep, dt_days)
        total_inflow = catchment_vol + external_inflow
        available = self.reservoir_level + total_inflow

        # --- 2. Hydropower production release ---
        desired_release = action * self.max_production * dt_days
        production_release = min(desired_release, available)
        available -= production_release

        # --- 3. Drinking-water withdrawal ---
        dw_demand = self.drink_water.demand(timestep, dt_days) if self.drink_water else 0.0
        drink_water_met = min(dw_demand, available)
        unmet_drink_water = dw_demand - drink_water_met
        available -= drink_water_met

        # --- 4. Food-production water allocation ---
        if self.food_production:
            # TimeSeriesFoodProduction and CSVFoodProduction expose produce_at();
            # the simple FoodProduction uses produce().
            if hasattr(self.food_production, "produce_at"):
                fp_result = self.food_production.produce_at(available, timestep, dt_days)
            else:
                fp_result = self.food_production.produce(available, dt_days)
            food_produced = fp_result["food_produced"]
            food_water = fp_result["water_consumed"]
        else:
            food_produced = 0.0
            food_water = 0.0
        available -= food_water

        # --- 5. Update reservoir; compute spill ---
        new_level_raw = available  # what remains goes back into reservoir
        spill = max(0.0, new_level_raw - self.max_capacity)
        self.reservoir_level = min(new_level_raw, self.max_capacity)

        # --- 6. Downstream routing ---
        # Both controlled production release AND uncontrolled spill travel
        # downstream through the same channels.  Spill generates no energy.
        total_fraction = sum(c.fraction for c in self.connections)
        downstream_release = (production_release + spill) * min(total_fraction, 1.0)

        # --- Energy value ---
        ep = self.energy_price.price(timestep) if self.energy_price else 0.0
        energy_value = production_release * ep

        # --- Optional water balance check ---
        if debug:
            # water_in  = level_before + total_inflow
            # water_out = production_release + drink_water_met + food_water + spill + level_after
            water_in = level_before + total_inflow
            water_out = production_release + drink_water_met + food_water + spill + self.reservoir_level
            imbalance = abs(water_in - water_out)
            if imbalance > 1e-6:
                logger.warning(
                    "Node '%s' t=%d: water imbalance of %.6f m3 "
                    "(in=%.4f, out=%.4f)",
                    self.node_id, timestep, imbalance, water_in, water_out,
                )

        return NodeStepResult(
            reservoir_level=self.reservoir_level,
            production_release=production_release,
            energy_value=energy_value,
            food_produced=food_produced,
            drink_water_met=drink_water_met,
            unmet_drink_water=unmet_drink_water,
            spill=spill,
            downstream_release=downstream_release,
            total_inflow=total_inflow,
        )
