# L4 — Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A React + Vite + TypeScript SPA with map-first layout (MapLibre), left-rail policy sliders, right-rail Plotly KPI panels, scenario save/load tray, Compare view, month scrubber, and NDVI raster overlay. Talks to the L3 API.

**Architecture:** SPA. No SSR. Zustand for state. MapLibre GL for the map (uses a free raster basemap — no paid tiles). Plotly via `react-plotly.js`. NDVI overlay is a raster tile source pointing at the static tiles produced by L1 Task 10.

**Tech stack:** Node 20, Vite 5, React 18, TypeScript 5, MapLibre GL 4, `react-plotly.js`, Zustand, Tailwind CSS, `vitest` (for the handful of unit tests that earn their keep).

**Lane ownership:** 2 people. Split suggestion:
- **Person A:** Map + node layer + node inspector + scrubber + NDVI overlay.
- **Person B:** API client + state + left rail + right rail + scenario tray + Compare view.
Tasks below note which person naturally picks each up.

**Deliverables:**
- **Sat 17:00** — UI renders against L3 stub API, sliders move, Run returns a response, KPI charts update. No map styling yet — just a node list + charts.
- **Sun 09:00** — full map layer live; Save/Load/Compare work.
- **Sun 13:00** — NDVI overlay + month scrubber; demo polish.

**Shared contracts** (see L3 plan): timeseries + NDVI are column-oriented JSON; Scenario JSON round-trips exactly as L2 defines it.

---

## File Structure

```
frontend/
  package.json
  tsconfig.json
  vite.config.ts
  tailwind.config.js
  postcss.config.js
  index.html
  src/
    main.tsx
    App.tsx
    api/
      client.ts              # fetch wrappers
      types.ts               # TS mirrors of spec/L3 shapes
    state/
      store.ts               # Zustand
    components/
      Header.tsx             # title + Run/Save/Compare buttons
      LeftRail.tsx           # sliders, weights, period
      RightRail.tsx          # KPI panels
      NileMap.tsx            # MapLibre + node layer
      NodeInspector.tsx      # popover on node click
      MonthScrubber.tsx
      ScenarioTray.tsx
      CompareView.tsx
    lib/
      kpiChart.tsx           # Plotly wrapper
      colors.ts              # shared palettes
      ndvi.ts                # NDVI overlay source builder
  public/
    nile-style.json          # MapLibre style (OSM raster basemap)
  Dockerfile.frontend
  nginx.conf
  tests/
    api.test.ts
    store.test.ts
```

---

## Task 1: Vite scaffold + deps + Tailwind

**Files:**
- Create: `frontend/` subtree (scaffolded by `npm create`)

- [ ] **Step 1: Scaffold**

```bash
cd /home/storms/persprojects/aenergi/fairwater
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install maplibre-gl react-plotly.js plotly.js zustand
npm install -D @types/react @types/react-dom vitest @vitest/ui \
  tailwindcss@3 postcss autoprefixer @types/plotly.js
npx tailwindcss init -p
```

- [ ] **Step 2: Configure Tailwind**

`frontend/tailwind.config.js`:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

Replace `frontend/src/index.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body, #root { height: 100%; margin: 0; }
body { font-family: ui-sans-serif, system-ui, sans-serif; }
```

- [ ] **Step 3: Configure Vite proxy to the API**

`frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: p => p.replace(/^\/api/, "") },
      "/tiles": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  test: { environment: "jsdom" },
});
```

- [ ] **Step 4: Smoke test**

```bash
npm run dev
# open http://localhost:5173 in a browser
# CTRL-C to stop
```

Expected: Vite default page loads.

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/
git commit -m "L4: Vite + React + Tailwind scaffold"
```

---

## Task 2: TypeScript types + API client

**Files:**
- Create: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`
- Create: `frontend/tests/api.test.ts`

- [ ] **Step 1: Mirror the API shapes in TypeScript**

`frontend/src/api/types.ts`:

```typescript
export type NodeFeature = {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    id: string;
    name: string;
    type: "source" | "reservoir" | "reach" | "confluence" | "wetland"
        | "demand_municipal" | "demand_irrigation" | "sink";
    country: string;
    upstream: string[];
    downstream: string[];
  };
};
export type NodesGeoJSON = { type: "FeatureCollection"; features: NodeFeature[] };

export type Timeseries = {
  month: string[];
  values: Record<string, (number | null)[]>;
};

export type Weights = { water: number; food: number; energy: number };
export type ReservoirPolicy = {
  mode: "historical" | "rule_curve" | "manual";
  release_m3s_by_month?: Record<string, number>;
};
export type DemandPolicy = { area_scale?: number; population_scale?: number };
export type Constraints = { min_delta_flow_m3s: number };
export type Policy = {
  reservoirs: Record<string, ReservoirPolicy>;
  demands: Record<string, DemandPolicy>;
  constraints: Constraints;
  weights: Weights;
};

export type Kpi = { month: string; water_served_pct: number; food_tonnes: number; energy_gwh: number };
export type ScenarioResults = {
  timeseries_per_node: Record<string, Array<Record<string, number | string | null>>>;
  kpi_monthly: Kpi[];
  score: number | null;
  score_breakdown: Record<string, number>;
};
export type Scenario = {
  id: string;
  name: string;
  created_at: string;
  period: [string, string];
  policy: Policy;
  results?: ScenarioResults | null;
};
export type ScenarioSummary = {
  id: string; name: string; created_at: string; score: number | null;
  period: [string, string];
};
export type CompareResponse = {
  scenarios: Record<string, { name: string; score: number | null }>;
  kpi_deltas: Array<{ month: string; water_served_pct: number; food_tonnes: number; energy_gwh: number }>;
  score_delta: number;
};
```

- [ ] **Step 2: Implement the client**

`frontend/src/api/client.ts`:

```typescript
import type {
  CompareResponse, NodesGeoJSON, Scenario, ScenarioSummary, Timeseries,
} from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const api = {
  health: () => fetch(`${BASE}/health`).then(j<{ status: string }>),
  nodes: () => fetch(`${BASE}/nodes`).then(j<NodesGeoJSON>),
  nodeConfig: (id: string) => fetch(`${BASE}/nodes/${id}`).then(j<Record<string, unknown>>),
  timeseries: (id: string, opts: { start?: string; end?: string; vars?: string[] } = {}) => {
    const qs = new URLSearchParams();
    if (opts.start) qs.set("start", opts.start);
    if (opts.end) qs.set("end", opts.end);
    if (opts.vars) qs.set("vars", opts.vars.join(","));
    return fetch(`${BASE}/nodes/${id}/timeseries?${qs}`).then(j<Timeseries>);
  },
  ndvi: (zone: string, opts: { start?: string; end?: string } = {}) => {
    const qs = new URLSearchParams();
    if (opts.start) qs.set("start", opts.start);
    if (opts.end) qs.set("end", opts.end);
    return fetch(`${BASE}/overlays/ndvi/${zone}?${qs}`).then(j<Timeseries>);
  },
  runScenario: (s: Partial<Scenario>) =>
    fetch(`${BASE}/scenarios/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(s),
    }).then(j<Scenario>),
  listScenarios: () => fetch(`${BASE}/scenarios`).then(j<ScenarioSummary[]>),
  getScenario: (id: string) => fetch(`${BASE}/scenarios/${id}`).then(j<Scenario>),
  saveScenario: (id: string, s: Scenario) =>
    fetch(`${BASE}/scenarios/${id}/save`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(s),
    }).then(j<Scenario>),
  deleteScenario: (id: string) =>
    fetch(`${BASE}/scenarios/${id}`, { method: "DELETE" }).then(r => { if (!r.ok) throw new Error("del"); }),
  compare: (ids: [string, string]) =>
    fetch(`${BASE}/scenarios/compare`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario_ids: ids }),
    }).then(j<CompareResponse>),
};
```

- [ ] **Step 3: Add a smoke test (vitest + fetch mock)**

`frontend/tests/api.test.ts`:

```typescript
import { beforeEach, describe, expect, test, vi } from "vitest";
import { api } from "../src/api/client";

describe("api client", () => {
  beforeEach(() => vi.restoreAllMocks());

  test("health", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" })));
    await expect(api.health()).resolves.toEqual({ status: "ok" });
    expect(spy).toHaveBeenCalledWith(expect.stringMatching(/\/health$/));
  });

  test("timeseries builds query string", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ month: [], values: {} })));
    await api.timeseries("gerd", { start: "2020-01", end: "2020-12", vars: ["precip_mm"] });
    const url = spy.mock.calls[0][0] as string;
    expect(url).toContain("start=2020-01");
    expect(url).toContain("end=2020-12");
    expect(url).toContain("vars=precip_mm");
  });
});
```

- [ ] **Step 4: Run, commit**

```bash
cd frontend
npx vitest run
cd ..
git add frontend/src/api/ frontend/tests/api.test.ts
git commit -m "L4: API client + TS types"
```

---

## Task 3: Zustand store

**Files:**
- Create: `frontend/src/state/store.ts`
- Create: `frontend/tests/store.test.ts`

- [ ] **Step 1: Write the failing test**

`frontend/tests/store.test.ts`:

```typescript
import { describe, expect, test } from "vitest";
import { useStore } from "../src/state/store";

describe("store", () => {
  test("default weights sum to 1", () => {
    const { policy } = useStore.getState();
    const w = policy.weights;
    expect(Math.abs(w.water + w.food + w.energy - 1)).toBeLessThan(1e-6);
  });

  test("setWeight renormalizes", () => {
    useStore.getState().setWeight("water", 0.6);
    const w = useStore.getState().policy.weights;
    expect(Math.abs(w.water + w.food + w.energy - 1)).toBeLessThan(1e-6);
    expect(w.water).toBeCloseTo(0.6);
  });

  test("setReleaseMonth mutates nested release map", () => {
    useStore.getState().setReleaseMonth("gerd", "2020-01", 1500);
    expect(useStore.getState().policy.reservoirs.gerd?.release_m3s_by_month?.["2020-01"]).toBe(1500);
  });
});
```

- [ ] **Step 2: Implement `frontend/src/state/store.ts`**

```typescript
import { create } from "zustand";

import type { NodesGeoJSON, Policy, Scenario, ScenarioSummary, Timeseries } from "../api/types";

type State = {
  nodes: NodesGeoJSON | null;
  setNodes: (g: NodesGeoJSON) => void;

  policy: Policy;
  setMode: (nodeId: string, mode: "historical" | "rule_curve" | "manual") => void;
  setReleaseMonth: (nodeId: string, month: string, m3s: number) => void;
  setDemandScale: (nodeId: string, kind: "area" | "population", v: number) => void;
  setMinDeltaFlow: (v: number) => void;
  setWeight: (k: "water" | "food" | "energy", v: number) => void;

  period: [string, string];
  setPeriod: (p: [string, string]) => void;

  runningResults: Scenario | null;
  setRunningResults: (s: Scenario | null) => void;

  saved: ScenarioSummary[];
  setSaved: (s: ScenarioSummary[]) => void;

  compareMode: boolean;
  compareIds: [string | null, string | null];
  setCompareMode: (on: boolean) => void;
  setCompareId: (slot: 0 | 1, id: string | null) => void;

  overlays: { ndvi: boolean; flow: boolean };
  setOverlay: (k: "ndvi" | "flow", v: boolean) => void;

  scrubMonth: string | null;      // null → show latest month of running results
  setScrubMonth: (m: string | null) => void;

  ndviByZone: Record<string, Timeseries>;
  setNdvi: (zone: string, t: Timeseries) => void;
};

const DEFAULT_POLICY: Policy = {
  reservoirs: {},
  demands: {},
  constraints: { min_delta_flow_m3s: 500 },
  weights: { water: 0.4, food: 0.3, energy: 0.3 },
};

function renormalizeWeights(w: Policy["weights"], changed: keyof Policy["weights"], v: number) {
  const next = { ...w, [changed]: v };
  const others = (["water", "food", "energy"] as const).filter(k => k !== changed);
  const remaining = 1 - v;
  const othersTotal = others.reduce((a, k) => a + w[k], 0);
  if (othersTotal > 0) {
    for (const k of others) next[k] = (w[k] / othersTotal) * remaining;
  } else {
    for (const k of others) next[k] = remaining / others.length;
  }
  return next;
}

export const useStore = create<State>((set) => ({
  nodes: null,
  setNodes: (g) => set({ nodes: g }),

  policy: DEFAULT_POLICY,
  setMode: (nodeId, mode) =>
    set((s) => ({
      policy: {
        ...s.policy,
        reservoirs: {
          ...s.policy.reservoirs,
          [nodeId]: { ...(s.policy.reservoirs[nodeId] ?? { mode: "historical" }), mode },
        },
      },
    })),
  setReleaseMonth: (nodeId, month, m3s) =>
    set((s) => {
      const cur = s.policy.reservoirs[nodeId] ?? { mode: "manual", release_m3s_by_month: {} };
      const mapping = { ...(cur.release_m3s_by_month ?? {}), [month]: m3s };
      return {
        policy: { ...s.policy, reservoirs: { ...s.policy.reservoirs,
          [nodeId]: { ...cur, mode: "manual", release_m3s_by_month: mapping } } },
      };
    }),
  setDemandScale: (nodeId, kind, v) =>
    set((s) => {
      const cur = s.policy.demands[nodeId] ?? {};
      return {
        policy: { ...s.policy, demands: { ...s.policy.demands,
          [nodeId]: { ...cur, [kind === "area" ? "area_scale" : "population_scale"]: v } } },
      };
    }),
  setMinDeltaFlow: (v) => set((s) => ({
    policy: { ...s.policy, constraints: { ...s.policy.constraints, min_delta_flow_m3s: v } },
  })),
  setWeight: (k, v) => set((s) => ({
    policy: { ...s.policy, weights: renormalizeWeights(s.policy.weights, k, v) },
  })),

  period: ["2005-01", "2024-12"],
  setPeriod: (p) => set({ period: p }),

  runningResults: null,
  setRunningResults: (s) => set({ runningResults: s }),

  saved: [],
  setSaved: (s) => set({ saved: s }),

  compareMode: false,
  compareIds: [null, null],
  setCompareMode: (on) => set({ compareMode: on }),
  setCompareId: (slot, id) => set((s) => {
    const next = [...s.compareIds] as [string | null, string | null]; next[slot] = id;
    return { compareIds: next };
  }),

  overlays: { ndvi: false, flow: true },
  setOverlay: (k, v) => set((s) => ({ overlays: { ...s.overlays, [k]: v } })),

  scrubMonth: null,
  setScrubMonth: (m) => set({ scrubMonth: m }),

  ndviByZone: {},
  setNdvi: (zone, t) => set((s) => ({ ndviByZone: { ...s.ndviByZone, [zone]: t } })),
}));
```

- [ ] **Step 3: Run, commit**

```bash
cd frontend && npx vitest run && cd ..
git add frontend/src/state/ frontend/tests/store.test.ts
git commit -m "L4: Zustand store with weight renormalization"
```

---

## Task 4: App shell + Header

**Files:**
- Create: `frontend/src/App.tsx`, `frontend/src/components/Header.tsx`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Implement `App.tsx`**

```tsx
import { useEffect } from "react";

import { api } from "./api/client";
import { Header } from "./components/Header";
import { LeftRail } from "./components/LeftRail";
import { RightRail } from "./components/RightRail";
import { NileMap } from "./components/NileMap";
import { ScenarioTray } from "./components/ScenarioTray";
import { MonthScrubber } from "./components/MonthScrubber";
import { CompareView } from "./components/CompareView";
import { useStore } from "./state/store";

export default function App() {
  const { setNodes, setSaved, compareMode } = useStore();

  useEffect(() => {
    api.nodes().then(setNodes);
    api.listScenarios().then(setSaved);
  }, [setNodes, setSaved]);

  return (
    <div className="h-full grid grid-rows-[auto_1fr_auto] bg-slate-900 text-slate-100">
      <Header />
      {compareMode ? (
        <CompareView />
      ) : (
        <div className="grid grid-cols-[340px_1fr_320px] min-h-0">
          <LeftRail />
          <div className="relative min-h-0">
            <NileMap />
            <MonthScrubber />
          </div>
          <RightRail />
        </div>
      )}
      <ScenarioTray />
    </div>
  );
}
```

- [ ] **Step 2: Implement `Header.tsx`**

```tsx
import { useState } from "react";

import { api } from "../api/client";
import { useStore } from "../state/store";

export function Header() {
  const { policy, period, runningResults, setRunningResults, setSaved,
          compareMode, setCompareMode } = useStore();
  const [running, setRunning] = useState(false);

  async function run() {
    setRunning(true);
    try {
      const res = await api.runScenario({ name: "current", period, policy });
      setRunningResults(res);
    } finally { setRunning(false); }
  }

  async function save() {
    if (!runningResults) return;
    await api.saveScenario(runningResults.id, runningResults);
    setSaved(await api.listScenarios());
  }

  return (
    <header className="flex items-center justify-between px-4 py-2 bg-slate-800 border-b border-slate-700">
      <h1 className="font-semibold">Nile Digital Twin</h1>
      <div className="flex gap-2">
        <button disabled={running} onClick={run}
                className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50">
          {running ? "Running…" : "Run"}
        </button>
        <button disabled={!runningResults} onClick={save}
                className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50">
          Save
        </button>
        <button onClick={() => setCompareMode(!compareMode)}
                className={`px-3 py-1 rounded ${compareMode ? "bg-amber-600" : "bg-slate-600 hover:bg-slate-500"}`}>
          {compareMode ? "Exit compare" : "Compare"}
        </button>
      </div>
    </header>
  );
}
```

- [ ] **Step 3: Create placeholder stubs** for LeftRail, RightRail, NileMap, ScenarioTray, MonthScrubber, CompareView so the app compiles. Each is a trivial `function X() { return <div className="bg-slate-800 p-2 text-xs text-slate-400">{name}</div>; }` for now.

- [ ] **Step 4: Smoke test + commit**

```bash
cd frontend && npm run dev
# open http://localhost:5173 with L3 stub running at http://localhost:8000
# verify: header renders, clicking Run calls the API (Network tab shows POST /api/scenarios/run)
cd ..
git add frontend/src/App.tsx frontend/src/components/
git commit -m "L4: app shell + Header with Run/Save/Compare wiring"
```

---

## Task 5: Left rail — sliders, weights, period

**Files:**
- Create: `frontend/src/components/LeftRail.tsx`

- [ ] **Step 1: Implement**

```tsx
import { useStore } from "../state/store";

const SLIDERS: Array<{ id: string; label: string; kind: "reservoir" | "demand" | "constraint";
                       min: number; max: number; step: number; unit: string; default: number }> = [
  { id: "gerd", label: "GERD release", kind: "reservoir", min: 0, max: 4000, step: 50, unit: "m³/s", default: 1500 },
  { id: "aswan", label: "Aswan release", kind: "reservoir", min: 500, max: 5000, step: 50, unit: "m³/s", default: 2500 },
  { id: "gezira_irr", label: "Gezira irrigation", kind: "demand", min: 0, max: 2, step: 0.05, unit: "×", default: 1 },
  { id: "egypt_ag", label: "Egypt irrigation", kind: "demand", min: 0, max: 2, step: 0.05, unit: "×", default: 1 },
  { id: "min_delta", label: "Min delta flow", kind: "constraint", min: 0, max: 1500, step: 50, unit: "m³/s", default: 500 },
];

export function LeftRail() {
  const { policy, period, setPeriod, setReleaseMonth, setDemandScale, setMinDeltaFlow, setWeight } = useStore();

  return (
    <aside className="bg-slate-800 border-r border-slate-700 p-3 overflow-y-auto text-sm">
      <section className="mb-4">
        <h3 className="text-xs uppercase text-slate-400 mb-1">Period</h3>
        <div className="flex gap-2">
          <input type="month" value={period[0]} onChange={e => setPeriod([e.target.value, period[1]])}
                 className="bg-slate-700 text-slate-100 px-2 py-1 rounded flex-1" />
          <input type="month" value={period[1]} onChange={e => setPeriod([period[0], e.target.value])}
                 className="bg-slate-700 text-slate-100 px-2 py-1 rounded flex-1" />
        </div>
      </section>

      <section className="mb-4 space-y-3">
        <h3 className="text-xs uppercase text-slate-400 mb-1">Policy levers</h3>
        {SLIDERS.map(s => {
          let value: number;
          if (s.kind === "reservoir") {
            const rp = policy.reservoirs[s.id];
            const mapping = rp?.release_m3s_by_month ?? {};
            // If the user hasn't scrubbed a month, apply release to every month of the period.
            const sample = Object.values(mapping)[0];
            value = typeof sample === "number" ? sample : s.default;
          } else if (s.kind === "demand") {
            value = policy.demands[s.id]?.area_scale ?? s.default;
          } else {
            value = policy.constraints.min_delta_flow_m3s;
          }
          return (
            <label key={s.id} className="block">
              <div className="flex justify-between">
                <span>{s.label}</span>
                <span className="text-slate-400">{value.toFixed(s.step < 1 ? 2 : 0)} {s.unit}</span>
              </div>
              <input type="range" min={s.min} max={s.max} step={s.step} value={value}
                     onChange={e => {
                       const v = Number(e.target.value);
                       if (s.kind === "reservoir") {
                         // Apply uniformly across the period
                         const [start, end] = period;
                         const months = monthRange(start, end);
                         months.forEach(m => setReleaseMonth(s.id, m, v));
                       } else if (s.kind === "demand") {
                         setDemandScale(s.id, "area", v);
                       } else {
                         setMinDeltaFlow(v);
                       }
                     }} className="w-full accent-blue-500" />
            </label>
          );
        })}
      </section>

      <section>
        <h3 className="text-xs uppercase text-slate-400 mb-1">Weights (scored KPIs)</h3>
        {(["water","food","energy"] as const).map(k => (
          <label key={k} className="block text-xs mb-2">
            <div className="flex justify-between capitalize">
              <span>{k}</span>
              <span className="text-slate-400">{(policy.weights[k] * 100).toFixed(0)}%</span>
            </div>
            <input type="range" min={0} max={1} step={0.05} value={policy.weights[k]}
                   onChange={e => setWeight(k, Number(e.target.value))} className="w-full accent-emerald-500" />
          </label>
        ))}
      </section>
    </aside>
  );
}

function monthRange(start: string, end: string): string[] {
  const out: string[] = [];
  const [sy, sm] = start.split("-").map(Number);
  const [ey, em] = end.split("-").map(Number);
  let y = sy, m = sm;
  while (y < ey || (y === ey && m <= em)) {
    out.push(`${y.toString().padStart(4, "0")}-${m.toString().padStart(2, "0")}`);
    m++; if (m > 12) { m = 1; y++; }
  }
  return out;
}
```

- [ ] **Step 2: Smoke test**

Move sliders in the browser, confirm header Run posts the updated policy. DevTools Network should show `release_m3s_by_month` populated for each reservoir when the slider was moved.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LeftRail.tsx
git commit -m "L4: LeftRail — sliders + weights + period"
```

---

## Task 6: Right rail — KPI panels

**Files:**
- Create: `frontend/src/components/RightRail.tsx`, `frontend/src/lib/kpiChart.tsx`

- [ ] **Step 1: Implement KPI chart wrapper**

`frontend/src/lib/kpiChart.tsx`:

```tsx
import Plot from "react-plotly.js";

export function KpiChart({ x, y, color, unit }: { x: string[]; y: number[]; color: string; unit: string }) {
  return (
    <Plot
      data={[{ x, y, type: "scatter", mode: "lines", line: { color, width: 2 } }]}
      layout={{
        autosize: true, height: 100,
        margin: { l: 30, r: 8, t: 8, b: 24 },
        xaxis: { showgrid: false, tickfont: { size: 9, color: "#94a3b8" } },
        yaxis: { title: { text: unit, font: { size: 9, color: "#94a3b8" } },
                 tickfont: { size: 9, color: "#94a3b8" } },
        paper_bgcolor: "transparent", plot_bgcolor: "transparent",
      }}
      config={{ displayModeBar: false }}
      style={{ width: "100%" }}
    />
  );
}
```

- [ ] **Step 2: Implement RightRail**

```tsx
import { useStore } from "../state/store";
import { KpiChart } from "../lib/kpiChart";

export function RightRail() {
  const r = useStore(s => s.runningResults);

  if (!r?.results) {
    return <aside className="bg-slate-800 border-l border-slate-700 p-3 text-sm text-slate-400">
      Run a scenario to see KPIs.
    </aside>;
  }

  const months = r.results.kpi_monthly.map(k => k.month);
  const water = r.results.kpi_monthly.map(k => k.water_served_pct * 100);
  const food = r.results.kpi_monthly.map(k => k.food_tonnes / 1e6);  // Mt
  const energy = r.results.kpi_monthly.map(k => k.energy_gwh / 1000); // TWh
  const avg = (a: number[]) => a.reduce((x, y) => x + y, 0) / (a.length || 1);

  return (
    <aside className="bg-slate-800 border-l border-slate-700 p-3 overflow-y-auto text-sm">
      <section className="mb-4">
        <h3 className="text-xs uppercase text-slate-400">Drinking water</h3>
        <div className="text-xl font-semibold">{avg(water).toFixed(1)}% served</div>
        <KpiChart x={months} y={water} color="#3b82f6" unit="%" />
      </section>
      <section className="mb-4">
        <h3 className="text-xs uppercase text-slate-400">Food</h3>
        <div className="text-xl font-semibold">{avg(food).toFixed(1)} Mt/month</div>
        <KpiChart x={months} y={food} color="#f59e0b" unit="Mt" />
      </section>
      <section className="mb-4">
        <h3 className="text-xs uppercase text-slate-400">Energy</h3>
        <div className="text-xl font-semibold">{avg(energy).toFixed(2)} TWh/month</div>
        <KpiChart x={months} y={energy} color="#10b981" unit="TWh" />
      </section>
      <section className="pt-2 border-t border-slate-700">
        <h3 className="text-xs uppercase text-slate-400">Score</h3>
        <div className="text-3xl font-semibold">{(r.results.score! * 100).toFixed(0)}</div>
        <ul className="text-xs text-slate-400 mt-1 space-y-0.5">
          {Object.entries(r.results.score_breakdown).map(([k, v]) => (
            <li key={k} className="flex justify-between">
              <span className="capitalize">{k}</span>
              <span>{(v * 100).toFixed(0)}</span>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
```

- [ ] **Step 3: Smoke test + commit**

Run scenario in the browser. Watch the three sparklines populate.

```bash
git add frontend/src/components/RightRail.tsx frontend/src/lib/kpiChart.tsx
git commit -m "L4: RightRail — KPI panels + score"
```

---

## Task 7: Map — basemap + node layer

**Files:**
- Create: `frontend/src/components/NileMap.tsx`, `frontend/public/nile-style.json`

- [ ] **Step 1: Basemap style**

`frontend/public/nile-style.json` (raster OSM — free, no token):

```json
{
  "version": 8,
  "sources": {
    "osm": {
      "type": "raster",
      "tiles": ["https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"],
      "tileSize": 256,
      "attribution": "© OpenStreetMap contributors"
    }
  },
  "layers": [{ "id": "osm", "type": "raster", "source": "osm" }]
}
```

- [ ] **Step 2: Implement NileMap**

```tsx
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { useStore } from "../state/store";

export function NileMap() {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const { nodes, runningResults } = useStore();

  useEffect(() => {
    if (!ref.current) return;
    const map = new maplibregl.Map({
      container: ref.current,
      style: "/nile-style.json",
      center: [32, 15],
      zoom: 3.6,
    });
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // Load / refresh node layer whenever nodes or results change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !nodes) return;
    const addLayers = () => {
      const enriched = enrichNodesWithResults(nodes, runningResults);
      if (map.getSource("nodes")) (map.getSource("nodes") as maplibregl.GeoJSONSource).setData(enriched);
      else {
        map.addSource("nodes", { type: "geojson", data: enriched });
        map.addLayer({
          id: "node-circle", type: "circle", source: "nodes",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["get", "radius_px"], 0, 3, 30, 22],
            "circle-color":
              ["case",
                ["==", ["get", "type"], "reservoir"], "#60a5fa",
                ["==", ["get", "type"], "wetland"], "#10b981",
                ["==", ["get", "type"], "demand_irrigation"], "#f59e0b",
                ["==", ["get", "type"], "demand_municipal"], "#fb923c",
                ["==", ["get", "type"], "sink"], "#6366f1",
                "#3b82f6"],
            "circle-stroke-color": "#0b1220", "circle-stroke-width": 1.5,
          },
        });
        map.addLayer({
          id: "node-label", type: "symbol", source: "nodes",
          layout: { "text-field": ["get", "name"], "text-offset": [0, 1.2], "text-size": 11 },
          paint: { "text-color": "#e5e7eb", "text-halo-color": "#0b1220", "text-halo-width": 1 },
        });
      }
    };
    if (map.isStyleLoaded()) addLayers();
    else map.once("load", addLayers);
  }, [nodes, runningResults]);

  return <div ref={ref} className="absolute inset-0" />;
}

function enrichNodesWithResults(nodes: GeoJSON.FeatureCollection, r: any) {
  const copy = structuredClone(nodes) as GeoJSON.FeatureCollection;
  copy.features.forEach((f: any) => {
    f.properties.radius_px = 10;
    if (r?.results) {
      const ts = r.results.timeseries_per_node?.[f.properties.id];
      if (ts?.length) {
        const last = ts[ts.length - 1];
        if ("storage_mcm" in last) f.properties.radius_px = Math.sqrt((last.storage_mcm as number) / 1000) + 4;
        else if ("outflow_m3s" in last) f.properties.radius_px = Math.sqrt((last.outflow_m3s as number) / 10) + 3;
      }
    }
  });
  return copy;
}
```

- [ ] **Step 3: Smoke test**

Browser → see Nile nodes over OSM basemap; sizes reflect running results when a scenario has been run.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/NileMap.tsx frontend/public/nile-style.json
git commit -m "L4: MapLibre basemap + node layer with result-driven sizing"
```

---

## Task 8: Node inspector popover

**Files:**
- Create: `frontend/src/components/NodeInspector.tsx`
- Modify: `frontend/src/components/NileMap.tsx` (wire `click` handler)

- [ ] **Step 1: Implement NodeInspector**

```tsx
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { Timeseries } from "../api/types";
import { KpiChart } from "../lib/kpiChart";

export function NodeInspector({ nodeId, onClose }: { nodeId: string; onClose: () => void }) {
  const [cfg, setCfg] = useState<Record<string, unknown> | null>(null);
  const [ts, setTs] = useState<Timeseries | null>(null);
  useEffect(() => {
    api.nodeConfig(nodeId).then(setCfg);
    api.timeseries(nodeId, { vars: ["precip_mm", "pet_mm", "runoff_mm"] }).then(setTs).catch(() => setTs(null));
  }, [nodeId]);
  return (
    <div className="absolute right-3 top-3 w-72 bg-slate-800 border border-slate-700 rounded p-3 shadow-xl text-sm z-10">
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-semibold">{cfg?.id ?? nodeId}</h3>
        <button onClick={onClose} className="text-slate-400 hover:text-white">×</button>
      </div>
      {cfg && (
        <pre className="text-xs bg-slate-900 p-2 rounded max-h-32 overflow-auto">
{JSON.stringify(cfg, null, 2)}
        </pre>
      )}
      {ts && (
        <>
          <h4 className="text-xs uppercase text-slate-400 mt-2">Precip (mm)</h4>
          <KpiChart x={ts.month} y={(ts.values.precip_mm ?? []).map(v => v ?? 0)} color="#3b82f6" unit="mm" />
          <h4 className="text-xs uppercase text-slate-400 mt-2">PET (mm)</h4>
          <KpiChart x={ts.month} y={(ts.values.pet_mm ?? []).map(v => v ?? 0)} color="#f59e0b" unit="mm" />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire from NileMap**

In `NileMap.tsx`, add local state for `selectedId` and render `<NodeInspector nodeId={selectedId} onClose={...} />` when set. In the `load` handler, add:

```typescript
map.on("click", "node-circle", (e) => {
  const id = (e.features?.[0]?.properties as any)?.id;
  if (id) setSelectedId(id as string);
});
map.on("mouseenter", "node-circle", () => map.getCanvas().style.cursor = "pointer");
map.on("mouseleave", "node-circle", () => map.getCanvas().style.cursor = "");
```

- [ ] **Step 3: Smoke test + commit**

Click a node, see the inspector with config + timeseries charts.

```bash
git add frontend/src/components/NodeInspector.tsx frontend/src/components/NileMap.tsx
git commit -m "L4: node click → inspector popover with config + forcings"
```

---

## Task 9: Scenario tray

**Files:**
- Create: `frontend/src/components/ScenarioTray.tsx`

- [ ] **Step 1: Implement**

```tsx
import { useState } from "react";

import { api } from "../api/client";
import { useStore } from "../state/store";

export function ScenarioTray() {
  const { saved, setSaved, setRunningResults, setCompareId, compareMode, compareIds } = useStore();
  const [open, setOpen] = useState(true);

  async function load(id: string) {
    const s = await api.getScenario(id);
    setRunningResults(s);
  }
  async function remove(id: string) {
    await api.deleteScenario(id);
    setSaved(await api.listScenarios());
  }

  return (
    <footer className="bg-slate-800 border-t border-slate-700">
      <button onClick={() => setOpen(!open)}
              className="w-full text-left px-3 py-1 text-xs uppercase tracking-wide text-slate-400 hover:text-white">
        {open ? "▼" : "▲"} Saved scenarios ({saved.length})
      </button>
      {open && (
        <div className="flex gap-2 px-3 pb-2 overflow-x-auto">
          {saved.length === 0 && <div className="text-xs text-slate-500 py-2">Run → Save to keep a scenario here.</div>}
          {saved.map(s => (
            <div key={s.id} className="bg-slate-900 rounded px-2 py-1 text-xs min-w-[180px] flex flex-col">
              <div className="flex justify-between">
                <strong className="truncate" title={s.name}>{s.name}</strong>
                <button onClick={() => remove(s.id)} className="text-slate-500 hover:text-red-400">×</button>
              </div>
              <div className="text-slate-400">Score {s.score != null ? (s.score * 100).toFixed(0) : "–"}</div>
              <div className="flex gap-1 mt-1">
                <button onClick={() => load(s.id)} className="flex-1 bg-slate-700 rounded px-1 hover:bg-slate-600">
                  Load
                </button>
                {compareMode && (
                  <>
                    <button onClick={() => setCompareId(0, s.id)}
                            className={`px-1 rounded ${compareIds[0] === s.id ? "bg-amber-600" : "bg-slate-700 hover:bg-slate-600"}`}>A</button>
                    <button onClick={() => setCompareId(1, s.id)}
                            className={`px-1 rounded ${compareIds[1] === s.id ? "bg-amber-600" : "bg-slate-700 hover:bg-slate-600"}`}>B</button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </footer>
  );
}
```

- [ ] **Step 2: Smoke test + commit**

Run → Save → scenario appears in tray. Click Load. Delete with ×.

```bash
git add frontend/src/components/ScenarioTray.tsx
git commit -m "L4: scenario tray (load/delete + compare A/B pick)"
```

---

## Task 10: Compare view

**Files:**
- Create: `frontend/src/components/CompareView.tsx`

- [ ] **Step 1: Implement**

```tsx
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { CompareResponse } from "../api/types";
import { useStore } from "../state/store";

export function CompareView() {
  const { compareIds } = useStore();
  const [data, setData] = useState<CompareResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!compareIds[0] || !compareIds[1]) { setData(null); return; }
    api.compare(compareIds as [string, string]).then(setData).catch(e => setErr(String(e)));
  }, [compareIds]);

  if (!compareIds[0] || !compareIds[1]) {
    return <div className="p-8 text-slate-400">Pick two saved scenarios (A / B) in the tray to compare.</div>;
  }
  if (err) return <div className="p-8 text-red-400">{err}</div>;
  if (!data) return <div className="p-8 text-slate-400">Loading…</div>;

  const avg = (k: keyof CompareResponse["kpi_deltas"][number]) =>
    data.kpi_deltas.reduce((a, r) => a + (r[k] as number), 0) / data.kpi_deltas.length;

  const entries = Object.entries(data.scenarios);
  return (
    <div className="grid grid-cols-2 h-full">
      {entries.map(([id, s]) => (
        <div key={id} className="border-r border-slate-700 p-4">
          <h3 className="font-semibold">{s.name}</h3>
          <div className="text-slate-400 text-sm">Score {s.score != null ? (s.score * 100).toFixed(0) : "–"}</div>
        </div>
      ))}
      <div className="col-span-2 p-4 bg-slate-900 border-t border-slate-700">
        <h4 className="text-xs uppercase text-slate-400 mb-2">Deltas (B − A)</h4>
        <div className="grid grid-cols-4 gap-3 text-sm">
          <Delta label="Score" v={data.score_delta * 100} suffix="pt" />
          <Delta label="Water served" v={avg("water_served_pct") * 100} suffix="pp" />
          <Delta label="Food" v={avg("food_tonnes") / 1e6} suffix="Mt/mo" />
          <Delta label="Energy" v={avg("energy_gwh") / 1000} suffix="TWh/mo" />
        </div>
      </div>
    </div>
  );
}

function Delta({ label, v, suffix }: { label: string; v: number; suffix: string }) {
  const color = v > 0 ? "text-emerald-400" : v < 0 ? "text-red-400" : "text-slate-300";
  return (
    <div>
      <div className="text-slate-400 text-xs">{label}</div>
      <div className={`text-lg font-semibold ${color}`}>{v > 0 ? "+" : ""}{v.toFixed(2)} {suffix}</div>
    </div>
  );
}
```

- [ ] **Step 2: Smoke test + commit**

Compare mode → pick A and B in the tray → deltas render.

```bash
git add frontend/src/components/CompareView.tsx
git commit -m "L4: CompareView with delta KPIs"
```

---

## Task 11: Month scrubber + NDVI overlay

**Files:**
- Create: `frontend/src/components/MonthScrubber.tsx`, `frontend/src/lib/ndvi.ts`
- Modify: `frontend/src/components/NileMap.tsx`

- [ ] **Step 1: Scrubber**

```tsx
import { useStore } from "../state/store";

export function MonthScrubber() {
  const { runningResults, scrubMonth, setScrubMonth, overlays, setOverlay } = useStore();
  const months = runningResults?.results?.kpi_monthly.map(k => k.month) ?? [];
  if (months.length === 0) return null;
  const idx = scrubMonth ? months.indexOf(scrubMonth) : months.length - 1;
  return (
    <div className="absolute bottom-2 left-2 right-2 bg-slate-900/90 border border-slate-700 rounded px-3 py-2 flex items-center gap-3 backdrop-blur">
      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={overlays.ndvi} onChange={e => setOverlay("ndvi", e.target.checked)} />
        NDVI
      </label>
      <input type="range" min={0} max={months.length - 1} value={idx}
             onChange={e => setScrubMonth(months[Number(e.target.value)])}
             className="flex-1 accent-blue-500" />
      <span className="text-xs text-slate-300 w-16 text-right">{months[idx]}</span>
    </div>
  );
}
```

- [ ] **Step 2: NDVI overlay builder**

`frontend/src/lib/ndvi.ts`:

```typescript
import type maplibregl from "maplibre-gl";

const TILE_BASE = import.meta.env.VITE_TILE_BASE ?? "/tiles";

const ZONES: Array<{ id: string; bbox: [number, number, number, number] }> = [
  { id: "gezira", bbox: [32.5, 13.5, 33.6, 14.8] },
  { id: "egypt_delta", bbox: [30.0, 30.0, 32.2, 31.5] },
];

export function setNdviOverlay(map: maplibregl.Map, month: string | null, visible: boolean) {
  for (const z of ZONES) {
    const sid = `ndvi-${z.id}`, lid = `ndvi-layer-${z.id}`;
    if (!visible || !month) {
      if (map.getLayer(lid)) map.removeLayer(lid);
      if (map.getSource(sid)) map.removeSource(sid);
      continue;
    }
    const url = `${TILE_BASE}/ndvi/${z.id}/${month}/{z}/{x}/{y}.png`;
    const src = map.getSource(sid) as maplibregl.RasterTileSource | undefined;
    if (!src) {
      map.addSource(sid, { type: "raster", tiles: [url], tileSize: 256, bounds: z.bbox });
      map.addLayer({ id: lid, type: "raster", source: sid, paint: { "raster-opacity": 0.6 } });
    } else {
      src.setTiles([url]);
    }
  }
}
```

- [ ] **Step 3: Wire in NileMap**

In `NileMap.tsx`, add a `useEffect` that depends on `overlays.ndvi` and `scrubMonth`:

```typescript
useEffect(() => {
  const map = mapRef.current; if (!map) return;
  const apply = () => setNdviOverlay(map, scrubMonth ?? lastMonth(runningResults), overlays.ndvi);
  if (map.isStyleLoaded()) apply(); else map.once("load", apply);
}, [overlays.ndvi, scrubMonth, runningResults]);
```

Add:
```typescript
function lastMonth(r: any) { return r?.results?.kpi_monthly?.slice(-1)[0]?.month ?? null; }
```

- [ ] **Step 4: Smoke test + commit**

After running a scenario, toggle NDVI — tile URLs appear in Network tab. Scrub the month — tile URLs update.

```bash
git add frontend/src/components/MonthScrubber.tsx frontend/src/lib/ndvi.ts frontend/src/components/NileMap.tsx
git commit -m "L4: MonthScrubber + NDVI raster overlay"
```

---

## Task 12: Frontend Dockerfile

**Files:**
- Create: `frontend/Dockerfile.frontend`, `frontend/nginx.conf`

- [ ] **Step 1: Dockerfile (multi-stage)**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.25-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

- [ ] **Step 2: Nginx config (proxies /api and /tiles to the API service)**

`frontend/nginx.conf`:

```nginx
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;

  location /api/ {
    proxy_pass http://api:8000/;
    proxy_set_header Host $host;
  }
  location /tiles/ {
    proxy_pass http://api:8000/tiles/;
  }
  location / {
    try_files $uri /index.html;
  }
}
```

**Note:** the API needs to also serve `/tiles/ndvi/...` from `data/tiles/`. Add to `api/app.py`:

```python
from fastapi.staticfiles import StaticFiles

# after create_app() body:
    tiles_dir = DATA_DIR / "tiles"
    if tiles_dir.exists():
        app.mount("/tiles", StaticFiles(directory=str(tiles_dir)), name="tiles")
```

- [ ] **Step 3: Build + smoke test**

```bash
cd ..
docker compose build frontend
docker compose up -d
sleep 3
curl -s -I http://localhost:5173
docker compose down
```

Expected: 200 OK.

- [ ] **Step 4: Commit**

```bash
git add frontend/Dockerfile.frontend frontend/nginx.conf api/app.py
git commit -m "L4: frontend Dockerfile + API mounts /tiles"
```

---

## Task 13: Demo smoke checklist (Sun 15:00)

Not code — a rehearsal script. Execute before judging.

- [ ] **Step 1: Fresh boot**

```bash
docker compose down && docker compose up --build -d
sleep 5
open http://localhost:5173
```

- [ ] **Step 2: Run through the happy path**

| Action | Expected |
|---|---|
| Page loads | Header, map with ~18 node dots, empty right rail ("Run a scenario to see KPIs") |
| Click **Run** | Button says "Running…", comes back with 3 KPI sparklines + score |
| Click a node on the map | Inspector popover opens with config + forcings charts |
| Move GERD release slider to 500 m³/s | No change (run is stale) |
| Click Run | KPIs update; energy probably drops, delta flow warning |
| Click Save | Scenario appears in bottom tray |
| Slide GERD back to 2500, click Run, Save as "fast-fill" | Two scenarios in tray |
| Click Compare in header | Compare mode UI |
| Pick A and B from the tray | Delta view renders |
| Exit compare → toggle NDVI on scrubber | Raster overlay appears on Gezira & Delta |
| Scrub month back to 2005-07 | NDVI tiles update |

- [ ] **Step 3: Record any issues → fix until clean.**

---

## L4 Success Criteria

1. `npm run dev` + L3 stub API → full UI works against final JSON contracts.
2. `docker compose up` → http://localhost:5173 serves the built app, talks to the API, renders all panels.
3. 12-step smoke checklist in Task 13 runs end-to-end without a page reload or console error.
4. `npx vitest run` green (handful of API-client + store tests).

## Explicit non-goals for L4

- No SSR, no auth, no accessibility beyond basic keyboard nav.
- No E2E (Playwright); the manual checklist is the E2E.
- No 3D visualization; no animated flow particles (can add in polish if time).
- No per-reservoir release curve editor (slider applies uniformly across the period — this is a known simplification, okay for the pitch).
- No mobile layout.
- No responsive breakpoints below 1280 px.
