"""Build the three canned demo scenarios. Each is run through the sim engine
and saved to `data/scenarios/<name>.json` so the dashboard finds them.

1. **baseline**         — historical default policy across 2005–2024.
2. **gerd_fast_fill**   — GERD release pinned low 2020-01..2023-06, forcing
                          accelerated reservoir filling; downstream pain visible.
3. **drought_2010**     — 2009–2012 window with tightened delta flow and
                          reduced Gezira irrigation area (simulates a drought
                          response since we can't modulate ERA5 inputs here).

Requires real graph (19 nodes). Fails gracefully on stub data with a clear
error pointing to `python -m dataloader nodes`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from simengine.engine import run
from simengine.scenario import (
    Constraints, DemandPolicy, Policy, ReservoirPolicy, Scenario, Weights,
)

CONFIG = Path("data/node_config.yaml")
GEOJSON = Path("data/nodes.geojson")
TS = Path("data/timeseries")
SCEN = Path("data/scenarios")


def _month_keys(start: str, end: str) -> list[str]:
    return pd.date_range(f"{start}-01", f"{end}-01", freq="MS").strftime("%Y-%m").tolist()


def build_baseline() -> Scenario:
    return Scenario(
        name="baseline",
        period=["2005-01", "2024-12"],
        policy=Policy(
            reservoirs={},
            demands={},
            constraints=Constraints(min_delta_flow_m3s=500),
            weights=Weights(water=0.4, food=0.3, energy=0.3),
        ),
    )


def build_gerd_fast_fill() -> Scenario:
    low_release = {m: 500.0 for m in _month_keys("2020-01", "2023-06")}
    return Scenario(
        name="gerd_fast_fill",
        period=["2005-01", "2024-12"],
        policy=Policy(
            reservoirs={
                "gerd": ReservoirPolicy(mode="manual", release_m3s_by_month=low_release),
            },
            demands={},
            constraints=Constraints(min_delta_flow_m3s=500),
            weights=Weights(water=0.4, food=0.3, energy=0.3),
        ),
    )


def build_drought_2010() -> Scenario:
    return Scenario(
        name="drought_2010",
        period=["2009-01", "2012-12"],
        policy=Policy(
            reservoirs={},
            demands={"gezira_irr": DemandPolicy(area_scale=0.8)},
            constraints=Constraints(min_delta_flow_m3s=700),
            weights=Weights(water=0.5, food=0.3, energy=0.2),
        ),
    )


BUILDERS: list[Callable[[], Scenario]] = [
    build_baseline,
    build_gerd_fast_fill,
    build_drought_2010,
]


def main() -> None:
    SCEN.mkdir(parents=True, exist_ok=True)
    for builder in BUILDERS:
        s = builder()
        try:
            s = run(s, config_path=CONFIG, geojson_path=GEOJSON, timeseries_dir=TS)
        except KeyError as e:
            raise RuntimeError(
                f"scenario {s.name!r} references node {e} which is not in the "
                f"current graph. These canned scenarios target the real 19-node "
                f"Nile graph; run `python -m dataloader nodes` (without --stub) "
                f"first, or trim the canned scenarios to match your graph."
            ) from e
        out = SCEN / f"{s.name}.json"
        s.to_file(out)
        score = s.results.score if s.results and s.results.score is not None else float("nan")
        print(f"wrote {out} — score {score:.3f}")


if __name__ == "__main__":
    main()
