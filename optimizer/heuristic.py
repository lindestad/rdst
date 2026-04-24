"""Heuristic optimizer for the water resource simulator.

Strategy — Reservoir-fill × Price greedy rule
----------------------------------------------
For each node at each timestep the action (production fraction ∈ [0, 1]) is
chosen with three simple rules applied in priority order:

1. **Spill prevention**: if the reservoir is nearly full (fill > *spill_threshold*)
   release at maximum capacity to avoid wasting water over the dam.

2. **Drought protection**: if the reservoir is nearly empty (fill < *drought_threshold*)
   cut release to a small safety trickle so the reservoir can recover.

3. **Greedy value maximisation**: otherwise scale the release linearly with both
   the current fill ratio and a normalised energy price:

       action = fill_ratio × price_weight
       price_weight = 0.4 + 0.6 × (current_price / max_price)

   This means we release more when the reservoir is full *and* prices are high,
   and hold back water when prices are low or the reservoir is running low.

The optimizer is intentionally stateless between nodes — it makes independent
decisions per node based solely on that node's reservoir and its energy-price
module, so it is fast and requires no look-ahead.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).parent.parent / "node"))

from simulator import Simulator  # noqa: E402
from node import NodeStepResult  # noqa: E402

if TYPE_CHECKING:
    pass


@dataclass
class HeuristicOptimizer:
    """Greedy fill-level × price heuristic optimizer.

    Parameters
    ----------
    simulator:
        A configured :class:`~simulator.Simulator` instance.
    spill_threshold:
        Fill ratio above which the node releases at full capacity (default 0.80).
    drought_threshold:
        Fill ratio below which the node reduces release to *min_action* (default 0.15).
    min_action:
        Minimum production fraction used during drought protection (default 0.05).
    price_lookup:
        Optional mapping of ``node_id → list[float]`` of pre-computed prices,
        used to normalise the price signal.  If *None*, normalisation is
        estimated from the first *warmup_steps* prices seen.
    warmup_steps:
        Number of steps used to estimate the max price when *price_lookup* is
        not provided (default 365).
    """

    simulator: Simulator
    spill_threshold: float = 0.80
    drought_threshold: float = 0.15
    min_action: float = 0.05
    # Pre-computed per-node max prices (populated lazily or by caller).
    _max_prices: dict[str, float] = field(default_factory=dict, init=False)

    def set_max_price(self, node_id: str, max_price: float) -> None:
        """Provide the maximum expected energy price for *node_id*."""
        self._max_prices[node_id] = max_price

    def compute_action(self, node_id: str, timestep: int) -> float:
        """Compute the production fraction for *node_id* at *timestep*.

        Parameters
        ----------
        node_id:
            Target node identifier.
        timestep:
            Current simulation timestep.

        Returns
        -------
        float
            Production fraction ∈ [0, 1].
        """
        node = self.simulator.nodes[node_id]
        fill_ratio = node.reservoir_level / node.max_capacity if node.max_capacity > 0 else 0.0

        # --- Rule 1: spill prevention ---
        if fill_ratio >= self.spill_threshold:
            return 1.0

        # --- Rule 2: drought protection ---
        if fill_ratio <= self.drought_threshold:
            return self.min_action

        # --- Rule 3: greedy value maximisation ---
        current_price = node.energy_price.price(timestep) if node.energy_price else 1.0
        max_price = self._max_prices.get(node_id, current_price) or current_price

        # Normalised price in [0, 1]; clamp in case actual price exceeds estimate.
        norm_price = min(current_price / max_price, 1.0) if max_price > 0 else 1.0
        price_weight = 0.4 + 0.6 * norm_price  # maps [0,1] → [0.4, 1.0]

        action = fill_ratio * price_weight
        return max(self.min_action, min(1.0, action))

    def run(self, n_steps: int) -> list[dict[str, NodeStepResult]]:
        """Run the heuristic optimizer for *n_steps* timesteps.

        Parameters
        ----------
        n_steps:
            Number of simulation steps to execute.

        Returns
        -------
        list[dict[str, NodeStepResult]]
            One result dictionary per timestep (list index = timestep index).
        """
        history: list[dict[str, NodeStepResult]] = []

        for t in range(n_steps):
            actions = {
                node_id: self.compute_action(node_id, t)
                for node_id in self.simulator.nodes
            }
            results = self.simulator.step(actions, timestep=t)
            history.append(results)

        return history
