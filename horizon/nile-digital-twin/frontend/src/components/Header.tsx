import { useState } from "react";

import { api } from "../api/client";
import { useStore } from "../state/store";

export function Header() {
  const {
    policy, period, runningResults, setRunningResults, setSaved,
    compareMode, setCompareMode,
  } = useStore();
  const [running, setRunning] = useState(false);

  async function run() {
    setRunning(true);
    try {
      const res = await api.runScenario({ name: "current", period, policy });
      setRunningResults(res);
    } catch (e) {
      alert(`Run failed: ${e}`);
    } finally {
      setRunning(false);
    }
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
        <button
          disabled={running}
          onClick={run}
          className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50"
        >
          {running ? "Running…" : "Run"}
        </button>
        <button
          disabled={!runningResults}
          onClick={save}
          className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50"
        >
          Save
        </button>
        <button
          onClick={() => setCompareMode(!compareMode)}
          className={`px-3 py-1 rounded ${
            compareMode ? "bg-amber-600" : "bg-slate-600 hover:bg-slate-500"
          }`}
        >
          {compareMode ? "Exit compare" : "Compare"}
        </button>
      </div>
    </header>
  );
}
