"""Time-stepping orchestrator."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from simengine.forcings import load_forcings
from simengine.graph import load_graph
from simengine.kpi import compute_monthly_kpis
from simengine.scenario import Scenario
from simengine.scoring import score_scenario


def run(scenario: Scenario, *, config_path: Path, topology_path: Path | None = None,
        geojson_path: Path | None = None, timeseries_dir: Path) -> Scenario:
    """Run a scenario in place: populates `scenario.results` and returns it."""
    graph = load_graph(config_path, topology_path=topology_path, geojson_path=geojson_path)

    # Load per-node forcings (may be empty DataFrame for confluences/sinks)
    for nid, node in graph.nodes.items():
        node.load_forcings(load_forcings(nid, timeseries_dir))

    # Determine number of time steps from any node that has forcings
    n_months = 0
    for node in graph.nodes.values():
        if len(node.forcings) > 0:
            n_months = max(n_months, len(node.forcings))
    if n_months == 0:
        raise ValueError("no forcings found for any node")

    # Filter to scenario period
    start, end = scenario.period
    for node in graph.nodes.values():
        if len(node.forcings):
            f = node.forcings.copy()
            f["month"] = pd.to_datetime(f["month"])
            mask = (f["month"] >= f"{start}-01") & (f["month"] <= f"{end}-01")
            node.forcings = f.loc[mask].reset_index(drop=True)
    n_months = max(len(n.forcings) for n in graph.nodes.values() if len(n.forcings))

    ts_per_node: dict[str, list[dict]] = {nid: [] for nid in graph.nodes}
    sink_outflow_by_month: dict[str, float] = {}

    for t in range(n_months):
        step_state: dict[str, dict] = {}
        # month label: pick from any node with forcings
        month_label = None
        for n in graph.nodes.values():
            if len(n.forcings) > t:
                ts = n.forcings.iloc[t]["month"]
                month_label = pd.Timestamp(ts).strftime("%Y-%m")
                break

        for nid in graph.order:
            node = graph.nodes[nid]
            if _wants_policy(node):
                policy = _policy_for_node(scenario.policy, node)
                node.step(t, step_state, policy=policy)
            else:
                node.step(t, step_state)
            if nid in step_state:
                ts_per_node[nid].append({"month": month_label, **step_state[nid]})
            if node.__class__.__name__ == "Sink":
                sink_outflow_by_month[month_label] = step_state[nid].get("inflow_m3s", 0.0)

    kpis = compute_monthly_kpis(ts_per_node)
    baseline = _derive_baseline(kpis)
    scoring = score_scenario(
        kpis, baseline,
        weights={"water": scenario.policy.weights.water,
                 "food": scenario.policy.weights.food,
                 "energy": scenario.policy.weights.energy},
        min_delta_flow_m3s=scenario.policy.constraints.min_delta_flow_m3s,
        sink_outflow=sink_outflow_by_month,
    )

    from simengine.scenario import ScenarioResults
    scenario.results = ScenarioResults(
        timeseries_per_node=ts_per_node,
        kpi_monthly=kpis,
        score=scoring["score"],
        score_breakdown=scoring["breakdown"],
    )
    return scenario


def run_scenario_file(scenario_path, config_path, timeseries_dir, out_path=None):
    s = Scenario.from_file(scenario_path)
    # Try topology.json adjacent to config; else fall back to nodes.geojson
    cfg = Path(config_path)
    topo = cfg.parent / "topology.json"
    geo = cfg.parent / "nodes.geojson"
    s = run(s, config_path=cfg,
            topology_path=topo if topo.exists() else None,
            geojson_path=geo if geo.exists() else None,
            timeseries_dir=Path(timeseries_dir))
    s.to_file(out_path or scenario_path)


def _wants_policy(node) -> bool:
    return node.__class__.__name__ in {"Reservoir", "DemandIrrigation", "DemandMunicipal"}


def _policy_for_node(policy, node) -> dict:
    nid = node.id
    if node.__class__.__name__ == "Reservoir":
        r = policy.reservoirs.get(nid)
        return r.model_dump() if r else {}
    if node.__class__.__name__ in {"DemandIrrigation", "DemandMunicipal"}:
        d = policy.demands.get(nid)
        return d.model_dump() if d else {}
    return {}


def _derive_baseline(kpis):
    """Baseline for normalization = mean of the KPI time-series itself."""
    n = max(1, len(kpis))
    return {
        "food_tonnes": max(1.0, sum(k["food_tonnes"] for k in kpis) / n),
        "energy_gwh": max(1.0, sum(k["energy_gwh"] for k in kpis) / n),
    }
