import { monthRange, useStore } from "../state/store";

type SliderSpec = {
  id: string;
  label: string;
  kind: "reservoir" | "demand" | "constraint";
  min: number;
  max: number;
  step: number;
  unit: string;
  default: number;
};

const SLIDERS: SliderSpec[] = [
  { id: "gerd", label: "GERD release", kind: "reservoir", min: 0, max: 4000, step: 50, unit: "m³/s", default: 1500 },
  { id: "aswan", label: "Aswan release", kind: "reservoir", min: 500, max: 5000, step: 50, unit: "m³/s", default: 2500 },
  { id: "gezira_irr", label: "Gezira irrigation", kind: "demand", min: 0, max: 2, step: 0.05, unit: "×", default: 1 },
  { id: "egypt_ag", label: "Egypt irrigation", kind: "demand", min: 0, max: 2, step: 0.05, unit: "×", default: 1 },
  { id: "min_delta", label: "Min delta flow", kind: "constraint", min: 0, max: 1500, step: 50, unit: "m³/s", default: 500 },
];

export function LeftRail() {
  const {
    policy, period, setPeriod, setReleaseAllMonths, setDemandScale,
    setMinDeltaFlow, setWeight,
  } = useStore();

  return (
    <aside className="bg-slate-800 border-r border-slate-700 p-3 overflow-y-auto text-sm">
      <section className="mb-4">
        <h3 className="text-xs uppercase text-slate-400 mb-1">Period</h3>
        <div className="flex gap-2">
          <input
            type="month" value={period[0]}
            onChange={(e) => setPeriod([e.target.value, period[1]])}
            className="bg-slate-700 text-slate-100 px-2 py-1 rounded flex-1"
          />
          <input
            type="month" value={period[1]}
            onChange={(e) => setPeriod([period[0], e.target.value])}
            className="bg-slate-700 text-slate-100 px-2 py-1 rounded flex-1"
          />
        </div>
      </section>

      <section className="mb-4 space-y-3">
        <h3 className="text-xs uppercase text-slate-400 mb-1">Policy levers</h3>
        {SLIDERS.map((s) => {
          let value: number;
          if (s.kind === "reservoir") {
            const rp = policy.reservoirs[s.id];
            const mapping = rp?.release_m3s_by_month ?? {};
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
                <span className="text-slate-400">
                  {value.toFixed(s.step < 1 ? 2 : 0)} {s.unit}
                </span>
              </div>
              <input
                type="range" min={s.min} max={s.max} step={s.step} value={value}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (s.kind === "reservoir") {
                    setReleaseAllMonths(s.id, monthRange(period[0], period[1]), v);
                  } else if (s.kind === "demand") {
                    setDemandScale(s.id, "area", v);
                  } else {
                    setMinDeltaFlow(v);
                  }
                }}
                className="w-full accent-blue-500"
              />
            </label>
          );
        })}
      </section>

      <section>
        <h3 className="text-xs uppercase text-slate-400 mb-1">Weights (scored KPIs)</h3>
        {(["water", "food", "energy"] as const).map((k) => (
          <label key={k} className="block text-xs mb-2">
            <div className="flex justify-between capitalize">
              <span>{k}</span>
              <span className="text-slate-400">
                {(policy.weights[k] * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range" min={0} max={1} step={0.05} value={policy.weights[k]}
              onChange={(e) => setWeight(k, Number(e.target.value))}
              className="w-full accent-emerald-500"
            />
          </label>
        ))}
      </section>
    </aside>
  );
}
