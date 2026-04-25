import { KpiChart } from "../lib/kpiChart";
import { useStore } from "../state/store";

export function RightRail() {
  const r = useStore((s) => s.runningResults);

  if (!r?.results) {
    return (
      <aside className="bg-slate-800 border-l border-slate-700 p-3 text-sm text-slate-400">
        Run a scenario to see KPIs.
      </aside>
    );
  }

  const months = r.results.kpi_monthly.map((k) => k.month);
  const water = r.results.kpi_monthly.map((k) => k.water_served_pct * 100);
  const food = r.results.kpi_monthly.map((k) => k.food_tonnes / 1e6); // Mt
  const energy = r.results.kpi_monthly.map((k) => k.energy_gwh / 1000); // TWh
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
        <div className="text-3xl font-semibold">
          {r.results.score != null ? (r.results.score * 100).toFixed(0) : "—"}
        </div>
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
