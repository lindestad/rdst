---
marp: true
theme: default
paginate: true
---

# Nile Digital Twin
**CASSINI Space for Water** · Team &lt;your name&gt; · 2026

A policy what-if sandbox for the Nile basin, grounded in historical ERA5
reanalysis and validated against Sentinel-2 NDVI. Move three sliders, see
cascading impact on water / food / energy downstream — in real units.

---

## The tension

The Nile serves ~500 M people across 11 countries. Three competing uses:

- **Ethiopia** — hydropower via GERD (6.45 GW nameplate).
- **Sudan** — irrigation via Gezira (~900 000 ha).
- **Egypt** — water security for 100 M people + the Delta.

Policy debates happen in m³/s. Headlines happen in "crisis."
There is nothing in between that a decision-maker can actually *try*.

---

## What we built

A node-graph digital twin of the basin:

- **19 nodes** — Lake Victoria, Lake Tana, Sudd wetland, GERD, Aswan, Egyptian Delta, ...
- **20 years** of ERA5 monthly forcings, per node.
- **Sentinel-2 NDVI** over irrigated zones as the food-KPI validator.
- **Three sliders, three KPIs, one score, compare view.**

---

## What space data does

| Product | Role |
|---|---|
| **ERA5 reanalysis** (C3S) | Monthly precipitation, temperature, radiation, wind, runoff → drives every forcings parquet. |
| **Sentinel-2 NDVI** (2015+) | Month-by-month crop greenness over Gezira + Delta — visual validator of the food KPI. |
| **CGLS NDVI** (2005–2014) | Fills the pre-Sentinel-2 window. |

All free. All Copernicus. Pipeline writes Parquet on disk — reusable beyond this demo.

---

## Demo — three scenarios

1. **Baseline** — historical operation.
2. **GERD fast-fill** — Ethiopia fills GERD over 3 years instead of 7.
   Energy ↑, Sudanese food ↓, Delta flow violations in Jul–Oct.
3. **Drought 2010** — tightened delta constraint + reduced Gezira area.
   Score collapses; twin shows *which* downstream users break first.

*(Live walkthrough — 90 s.)*

---

## The physics, one slide

Monthly time step, topological sweep.

- **Reservoirs**: `storage = prev + inflow − release − evap`, HEP on turbined release only, spill separate.
- **Reaches**: Muskingum routing (lag + attenuation).
- **Wetlands**: Sudd loses ~50 % of White Nile inflow — measured, not assumed.
- **Demands**: FAO monthly crop-water curve × area × productivity → tonnes.

Mass conservation verified to &lt;0.1 % in a golden test. Validated against GRDC Aswan discharge.

---

## Calibration

![w:700](calibration-report.html)

Simulated vs. observed monthly discharge at Aswan, 2005–2024.
Relative RMSE ~&lt;X&gt;% after grid-search tuning of source catchment scales and Sudd evaporation.

*(Honest about uncertainty — not all calibrated, some canonical basin numbers.)*

---

## Stretch — the optimizer

Given weights `(water, food, energy)`, grid-search over GERD release schedules
to find a policy that Pareto-beats the historical baseline:

&gt; "Shift ~300 m³/s of release from Q1 to Q3 → food +4 Mt, energy flat, no
&gt; delta violation."

*(If the optimizer button is visible, it works. If not, the manual what-if
still tells the story.)*

---

## What's next

- Tributary-level resolution (Sobat, Bahr el Ghazal).
- Real head–storage rating curves at each dam.
- Coupling with **CMEMS** (delta salinity) and **CAMS** (dust over irrigated areas).
- Forward scenarios using **CMIP6** downscaled climate.

---

## Try it now

- Code: &lt;github-url&gt;
- Demo: `docker compose up` → http://localhost:5173
- QR → live demo

*Team: @… @… @… @… @…*
