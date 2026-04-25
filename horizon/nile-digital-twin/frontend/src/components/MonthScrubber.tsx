import { useStore } from "../state/store";

export function MonthScrubber() {
  const { runningResults, scrubMonth, setScrubMonth, overlays, setOverlay } = useStore();
  const months = runningResults?.results?.kpi_monthly.map((k) => k.month) ?? [];
  if (months.length === 0) return null;
  const idx = scrubMonth ? months.indexOf(scrubMonth) : months.length - 1;

  return (
    <div className="absolute bottom-2 left-2 right-2 bg-slate-900/90 border border-slate-700 rounded px-3 py-2 flex items-center gap-3 backdrop-blur text-slate-100">
      <label className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          checked={overlays.ndvi}
          onChange={(e) => setOverlay("ndvi", e.target.checked)}
        />
        NDVI
      </label>
      <input
        type="range" min={0} max={months.length - 1} value={idx >= 0 ? idx : 0}
        onChange={(e) => setScrubMonth(months[Number(e.target.value)])}
        className="flex-1 accent-blue-500"
      />
      <span className="text-xs text-slate-300 w-16 text-right">{months[idx]}</span>
    </div>
  );
}
