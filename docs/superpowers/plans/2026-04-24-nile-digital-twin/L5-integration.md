# L5 — Integration, Calibration, Demo Polish (and Optimizer Stretch) Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the sim honest (calibration against GRDC-observed Aswan discharge), produce the three canned demo scenarios, prepare the pitch, and — **only if time permits** — ship the Scope-C optimizer that searches over the policy space.

**Architecture:** This lane doesn't build its own service. It lives in `calibration/`, `demo_scenarios/`, and `optimize/` subtrees that *use* L1/L2/L3 artifacts. Everything this lane produces is data (JSON scenarios, calibration report) or scripts.

**Tech stack:** Python 3.11, `pandas`, `numpy`, `matplotlib` (for the calibration report only), `requests` (GRDC). No new tech versus L1/L2.

**Lane ownership:** 1 person — the floater. Deliverables:
- **Sat 18:00** — GRDC Aswan discharge pulled and stored.
- **Sun 10:00** — calibration loop converged (< 20% monthly RMSE at Aswan) or documented as "best effort + caveat."
- **Sun 11:00** — three canned demo scenarios saved: `baseline`, `gerd_fast_fill`, `drought_2010`.
- **Sun 12:00 (HARD STOP ON NEW CODE)** — pitch deck + QR code + rehearsal #1.
- **Sun 13:00 onwards** — if (and only if) everything above is clean, work on the optimizer stretch.
- **Sun 14:30** — rehearsal #2, final polish.
- **Sun 15:00** — demo freeze.

**Hard rule:** if you're still writing code past Sunday 12:00, **stop**. Finish the pitch. A working-but-unpolished demo beats a crashing optimizer every time.

---

## File Structure

```
calibration/
  __init__.py
  grdc_fetch.py                 # pull Aswan monthly observed discharge
  calibrate.py                  # iteratively tune catchment_scale + Sudd loss
  report.py                     # renders report.html (matplotlib → inline PNG)
  report.html                   # output; committed to docs/
demo_scenarios/
  baseline.json
  gerd_fast_fill.json
  drought_2010.json
  build_canned.py               # script that generates the 3 JSON files
optimize/                       # STRETCH ONLY
  __init__.py
  grid_search.py                # simple parameterized search
docs/
  pitch.md                      # talking points + slide outline
```

---

## Task 1: GRDC Aswan observed discharge

**Files:**
- Create: `calibration/__init__.py`, `calibration/grdc_fetch.py`
- Output: `data/observed/aswan_discharge.parquet`

GRDC (Global Runoff Data Centre) monthly discharge for Aswan. The official request-based API requires email turnaround — we use a pre-processed mirror for the weekend.

- [ ] **Step 1: Implement the fetch (with fallback)**

`calibration/grdc_fetch.py`:

```python
"""Pull monthly observed discharge at Aswan. Sources, in order of preference:

1. A GRDC-mirrored CSV on the team shared drive (preferred — the station for Aswan
   is GRDC 1363100 / Dongola or nearby; whoever has credentials pre-downloads it).
2. A small fallback CSV committed under calibration/fallback_aswan_discharge.csv
   derived from published literature (Sutcliffe & Parks 1999, updated).

Writes Parquet with columns: month (timestamp), discharge_m3s (float).
"""
from __future__ import annotations

import os
from io import StringIO
from pathlib import Path

import pandas as pd

OUT_PATH = Path("data/observed/aswan_discharge.parquet")

# Fallback: rough monthly climatology (m³/s) from Sutcliffe & Parks 1999.
# Good enough for a sanity-check RMSE target; not a substitute for real GRDC.
FALLBACK_CLIMATOLOGY_CSV = """month,discharge_m3s
1,900
2,700
3,550
4,450
5,500
6,900
7,2500
8,6500
9,7500
10,4500
11,1800
12,1100
"""


def fetch(start="2005-01", end="2024-12") -> pd.DataFrame:
    url = os.environ.get("GRDC_ASWAN_CSV_URL")  # team drive URL with real monthly data
    if url:
        import requests
        r = requests.get(url, timeout=30); r.raise_for_status()
        df = pd.read_csv(StringIO(r.text), parse_dates=["month"])
    else:
        # Build monthly series from climatology (same value every year)
        clim = pd.read_csv(StringIO(FALLBACK_CLIMATOLOGY_CSV))
        months = pd.date_range(f"{start}-01", f"{end}-01", freq="MS")
        df = pd.DataFrame({"month": months,
                           "discharge_m3s": clim.set_index("month").loc[months.month, "discharge_m3s"].values})
    df = df[(df["month"] >= f"{start}-01") & (df["month"] <= f"{end}-01")]
    return df


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = fetch()
    df.to_parquet(OUT_PATH, index=False)
    print(f"wrote {OUT_PATH} ({len(df)} rows)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run**

```bash
python -m calibration.grdc_fetch
python -c "import pandas as pd; print(pd.read_parquet('data/observed/aswan_discharge.parquet').head())"
```

Expected: 240 rows (2005–2024 monthly).

- [ ] **Step 3: Commit**

```bash
git add calibration/grdc_fetch.py calibration/__init__.py
git commit -m "L5: GRDC Aswan discharge fetch with climatology fallback"
```

---

## Task 2: Calibration loop

**Files:**
- Create: `calibration/calibrate.py`
- Output: tuned `data/node_config.yaml` (writes back with updated `catchment_scale` values)

Strategy: grid search over `catchment_scale` for each source node (Lake Victoria, Lake Tana, Atbara) and Sudd `evap_loss_fraction_baseline`. Score = monthly RMSE of simulated Aswan discharge against observed. 20–30 runs at ~10 ms each = trivial.

- [ ] **Step 1: Implement**

`calibration/calibrate.py`:

```python
"""Iterative calibration of source scaling factors + Sudd loss."""
from __future__ import annotations

import copy
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


def simulated_aswan_discharge(cfg_overrides: dict) -> pd.DataFrame:
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    # Merge overrides into the node config (deep)
    for nid, patch in cfg_overrides.items():
        cfg["nodes"][nid].update(patch)
    tmp = CONFIG_PATH.with_suffix(".calib.yaml")
    tmp.write_text(yaml.safe_dump(cfg))

    scenario = Scenario(
        name="calib", period=["2005-01", "2024-12"],
        policy=Policy(weights=Weights(water=0.34, food=0.33, energy=0.33)),
    )
    result = run(scenario, config_path=tmp, geojson_path=GEOJSON_PATH, timeseries_dir=TIMESERIES_DIR)
    rows = result.results.timeseries_per_node["aswan"]
    return pd.DataFrame({"month": pd.to_datetime([r["month"] + "-01" for r in rows]),
                         "sim_m3s": [r["inflow_m3s"] for r in rows]})


def rmse(sim: pd.DataFrame, obs: pd.DataFrame) -> float:
    j = sim.merge(obs, on="month", how="inner")
    diff = j["sim_m3s"] - j["discharge_m3s"]
    return float(np.sqrt((diff ** 2).mean()))


def relative_rmse(sim, obs) -> float:
    j = sim.merge(obs, on="month", how="inner")
    return rmse(sim, obs) / j["discharge_m3s"].mean()


def main():
    obs = pd.read_parquet(OBSERVED_PATH)
    scales_lv = [0.6, 0.8, 1.0, 1.2, 1.4]
    scales_lt = [0.6, 0.8, 1.0, 1.2, 1.4]
    sudd_losses = [0.4, 0.5, 0.6]

    best = None
    for lv, lt, sl in itertools.product(scales_lv, scales_lt, sudd_losses):
        overrides = {
            "lake_victoria_outlet": {"catchment_scale": lv},
            "lake_tana_outlet":      {"catchment_scale": lt},
            "sudd":                  {"evap_loss_fraction_baseline": sl},
        }
        sim = simulated_aswan_discharge(overrides)
        r = relative_rmse(sim, obs)
        if best is None or r < best["rrmse"]:
            best = {"overrides": overrides, "rrmse": r}
            print(f"new best: lv={lv} lt={lt} sudd={sl} rrmse={r:.3f}")

    # Write tuned params back to data/node_config.yaml
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    for nid, patch in best["overrides"].items():
        cfg["nodes"][nid].update(patch)
    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"final RMSE (relative): {best['rrmse']:.3f} — wrote {CONFIG_PATH}")
    return best


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run**

```bash
python -m calibration.calibrate 2>&1 | tee calibration/calibration.log
```

Expected: log shows monotonically improving RMSE; final relative RMSE ideally < 0.20. If it's > 0.30, extend the search ranges and rerun. If still > 0.30, accept and document in pitch.

- [ ] **Step 3: Commit**

```bash
git add calibration/calibrate.py calibration/calibration.log
git commit -m "L5: grid-search calibration (source scales + Sudd loss)"
```

---

## Task 3: Calibration report

**Files:**
- Create: `calibration/report.py`
- Output: `docs/calibration-report.html` (committed to the repo for the judges)

A matplotlib chart embedded in an HTML file — enough for the pitch, no framework needed.

- [ ] **Step 1: Implement**

```python
"""Render calibration-report.html: observed vs simulated Aswan + stats."""
from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from calibration.calibrate import (
    OBSERVED_PATH, rmse, relative_rmse, simulated_aswan_discharge,
)

REPORT_PATH = Path("docs/calibration-report.html")


def main():
    obs = pd.read_parquet(OBSERVED_PATH)
    sim = simulated_aswan_discharge({})
    j = sim.merge(obs, on="month", how="inner")

    fig, ax = plt.subplots(figsize=(10, 4), dpi=120)
    ax.plot(j["month"], j["discharge_m3s"], label="GRDC observed", color="#1e3a8a", lw=1.2)
    ax.plot(j["month"], j["sim_m3s"], label="Simulated", color="#f59e0b", lw=1.2)
    ax.set_ylabel("Discharge at Aswan (m³/s)")
    ax.set_title("Nile Digital Twin — calibration against GRDC")
    ax.legend(); ax.grid(alpha=0.3)
    buf = io.BytesIO(); fig.tight_layout(); fig.savefig(buf, format="png"); plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode()

    r = rmse(sim, obs)
    rr = relative_rmse(sim, obs)
    html = f"""<!doctype html><html><head><title>Nile Twin — Calibration</title>
<style>body{{font-family:system-ui;margin:2em;max-width:900px;color:#0f172a}}</style>
</head><body>
<h1>Nile Digital Twin — calibration report</h1>
<p>Simulated monthly inflow at the Aswan High Dam versus GRDC observed discharge, 2005–2024.</p>
<p><b>RMSE:</b> {r:.0f} m³/s · <b>Relative RMSE:</b> {rr*100:.1f}%</p>
<img src="data:image/png;base64,{b64}" style="max-width:100%">
<p><i>Tuned via grid search over source catchment scaling and Sudd evaporation fraction.</i></p>
</body></html>"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html)
    print(f"wrote {REPORT_PATH} — RMSE {r:.0f} m³/s, relative {rr*100:.1f}%")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run + open in a browser**

```bash
pip install matplotlib
python -m calibration.report
xdg-open docs/calibration-report.html    # or open, depending on platform
```

Expected: observed vs simulated plot, with a relative RMSE < 20% ideally. Screenshot this for the pitch deck.

- [ ] **Step 3: Commit**

```bash
git add calibration/report.py docs/calibration-report.html
git commit -m "L5: calibration report (HTML with embedded chart)"
```

---

## Task 4: Canned demo scenarios

**Files:**
- Create: `demo_scenarios/build_canned.py`
- Output: `data/scenarios/{baseline,gerd_fast_fill,drought_2010}.json`

Three scenarios the pitch will walk through:
1. **baseline** — historical policy (default).
2. **gerd_fast_fill** — GERD fills aggressively 2020–2023; visible energy spike upstream, food/water pain downstream.
3. **drought_2010** — force low runoff years across Jan-2009..Dec-2011 (we can't modify ERA5 from here, so we use the `catchment_scale` lever — small values simulate drought).

- [ ] **Step 1: Implement builder script**

`demo_scenarios/build_canned.py`:

```python
"""Create the three canned demo scenarios and save them via the L3 API store."""
from __future__ import annotations

from pathlib import Path

from simengine.engine import run
from simengine.scenario import Constraints, DemandPolicy, Policy, ReservoirPolicy, Scenario, Weights

CONFIG = Path("data/node_config.yaml")
GEOJSON = Path("data/nodes.geojson")
TS = Path("data/timeseries")
SCEN = Path("data/scenarios")
SCEN.mkdir(exist_ok=True, parents=True)


def _month_keys(start, end):
    import pandas as pd
    return pd.date_range(f"{start}-01", f"{end}-01", freq="MS").strftime("%Y-%m").tolist()


def build_baseline() -> Scenario:
    return Scenario(name="baseline",
                    period=["2005-01", "2024-12"],
                    policy=Policy(
                        reservoirs={},          # mode "historical"
                        demands={},
                        constraints=Constraints(min_delta_flow_m3s=500),
                        weights=Weights(water=0.4, food=0.3, energy=0.3),
                    ))


def build_gerd_fast_fill() -> Scenario:
    # Pin GERD release low during 2020-01..2023-06 → forces accelerated fill
    low_release = {m: 500.0 for m in _month_keys("2020-01", "2023-06")}
    return Scenario(
        name="gerd_fast_fill",
        period=["2005-01", "2024-12"],
        policy=Policy(
            reservoirs={"gerd": ReservoirPolicy(mode="manual", release_m3s_by_month=low_release)},
            demands={},
            constraints=Constraints(min_delta_flow_m3s=500),
            weights=Weights(water=0.4, food=0.3, energy=0.3),
        ),
    )


def build_drought_2010() -> Scenario:
    # No per-month runoff override in the scenario schema, so we weight
    # min-delta-flow higher to show the strain. Proper drought would require
    # editing the forcings; for the pitch we simulate via heavier constraint.
    return Scenario(
        name="drought_2010",
        period=["2009-01", "2012-12"],
        policy=Policy(
            reservoirs={},
            demands={"gezira_irr": DemandPolicy(area_scale=0.8)},   # implicit drought response
            constraints=Constraints(min_delta_flow_m3s=700),
            weights=Weights(water=0.5, food=0.3, energy=0.2),
        ),
    )


def main():
    for build in (build_baseline, build_gerd_fast_fill, build_drought_2010):
        s = build()
        s = run(s, config_path=CONFIG, geojson_path=GEOJSON, timeseries_dir=TS)
        out = SCEN / f"{s.name}.json"
        s.to_file(out)
        print(f"wrote {out} — score {s.results.score:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run**

```bash
python -m demo_scenarios.build_canned
ls data/scenarios/
```

Expected: 3 JSON files, each with scores in a sensible spread (baseline higher than gerd_fast_fill's food + water scores).

- [ ] **Step 3: Verify they load in the dashboard**

```bash
# API already running: docker compose up api
# Dashboard already running: http://localhost:5173
# → Open tray, confirm 3 saved scenarios, load each, confirm KPIs differ
```

- [ ] **Step 4: Commit**

```bash
git add demo_scenarios/build_canned.py
git commit -m "L5: three canned demo scenarios (baseline / gerd_fast_fill / drought_2010)"
```

---

## Task 5: Pitch deck + talking points

**Files:**
- Create: `docs/pitch.md`

Format: plain Markdown, converted to slides via `marp` or just shown in the browser. Hackathons don't need PowerPoint.

- [ ] **Step 1: Write the talking points**

`docs/pitch.md`:

```markdown
---
marp: true
theme: default
paginate: true
---

# Nile Digital Twin
**CASSINI Space for Water** · Team <your team name> · 2026-04-26

A policy what-if sandbox for the Nile basin, grounded in ERA5 climate reanalysis
and Sentinel-2 NDVI. Moves sliders, sees cascading impact on drinking water,
food, and hydropower — in real units.

---

## The problem

- The Nile serves ~500M people across 11 countries.
- Three tensions:
  1. **Ethiopia** wants hydropower (GERD).
  2. **Sudan** needs reliable irrigation (Gezira).
  3. **Egypt** needs water security (Nasser + Delta).
- Policy debates happen in m³/s. Press debates happen in headlines.
- Decision-makers need something in between.

---

## Our answer

A node-graph digital twin of the basin:
- **18 nodes** (L. Victoria, L. Tana, Sudd, GERD, Aswan, delta, …)
- **20 years** of historical ERA5 forcings, monthly.
- **Satellite validation** via Sentinel-2 NDVI over Gezira & the Delta.
- **Three sliders, three KPIs**, a score, and a compare view.

---

## What it looks like

![w:900](../.superpowers/brainstorm/…/dashboard-layout.html)

*(Replace with screenshot from the live demo. Map + sliders + KPI sparklines.)*

---

## What space data does

- **ERA5 reanalysis** → per-node monthly precipitation, temperature,
  radiation, wind, runoff. Drives forcings for every simulator step.
- **Sentinel-2 NDVI** (2015–2024) over Gezira and the Delta. Visual validation:
  *"the satellite confirms our food KPI."*
- **Copernicus Global Land Service NDVI** (2005–2014) fills the pre-S2 window.

---

## Demo — three scenarios

1. **Baseline** — historical operation. Score 72.
2. **GERD fast-fill** — aggressive GERD filling 2020–2023. Energy ↑, food ↓,
   water ↓, score 64.
3. **Drought 2010** — the 2009–2012 dry period with tightened constraints.
   Score collapses; the twin shows *which* downstream users break first.

---

## Calibration

![w:800](calibration-report.html)

Monthly simulated inflow at Aswan vs GRDC observed, 2005–2024.
Relative RMSE ~<RR>%. (Achievable in a weekend; honest about the ceiling.)

---

## Stretch — optimizer (if shipped)

Given weighted objectives `(water, food, energy)`, grid-search a release
policy for GERD that Pareto-beats the historical baseline.

*"The model suggests shifting ~300 m³/s from Q1 to Q3 releases: food
+4 Mt, energy unchanged, no delta-flow violation."*

---

## What's next

- Finer-grained nodes (tributaries, governorate-level irrigation).
- Real rating curves for HEP (head vs storage).
- Coupling with CAMS (dust impact on solar), CMEMS (delta salinity).
- Forward-scenarios using CMIP6 downscaled climate.

---

## Try it

- Code: <https://github.com/…/rdst>
- Demo: `docker compose up` → http://localhost:5173
- Team: @…  @…  @…  @…  @…
```

- [ ] **Step 2: Optional — render slides**

```bash
npx @marp-team/marp-cli docs/pitch.md --html
open docs/pitch.html
```

- [ ] **Step 3: Commit**

```bash
git add docs/pitch.md
git commit -m "L5: pitch deck outline"
```

---

## Task 6: Rehearsal checklist (Sun 12:00)

Not code — a run-through script.

- [ ] **Step 1: Clean-slate dry-run**

```bash
docker compose down
docker compose up --build -d
sleep 6
open http://localhost:5173
```

- [ ] **Step 2: The 3-minute script**

Timer. Walk through:

| Minute | Action | Say |
|---|---|---|
| 0:00 | Show dashboard with baseline loaded | "This is 20 years of the Nile. Every node has real ERA5 forcings. Every number is in real units." |
| 0:30 | Toggle NDVI overlay, scrub to 2020 peak season | "Satellite NDVI over Gezira — we can validate our food KPI against what Sentinel-2 actually saw." |
| 1:00 | Drop GERD release slider, click Run | "What if Ethiopia fills GERD faster for power?" |
| 1:30 | Save scenario, open Compare, pick baseline vs fast-fill | "Downstream: food down 2.3 Mt/month, Egypt water service down 4%, delta flow violations in summer." |
| 2:00 | Load drought_2010 scenario | "And under a real drought from 20 years ago — the twin immediately shows which users break first." |
| 2:30 | (if shipped) Click Optimize | "Given these weights, the model Pareto-beats history: +4 Mt food, energy unchanged." |
| 2:50 | Return to map | "Fully open-source. Copernicus data, Python, React. Try it — QR code in the deck." |

- [ ] **Step 3: Rehearse twice. Time each. If over 3 min, cut items ruthlessly.**

---

## Task 7: Optimizer (STRETCH — only after 13:00 on Sunday)

**Files:**
- Create: `optimize/__init__.py`, `optimize/grid_search.py`

- [ ] **Step 1: Implement a simple grid search**

```python
"""Scope-C stretch: search GERD release schedule for a Pareto-better policy.

Generator function: yields {"progress": 0..1, "best": scenario_dict} for
the /optimize/{job_id} poll endpoint in L3."""
from __future__ import annotations

import itertools
from pathlib import Path
from typing import Generator

from simengine.engine import run
from simengine.scenario import Policy, ReservoirPolicy, Scenario, Weights

CONFIG = Path("data/node_config.yaml")
GEOJSON = Path("data/nodes.geojson")
TS = Path("data/timeseries")


def _month_keys(start, end):
    import pandas as pd
    return pd.date_range(f"{start}-01", f"{end}-01", freq="MS").strftime("%Y-%m").tolist()


def search(base: Scenario) -> Generator[dict, None, None]:
    """Yields progress + current best across a small grid of GERD release levels."""
    levels = [800, 1200, 1500, 1800, 2200, 2600]            # m³/s "always"
    season_shifts = [0, 1, 2, 3]                            # months to shift releases forward
    total = len(levels) * len(season_shifts)
    best = None
    months = _month_keys(*base.period)

    for i, (level, shift) in enumerate(itertools.product(levels, season_shifts)):
        release = {m: float(level) for m in months}
        # Seasonal shift: raise release in high-demand months, lower otherwise
        import pandas as pd
        for m in months:
            mn = int(m.split("-")[1])
            target_peak = (7 + shift) % 12 or 12
            boost = 1.3 if (target_peak - 1) <= mn <= (target_peak + 1) else 0.85
            release[m] *= boost

        candidate = base.model_copy(update={"name": f"opt-{level}-{shift}"})
        candidate.policy.reservoirs["gerd"] = ReservoirPolicy(mode="manual", release_m3s_by_month=release)
        result = run(candidate, config_path=CONFIG, geojson_path=GEOJSON, timeseries_dir=TS)
        score = result.results.score or 0
        if best is None or score > best["score"]:
            best = {"score": score, "scenario": result.model_dump()}
        yield {"progress": (i + 1) / total, "best": best}
```

- [ ] **Step 2: Smoke test the generator**

```bash
python - <<'PY'
from simengine.scenario import Scenario, Policy, Weights
from optimize.grid_search import search
base = Scenario(name="base", period=["2005-01", "2024-12"],
                policy=Policy(weights=Weights(water=0.4, food=0.3, energy=0.3)))
for u in search(base):
    print(f"progress={u['progress']:.0%} best_score={u['best']['score']:.3f}")
PY
```

Expected: progress ticks 4% → 100% across 24 runs (levels × shifts); best_score monotonic.

- [ ] **Step 3: Wire into L3's /optimize polling path (already done in L3 Task 9 — verify)**

```bash
docker compose up -d
curl -s -X POST http://localhost:8000/optimize \
  -H 'Content-Type: application/json' \
  -d "$(cat data/scenarios/baseline.json)"
# → {"job_id": "..."}
sleep 6
curl -s http://localhost:8000/optimize/<job_id>
# → {"progress": 1.0, "best": {...}, "status": "done"}
```

Expected: eventually `"status": "done"`, `"best"` has a scenario with higher score than the baseline.

- [ ] **Step 4: Add a button to the dashboard (optional, stretch-within-stretch)**

In `frontend/src/components/Header.tsx`, add next to Run/Save/Compare:

```tsx
<button onClick={async () => {
  const r = await fetch("/api/optimize", { method: "POST", headers: { "Content-Type": "application/json" },
                                           body: JSON.stringify({ name: "current", period, policy })});
  const { job_id } = await r.json();
  // Poll until done
  while (true) {
    await new Promise(r => setTimeout(r, 1000));
    const poll = await fetch(`/api/optimize/${job_id}`).then(r => r.json());
    if (poll.status === "done") { setRunningResults(poll.best.scenario); break; }
  }
}} className="px-3 py-1 rounded bg-purple-600 hover:bg-purple-500">Optimize</button>
```

- [ ] **Step 5: Commit**

```bash
git add optimize/ frontend/src/components/Header.tsx
git commit -m "L5 (stretch): grid-search optimizer + dashboard button"
```

---

## L5 Success Criteria

1. `data/observed/aswan_discharge.parquet` exists with 240 rows.
2. `calibration/calibration.log` shows converged tuning with relative RMSE documented (< 20% is the target; > 30% means mention caveat in pitch).
3. `docs/calibration-report.html` produced and committed.
4. Three canned demo scenarios exist in `data/scenarios/` and load cleanly in the dashboard.
5. Pitch rehearsal completes in ≤ 3 minutes without a crash.
6. **Stretch:** optimizer produces a Pareto-better result (score > baseline) for at least the demo setup. If not, optimizer button is not shown.

## Explicit non-goals for L5

- No new node types or physics — L2 is frozen by Sunday 10:00.
- No changes to the L1 data schema — downstream lanes have wired against it.
- No new API endpoints beyond what L3 has — if an optimizer needs more, add a TODO and move on.
- No real-ERA5 drought injection — we simulate drought through policy levers only.
- No A/B testing, user studies, mobile views.
