"""LP-based exact global-optimum social welfare optimizer.

Problem structure
-----------------
Given deterministic inflows and energy prices over a T-step horizon, the
social welfare maximisation problem is a **Linear Programme** (LP):

    Maximise   W = Σ_{i,t}  energy_weight · price[i,t] · r[i,t]
                           + food_weight  · food_per_m3[i] · f[i,t]

    Subject to (for every node i and timestep t):

      Water balance (equality):
        r[i,t] + s[i,t] + spill[i,t] + d[i,t] + f[i,t]
            − s[i, t−1]
            − Σ_{j→i}  fraction(j→i) · (r[j, t−delay] + spill[j, t−delay])
          = q[i,t]  +  (s_init[i]  if t == 0  else  0)

      Variable bounds:
        0 ≤ r[i,t]     ≤ max_production[i] · dt
        0 ≤ s[i,t]     ≤ max_capacity[i]
        0 ≤ spill[i,t]
        d[i,t]         = D[i,t]  (drinking-water demand must be fully met)
        0 ≤ f[i,t]     ≤ F_water_max[i,t]

Because the objective and every constraint are linear, SciPy's HiGHS solver
(scipy.optimize.linprog, method='highs') finds the *exact global optimum*
in polynomial time.

Why this is the true global optimum
------------------------------------
The feasible region is a convex polytope (intersection of linear equalities
and box bounds).  The objective is linear → the LP has no local optima that
are not global.  HiGHS guarantees optimality to machine precision.

Variables per (node i, timestep t), packed consecutively:
  k=0  r[i,t]     – production release (m³)
  k=1  s[i,t]     – reservoir level at end of timestep (m³)
  k=2  spill[i,t] – overflow (m³)
  k=3  d[i,t]     – drinking-water volume met (m³)
  k=4  f[i,t]     – food-production water consumed (m³)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

sys.path.insert(0, str(Path(__file__).parent.parent / "node"))

from node import NodeStepResult  # noqa: E402
from simulator import Simulator  # noqa: E402


@dataclass
class LPOptimizer:
    """Global-optimum LP optimizer for social welfare over a fixed horizon.

    Parameters
    ----------
    simulator:
        A freshly constructed :class:`~simulator.Simulator`.  The LP reads
        ``node.reservoir_level`` as the initial condition but does **not**
        call ``simulator.step()``, so the simulator state is never modified.
    T:
        Planning horizon in timesteps (e.g. 365 for one year).
    energy_weight:
        Weight for energy revenue in the objective (currency / currency).
        Default 1.0.
    food_weight:
        Weight for food production in the objective, expressed as
        **currency per food unit**.  The contribution per m³ of food water
        consumed is ``food_weight / water_coefficient``.  Default 0.08,
        which makes food roughly 50 % as valuable per m³ as energy.
    dt:
        Timestep length in days (default 1.0).
    """

    simulator: Simulator
    T: int
    energy_weight: float = 1.0
    food_weight: float = 0.08  # currency per food unit
    dt: float = 1.0

    _K: int = field(default=5, init=False, repr=False)  # vars per (node, t)

    def _var(self, i: int, t: int, k: int) -> int:
        return (i * self.T + t) * self._K + k

    def _eq(self, i: int, t: int) -> int:
        return i * self.T + t

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(self) -> tuple[list[dict[str, NodeStepResult]], dict]:
        """Solve the LP and return the globally optimal trajectory.

        Returns
        -------
        history : list[dict[str, NodeStepResult]]
            One result dict per timestep (same format as
            :meth:`HeuristicOptimizer.run`).
        info : dict
            Solver metadata: ``status``, ``message``, ``optimal_welfare``,
            ``n_vars``, ``n_constraints``.
        """
        nodes = list(self.simulator.nodes.values())
        node_ids = list(self.simulator.nodes.keys())
        N = len(nodes)
        T, dt = self.T, self.dt

        # ---- Precompute parameters -----------------------------------
        q = np.zeros((N, T))        # catchment inflow (m³)
        prices = np.zeros((N, T))   # energy price (currency/m³)
        D = np.zeros((N, T))        # drinking-water demand (m³)
        F_max = np.zeros((N, T))    # max food-water (m³)
        food_per_m3 = np.zeros(N)   # food units produced per m³ of food water

        for i, node in enumerate(nodes):
            for t in range(T):
                q[i, t] = node.catchment_inflow.inflow(t, dt)
                prices[i, t] = node.energy_price.price(t) if node.energy_price else 0.0
                D[i, t] = node.drink_water.demand(t, dt) if node.drink_water else 0.0
                if node.food_production:
                    fp = node.food_production
                    F_max[i, t] = fp.max_food_units * fp.water_coefficient * dt
            if node.food_production:
                food_per_m3[i] = 1.0 / node.food_production.water_coefficient

        # ---- Objective (linprog minimises → negate welfare) ----------
        n_vars = N * T * self._K
        c = np.zeros(n_vars)
        for i in range(N):
            for t in range(T):
                c[self._var(i, t, 0)] -= self.energy_weight * prices[i, t]
                c[self._var(i, t, 4)] -= self.food_weight * food_per_m3[i]

        # ---- Bounds --------------------------------------------------
        bounds: list[tuple] = []
        for i, node in enumerate(nodes):
            for t in range(T):
                r_max = node.max_production * dt
                s_max = node.max_capacity
                d_val = D[i, t]
                f_max = F_max[i, t]
                bounds.append((0.0, r_max))      # r[i,t]
                bounds.append((0.0, s_max))      # s[i,t]
                bounds.append((0.0, None))       # spill[i,t]
                bounds.append((d_val, d_val))    # d[i,t]  ← hard equality
                bounds.append((0.0, f_max))      # f[i,t]

        # ---- Upstream connection map ---------------------------------
        # conn_map[i] = list of (upstream_node_idx, fraction, delay)
        conn_map: dict[int, list] = {i: [] for i in range(N)}
        for up_i, node in enumerate(nodes):
            for conn in node.connections:
                dn_i = node_ids.index(conn.node_id)
                conn_map[dn_i].append((up_i, conn.fraction, conn.delay))

        # ---- Equality constraints: water balance ---------------------
        n_eq = N * T
        A_eq = lil_matrix((n_eq, n_vars))
        b_eq = np.zeros(n_eq)

        for i, node in enumerate(nodes):
            for t in range(T):
                eq = self._eq(i, t)

                # Current-node variables all have coefficient +1
                for k in range(self._K):
                    A_eq[eq, self._var(i, t, k)] = 1.0

                # Previous reservoir level
                if t > 0:
                    A_eq[eq, self._var(i, t - 1, 1)] = -1.0
                    b_eq[eq] = q[i, t]
                else:
                    # t = 0: the initial reservoir level stands in for s[i, -1]
                    b_eq[eq] = q[i, t] + node.reservoir_level

                # Subtract upstream routing contributions.
                # For src_t < 0 the initial buffer is 0 (simulator initialises
                # all delay-buffers with zeros), so no fixed RHS adjustment.
                for up_i, fraction, delay in conn_map[i]:
                    src_t = t - delay
                    if src_t >= 0:
                        A_eq[eq, self._var(up_i, src_t, 0)] -= fraction  # r
                        A_eq[eq, self._var(up_i, src_t, 2)] -= fraction  # spill

        # ---- Solve ---------------------------------------------------
        print(f"  Solving LP: {n_vars} variables, {n_eq} equality constraints …")
        result = linprog(
            c,
            A_eq=A_eq.tocsr(),
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
            options={"disp": False},
        )
        if result.status != 0:
            raise RuntimeError(f"LP solver failed (status {result.status}): {result.message}")

        print(f"  LP solved — status: {result.message}")
        x = result.x

        # ---- Reconstruct NodeStepResult history ----------------------
        history: list[dict[str, NodeStepResult]] = []
        for t in range(T):
            step: dict[str, NodeStepResult] = {}
            for i, node in enumerate(nodes):
                r     = max(0.0, x[self._var(i, t, 0)])
                s     = max(0.0, x[self._var(i, t, 1)])
                spill = max(0.0, x[self._var(i, t, 2)])
                d     = max(0.0, x[self._var(i, t, 3)])
                f     = max(0.0, x[self._var(i, t, 4)])

                ep = node.energy_price.price(t) if node.energy_price else 0.0
                food = f * food_per_m3[i]

                # Reconstruct total inflow for informational purposes
                ext = sum(
                    (max(0.0, x[self._var(up_i, t - delay, 0)])
                     + max(0.0, x[self._var(up_i, t - delay, 2)])) * frac
                    for up_i, frac, delay in conn_map[i]
                    if t - delay >= 0
                )
                total_inflow = q[i, t] + ext

                total_frac = sum(conn.fraction for conn in node.connections)
                step[node_ids[i]] = NodeStepResult(
                    reservoir_level=s,
                    production_release=r,
                    energy_value=r * ep,
                    food_produced=food,
                    drink_water_met=d,
                    unmet_drink_water=0.0,  # LP enforces d = D (hard equality)
                    spill=spill,
                    downstream_release=(r + spill) * min(total_frac, 1.0),
                    total_inflow=total_inflow,
                )
            history.append(step)

        info = {
            "status": result.status,
            "message": result.message,
            "optimal_welfare": -result.fun,
            "n_vars": n_vars,
            "n_constraints": n_eq,
        }
        return history, info
