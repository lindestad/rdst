import type {
  CompareResponse, NodesGeoJSON, Scenario, ScenarioSummary, Timeseries,
} from "./types";

const BASE = (import.meta as any).env?.VITE_API_BASE ?? "/api";

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return (await r.json()) as T;
}

export const api = {
  health: () => fetch(`${BASE}/health`).then((r) => j<{ status: string }>(r)),
  nodes: () => fetch(`${BASE}/nodes`).then((r) => j<NodesGeoJSON>(r)),
  nodeConfig: (id: string) =>
    fetch(`${BASE}/nodes/${id}`).then((r) => j<Record<string, unknown>>(r)),
  timeseries: (
    id: string,
    opts: { start?: string; end?: string; vars?: string[] } = {},
  ) => {
    const qs = new URLSearchParams();
    if (opts.start) qs.set("start", opts.start);
    if (opts.end) qs.set("end", opts.end);
    if (opts.vars) qs.set("vars", opts.vars.join(","));
    return fetch(`${BASE}/nodes/${id}/timeseries?${qs}`).then((r) => j<Timeseries>(r));
  },
  ndvi: (zone: string, opts: { start?: string; end?: string } = {}) => {
    const qs = new URLSearchParams();
    if (opts.start) qs.set("start", opts.start);
    if (opts.end) qs.set("end", opts.end);
    return fetch(`${BASE}/overlays/ndvi/${zone}?${qs}`).then((r) => j<Timeseries>(r));
  },
  runScenario: (s: Partial<Scenario>) =>
    fetch(`${BASE}/scenarios/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(s),
    }).then((r) => j<Scenario>(r)),
  listScenarios: () => fetch(`${BASE}/scenarios`).then((r) => j<ScenarioSummary[]>(r)),
  getScenario: (id: string) => fetch(`${BASE}/scenarios/${id}`).then((r) => j<Scenario>(r)),
  saveScenario: (id: string, s: Scenario) =>
    fetch(`${BASE}/scenarios/${id}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(s),
    }).then((r) => j<Scenario>(r)),
  deleteScenario: (id: string) =>
    fetch(`${BASE}/scenarios/${id}`, { method: "DELETE" }).then((r) => {
      if (!r.ok) throw new Error("delete failed");
    }),
  compare: (ids: [string, string]) =>
    fetch(`${BASE}/scenarios/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario_ids: ids }),
    }).then((r) => j<CompareResponse>(r)),
};
