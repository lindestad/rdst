"""Water resource simulator.

The :class:`Simulator` is the main entry point.  It holds a graph of
:class:`~node.Node` objects, performs a topological sort so that upstream
nodes are evaluated before downstream ones, and steps all nodes forward by
one timestep at a time.

Usage example::

    from loader import load_simulator

    sim = load_simulator("config.yaml")

    # --- Single step ---
    actions = {"reservoir_a": 0.8, "reservoir_b": 0.5, "reservoir_c": 0.6}
    state = sim.step(actions)

    # --- Full run over a sequence of actions ---
    actions_seq = [actions] * 30
    history = sim.run(actions_seq)

    # --- Reset to initial conditions and re-run ---
    sim.reset()
    history2 = sim.run(actions_seq)
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field

from node import Node, NodeStepResult

logger = logging.getLogger(__name__)


@dataclass
class Simulator:
    """Graph-based water resource simulator.

    Parameters
    ----------
    nodes:
        Mapping of node ID → :class:`~node.Node` instance.
    dt_days:
        Duration of one timestep in days (default ``1.0``).  Change this to
        simulate at e.g. hourly resolution (``dt_days=1/24``) or weekly
        resolution (``dt_days=7``).  All rate-based YAML values (inflow,
        demand, max production) are assumed to be per-day and are scaled by
        this factor automatically.
    """
    nodes: dict[str, Node] = field(default_factory=dict)
    dt_days: float = 1.0

    # Cached topological order; recomputed if nodes change.
    _topo_order: list[str] = field(default_factory=list, init=False, repr=False)

    # Per-connection delay buffers keyed by (source_id, target_id).
    # Each buffer is a deque of length == delay; popleft() yields water
    # arriving this step, append() enqueues water just released.
    _buffers: dict = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        self._topo_order = self._topological_sort()
        self._init_buffers()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset the simulator to its initial state.

        Restores every node's reservoir level to its original value and clears
        all in-transit water from delay buffers.  Use this to re-run a
        scenario from scratch without reloading the YAML.
        """
        for node in self.nodes.values():
            node.reset()
        self._init_buffers()

    def step(
        self,
        actions: dict[str, float],
        timestep: int = 0,
        dt_days: float | None = None,
        debug: bool = False,
    ) -> dict[str, NodeStepResult]:
        """Advance every node by one timestep and return the resulting states.

        Parameters
        ----------
        actions:
            Mapping of node ID → production fraction ∈ [0, 1].
            Any node not present in *actions* defaults to 0 (no production).
        timestep:
            Timestep index forwarded to time-aware modules.
        dt_days:
            Override the simulator's default timestep length for this step.
            If ``None`` (default), uses ``self.dt_days``.
        debug:
            If True, each node checks and logs water-balance violations.

        Returns
        -------
        dict[str, NodeStepResult]
            Mapping of node ID → per-node step result (see
            :class:`~node.NodeStepResult` for field descriptions).
        """
        dt = dt_days if dt_days is not None else self.dt_days

        # Warn about unrecognised node IDs in actions.
        for nid in actions:
            if nid not in self.nodes:
                logger.warning("Simulator.step(): unknown node id '%s' in actions (ignored).", nid)

        # Accumulate inflows delivered to each node from upstream releases.
        pending_inflow: dict[str, float] = {nid: 0.0 for nid in self.nodes}

        results: dict[str, NodeStepResult] = {}

        for node_id in self._topo_order:
            node = self.nodes[node_id]
            action = actions.get(node_id, 0.0)
            result = node.step(
                action=action,
                external_inflow=pending_inflow[node_id],
                timestep=timestep,
                dt_days=dt,
                debug=debug,
            )
            results[node_id] = result

            # Distribute production release AND spill to downstream nodes.
            # Spill travels the same channels but generates no energy.
            for conn in node.connections:
                routed = (result.production_release + result.spill) * conn.fraction
                key = (node_id, conn.node_id)
                if conn.delay == 0:
                    # Arrives within the same timestep.
                    pending_inflow[conn.node_id] += routed
                else:
                    # Shift the buffer: oldest parcel arrives now, new one
                    # is enqueued to arrive `delay` steps from now.
                    buf = self._buffers[key]
                    arriving = buf.popleft()
                    buf.append(routed)
                    pending_inflow[conn.node_id] += arriving

        return results

    def run(
        self,
        actions_sequence: list[dict[str, float]],
        start_timestep: int = 0,
        dt_days: float | None = None,
        debug: bool = False,
    ) -> list[dict[str, NodeStepResult]]:
        """Run the simulator over a sequence of timesteps.

        Parameters
        ----------
        actions_sequence:
            List of per-timestep action dicts (node ID → fraction).  Each
            entry is passed to :meth:`step` in order.
        start_timestep:
            Timestep index of the first entry in *actions_sequence* (default 0).
            Useful when continuing a partially-run simulation.
        dt_days:
            Timestep length override applied to every step.  ``None`` uses
            ``self.dt_days``.
        debug:
            Passed through to each :meth:`step` call.

        Returns
        -------
        list[dict[str, NodeStepResult]]
            One entry per timestep; same structure as the return value of
            :meth:`step`.
        """
        history = []
        for i, actions in enumerate(actions_sequence):
            result = self.step(
                actions=actions,
                timestep=start_timestep + i,
                dt_days=dt_days,
                debug=debug,
            )
            history.append(result)
        return history

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_buffers(self) -> None:
        """(Re)initialise all delay buffers to zero."""
        self._buffers = {}
        for node in self.nodes.values():
            for conn in node.connections:
                if conn.delay > 0:
                    self._buffers[(node.node_id, conn.node_id)] = deque(
                        [0.0] * conn.delay
                    )

    def _topological_sort(self) -> list[str]:
        """Return node IDs in topological order (upstream before downstream).

        Uses Kahn's algorithm (BFS-based).  Raises :exc:`ValueError` if the
        node graph contains a cycle.
        """
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        for node in self.nodes.values():
            for conn in node.connections:
                in_degree[conn.node_id] += 1

        queue: deque[str] = deque(
            nid for nid, deg in in_degree.items() if deg == 0
        )
        order: list[str] = []

        while queue:
            nid = queue.popleft()
            order.append(nid)
            for conn in self.nodes[nid].connections:
                in_degree[conn.node_id] -= 1
                if in_degree[conn.node_id] == 0:
                    queue.append(conn.node_id)

        if len(order) != len(self.nodes):
            raise ValueError(
                "Node connection graph contains a cycle; topological sort is impossible."
            )

        return order



