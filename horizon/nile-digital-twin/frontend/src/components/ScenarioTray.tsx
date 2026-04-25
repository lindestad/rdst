import { useState } from "react";

import { api } from "../api/client";
import { useStore } from "../state/store";

export function ScenarioTray() {
  const {
    saved, setSaved, setRunningResults, setCompareId, compareMode, compareIds,
  } = useStore();
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
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left px-3 py-1 text-xs uppercase tracking-wide text-slate-400 hover:text-white"
      >
        {open ? "▼" : "▲"} Saved scenarios ({saved.length})
      </button>
      {open && (
        <div className="flex gap-2 px-3 pb-2 overflow-x-auto">
          {saved.length === 0 && (
            <div className="text-xs text-slate-500 py-2">
              Run → Save to keep a scenario here.
            </div>
          )}
          {saved.map((s) => (
            <div
              key={s.id}
              className="bg-slate-900 rounded px-2 py-1 text-xs min-w-[180px] flex flex-col"
            >
              <div className="flex justify-between">
                <strong className="truncate" title={s.name}>{s.name}</strong>
                <button
                  onClick={() => remove(s.id)}
                  className="text-slate-500 hover:text-red-400"
                >×</button>
              </div>
              <div className="text-slate-400">
                Score {s.score != null ? (s.score * 100).toFixed(0) : "–"}
              </div>
              <div className="flex gap-1 mt-1">
                <button
                  onClick={() => load(s.id)}
                  className="flex-1 bg-slate-700 rounded px-1 hover:bg-slate-600"
                >Load</button>
                {compareMode && (
                  <>
                    <button
                      onClick={() => setCompareId(0, s.id)}
                      className={`px-1 rounded ${
                        compareIds[0] === s.id
                          ? "bg-amber-600"
                          : "bg-slate-700 hover:bg-slate-600"
                      }`}
                    >A</button>
                    <button
                      onClick={() => setCompareId(1, s.id)}
                      className={`px-1 rounded ${
                        compareIds[1] === s.id
                          ? "bg-amber-600"
                          : "bg-slate-700 hover:bg-slate-600"
                      }`}
                    >B</button>
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
