"""Iterative calibration of source scaling factors + Sudd loss.

Grid-search over (Lake Victoria scale, Lake Tana scale, Sudd evap fraction)
minimizing relative RMSE of simulated Aswan discharge vs. GRDC observed.
Writes the best parameters back into `data/node_config.yaml`.

Requires a full 19-node configuration (real `dataloader nodes`), not --stub.
Against stub data, exits with a helpful error.
"""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from simengine.engine import run
from simengine.scenario import Policy, Scenario, Weights

CONFIG_PATH = Path("data/node_config.yaml")
GEOJSON_PATH = Path("data/nodes.geojson")
TIMESERIES_DIR = Path("data/timeseries")
OBSERVED_PATH = Path("data/observed/aswan_discharge.parquet")
TARGET_NODE = "aswan"


def simulated_target_discharge(cfg_overrides: dict) -> pd.DataFrame:
    """Run the sim with the overrides patched into node_config.yaml, return
    the target node's inflow as a monthly time-series."""
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    for nid, patch in cfg_overrides.items():
        if nid in cfg["nodes"]:
            cfg["nodes"][nid].update(patch)
    tmp = CONFIG_PATH.with_suffix(".calib.yaml")
    tmp.write_text(yaml.safe_dump(cfg, sort_keys=False))

    scenario = Scenario(
        name="calib", period=["2005-01", "2024-12"],
        policy=Policy(weights=Weights(water=0.34, food=0.33, energy=0.33)),
    )
    result = run(scenario, config_path=tmp, geojson_path=GEOJSON_PATH, timeseries_dir=TIMESERIES_DIR)
    if TARGET_NODE not in result.results.timeseries_per_node:
        raise RuntimeError(
            f"target node {TARGET_NODE!r} not in graph — calibration needs the full "
            f"19-node Nile graph (run `python -m dataloader nodes` without --stub)."
        )
    rows = result.results.timeseries_per_node[TARGET_NODE]
    return pd.DataFrame({
        "month": pd.to_datetime([r["month"] + "-01" for r in rows]),
        "sim_m3s": [r["inflow_m3s"] for r in rows],
    })


def rmse(sim: pd.DataFrame, obs: pd.DataFrame) -> float:
    j = sim.merge(obs, on="month", how="inner")
    diff = j["sim_m3s"] - j["discharge_m3s"]
    return float(np.sqrt((diff ** 2).mean()))


def relative_rmse(sim: pd.DataFrame, obs: pd.DataFrame) -> float:
    j = sim.merge(obs, on="month", how="inner")
    mean_obs = j["discharge_m3s"].mean()
    return float(rmse(sim, obs) / mean_obs) if mean_obs > 0 else float("inf")


def main() -> dict:
    if not OBSERVED_PATH.exists():
        raise FileNotFoundError(
            f"{OBSERVED_PATH} missing — run `python -m calibration.grdc_fetch` first."
        )
    obs = pd.read_parquet(OBSERVED_PATH)

    lv_scales = [0.6, 0.8, 1.0, 1.2, 1.4]
    lt_scales = [0.6, 0.8, 1.0, 1.2, 1.4]
    sudd_losses = [0.4, 0.5, 0.6]

    best: dict | None = None
    for lv, lt, sl in itertools.product(lv_scales, lt_scales, sudd_losses):
        overrides = {
            "lake_victoria_outlet": {"catchment_scale": lv},
            "lake_tana_outlet":      {"catchment_scale": lt},
            "sudd":                  {"evap_loss_fraction_baseline": sl},
        }
        sim = simulated_target_discharge(overrides)
        rr = relative_rmse(sim, obs)
        if best is None or rr < best["rrmse"]:
            best = {"overrides": overrides, "rrmse": rr}
            print(f"new best: lv={lv} lt={lt} sudd={sl} rrmse={rr:.3f}")

    assert best is not None
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    for nid, patch in best["overrides"].items():
        if nid in cfg["nodes"]:
            cfg["nodes"][nid].update(patch)
    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"final relative RMSE: {best['rrmse']:.3f} — wrote tuned {CONFIG_PATH}")
    return best


if __name__ == "__main__":
    main()
