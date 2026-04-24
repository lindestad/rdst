"""Scope-C stretch: grid-search a GERD release schedule that improves the
scenario score vs. the caller's baseline policy.

Exposed as an iterator so the L3 `/optimize` endpoint can stream progress
updates to the client.
"""
from __future__ import annotations

import itertools
from pathlib import Path
from typing import Generator

import pandas as pd

from simengine.engine import run
from simengine.scenario import ReservoirPolicy, Scenario

CONFIG = Path("data/node_config.yaml")
GEOJSON = Path("data/nodes.geojson")
TS = Path("data/timeseries")


def _month_keys(start: str, end: str) -> list[str]:
    return pd.date_range(f"{start}-01", f"{end}-01", freq="MS").strftime("%Y-%m").tolist()


def search(base: Scenario) -> Generator[dict, None, None]:
    """Iterate over (level, seasonal-shift) combinations, run each, yield
    the current best-known scenario. Up to `len(levels) * len(shifts)` sim
    runs; each is ~10 ms so the whole sweep finishes in under a second."""
    levels = [800, 1200, 1500, 1800, 2200, 2600]   # m³/s baseline for GERD
    season_shifts = [0, 1, 2, 3]                    # months to push the peak
    total = len(levels) * len(season_shifts)
    months = _month_keys(*base.period)

    best: dict | None = None
    for i, (level, shift) in enumerate(itertools.product(levels, season_shifts)):
        release = {}
        for m in months:
            month_num = int(m.split("-")[1])
            target_peak = ((7 + shift - 1) % 12) + 1   # default peak = Jul, shift forward
            near_peak = abs(month_num - target_peak) <= 1 or abs(month_num - target_peak) >= 11
            release[m] = float(level) * (1.3 if near_peak else 0.85)

        candidate = base.model_copy(deep=True, update={"name": f"opt-{level}-{shift}"})
        candidate.policy.reservoirs["gerd"] = ReservoirPolicy(
            mode="manual", release_m3s_by_month=release,
        )
        result = run(
            candidate,
            config_path=CONFIG,
            geojson_path=GEOJSON,
            timeseries_dir=TS,
        )
        score = result.results.score or 0.0
        if best is None or score > best["score"]:
            best = {"score": score, "scenario": result.model_dump()}
        yield {"progress": (i + 1) / total, "best": best}
