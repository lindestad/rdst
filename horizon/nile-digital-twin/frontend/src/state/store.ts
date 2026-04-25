import { create } from "zustand";

import type {
  NodesGeoJSON, Policy, Scenario, ScenarioSummary, Timeseries,
} from "../api/types";

type State = {
  nodes: NodesGeoJSON | null;
  setNodes: (g: NodesGeoJSON) => void;

  policy: Policy;
  setMode: (nodeId: string, mode: "historical" | "rule_curve" | "manual") => void;
  setReleaseMonth: (nodeId: string, month: string, m3s: number) => void;
  setReleaseAllMonths: (nodeId: string, months: string[], m3s: number) => void;
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

  scrubMonth: string | null;
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

function renormalizeWeights(
  w: Policy["weights"],
  changed: keyof Policy["weights"],
  v: number,
) {
  const next = { ...w, [changed]: v };
  const others = (["water", "food", "energy"] as const).filter((k) => k !== changed);
  const remaining = Math.max(0, 1 - v);
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
      const cur = s.policy.reservoirs[nodeId] ?? {
        mode: "manual" as const, release_m3s_by_month: {},
      };
      const mapping = { ...(cur.release_m3s_by_month ?? {}), [month]: m3s };
      return {
        policy: {
          ...s.policy,
          reservoirs: {
            ...s.policy.reservoirs,
            [nodeId]: { ...cur, mode: "manual", release_m3s_by_month: mapping },
          },
        },
      };
    }),
  setReleaseAllMonths: (nodeId, months, m3s) =>
    set((s) => {
      const cur = s.policy.reservoirs[nodeId] ?? {
        mode: "manual" as const, release_m3s_by_month: {},
      };
      const mapping = { ...(cur.release_m3s_by_month ?? {}) };
      for (const m of months) mapping[m] = m3s;
      return {
        policy: {
          ...s.policy,
          reservoirs: {
            ...s.policy.reservoirs,
            [nodeId]: { ...cur, mode: "manual", release_m3s_by_month: mapping },
          },
        },
      };
    }),
  setDemandScale: (nodeId, kind, v) =>
    set((s) => {
      const cur = s.policy.demands[nodeId] ?? {};
      return {
        policy: {
          ...s.policy,
          demands: {
            ...s.policy.demands,
            [nodeId]: {
              ...cur,
              [kind === "area" ? "area_scale" : "population_scale"]: v,
            },
          },
        },
      };
    }),
  setMinDeltaFlow: (v) =>
    set((s) => ({
      policy: {
        ...s.policy,
        constraints: { ...s.policy.constraints, min_delta_flow_m3s: v },
      },
    })),
  setWeight: (k, v) =>
    set((s) => ({
      policy: { ...s.policy, weights: renormalizeWeights(s.policy.weights, k, v) },
    })),

  period: ["2005-01", "2024-12"],
  setPeriod: (p) => set({ period: p }),

  runningResults: null,
  setRunningResults: (r) => set({ runningResults: r }),

  saved: [],
  setSaved: (s) => set({ saved: s }),

  compareMode: false,
  compareIds: [null, null],
  setCompareMode: (on) => set({ compareMode: on }),
  setCompareId: (slot, id) =>
    set((s) => {
      const next = [...s.compareIds] as [string | null, string | null];
      next[slot] = id;
      return { compareIds: next };
    }),

  overlays: { ndvi: false, flow: true },
  setOverlay: (k, v) => set((s) => ({ overlays: { ...s.overlays, [k]: v } })),

  scrubMonth: null,
  setScrubMonth: (m) => set({ scrubMonth: m }),

  ndviByZone: {},
  setNdvi: (zone, t) =>
    set((s) => ({ ndviByZone: { ...s.ndviByZone, [zone]: t } })),
}));

export function monthRange(start: string, end: string): string[] {
  const out: string[] = [];
  const [sy, sm] = start.split("-").map(Number);
  const [ey, em] = end.split("-").map(Number);
  let y = sy, m = sm;
  while (y < ey || (y === ey && m <= em)) {
    out.push(`${y.toString().padStart(4, "0")}-${m.toString().padStart(2, "0")}`);
    m++;
    if (m > 12) { m = 1; y++; }
  }
  return out;
}
