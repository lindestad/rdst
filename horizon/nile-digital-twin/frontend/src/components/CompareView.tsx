import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { CompareResponse } from "../api/types";
import { useStore } from "../state/store";

export function CompareView() {
  const { compareIds } = useStore();
  const [data, setData] = useState<CompareResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setErr(null);
    if (!compareIds[0] || !compareIds[1]) {
      setData(null);
      return;
    }
    api.compare(compareIds as [string, string]).then(setData).catch((e) => setErr(String(e)));
  }, [compareIds]);

  if (!compareIds[0] || !compareIds[1]) {
    return (
      <div className="p-8 text-slate-400">
        Pick two saved scenarios (A / B) in the tray to compare.
      </div>
    );
  }
  if (err) return <div className="p-8 text-red-400">{err}</div>;
  if (!data) return <div className="p-8 text-slate-400">Loading…</div>;

  const avg = (k: "water_served_pct" | "food_tonnes" | "energy_gwh") =>
    data.kpi_deltas.reduce((a, r) => a + r[k], 0) / (data.kpi_deltas.length || 1);

  const entries = Object.entries(data.scenarios);
  return (
    <div className="grid grid-rows-[1fr_auto] h-full">
      <div className="grid grid-cols-2 min-h-0">
        {entries.map(([id, s]) => (
          <div key={id} className="border-r border-slate-700 p-4 last:border-r-0">
            <h3 className="font-semibold">{s.name}</h3>
            <div className="text-slate-400 text-sm">
              Score {s.score != null ? (s.score * 100).toFixed(0) : "–"}
            </div>
          </div>
        ))}
      </div>
      <div className="p-4 bg-slate-900 border-t border-slate-700">
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

function Delta({
  label, v, suffix,
}: { label: string; v: number; suffix: string }) {
  const color = v > 0 ? "text-emerald-400" : v < 0 ? "text-red-400" : "text-slate-300";
  return (
    <div>
      <div className="text-slate-400 text-xs">{label}</div>
      <div className={`text-lg font-semibold ${color}`}>
        {v > 0 ? "+" : ""}{v.toFixed(2)} {suffix}
      </div>
    </div>
  );
}
