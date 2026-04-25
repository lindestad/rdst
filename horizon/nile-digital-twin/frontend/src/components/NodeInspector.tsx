import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { Timeseries } from "../api/types";
import { KpiChart } from "../lib/kpiChart";

export function NodeInspector({
  nodeId, onClose,
}: { nodeId: string; onClose: () => void }) {
  const [cfg, setCfg] = useState<Record<string, unknown> | null>(null);
  const [ts, setTs] = useState<Timeseries | null>(null);

  useEffect(() => {
    api.nodeConfig(nodeId).then(setCfg).catch(() => setCfg(null));
    api.timeseries(nodeId, { vars: ["precip_mm", "pet_mm", "runoff_mm"] })
      .then(setTs).catch(() => setTs(null));
  }, [nodeId]);

  return (
    <div className="absolute right-3 top-3 w-72 bg-slate-800 border border-slate-700 rounded p-3 shadow-xl text-sm text-slate-100 z-10">
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-semibold">{(cfg?.id as string) ?? nodeId}</h3>
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
          <KpiChart
            x={ts.month}
            y={(ts.values.precip_mm ?? []).map((v) => v ?? 0)}
            color="#3b82f6" unit="mm"
          />
          <h4 className="text-xs uppercase text-slate-400 mt-2">PET (mm)</h4>
          <KpiChart
            x={ts.month}
            y={(ts.values.pet_mm ?? []).map((v) => v ?? 0)}
            color="#f59e0b" unit="mm"
          />
        </>
      )}
    </div>
  );
}
