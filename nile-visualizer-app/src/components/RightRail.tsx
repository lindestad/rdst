import { Activity, Droplets } from "lucide-react";
import { format, signed, sumNodes } from "../lib/format";
import type {
  EdgePeriodResult,
  NileEdge,
  NileNode,
  NodePeriodResult,
  PeriodResult,
} from "../types";

type RightRailProps = {
  selectedNode: NileNode;
  selectedNodeResult: NodePeriodResult | undefined;
  selectedEdge: NileEdge;
  selectedEdgeResult: EdgePeriodResult | undefined;
  periods: PeriodResult[];
  activePeriodIndex: number;
  period: PeriodResult;
  maxLoss: number;
};

export function RightRail({
  selectedNode,
  selectedNodeResult,
  selectedEdge,
  selectedEdgeResult,
  periods,
  activePeriodIndex,
  period,
  maxLoss,
}: RightRailProps) {
  return (
    <aside className="right-rail" aria-label="Selected details">
      <PlotPanel periods={periods} activeIndex={activePeriodIndex} />
      <NodeInspector node={selectedNode} result={selectedNodeResult} />
      <EdgeInspector edge={selectedEdge} result={selectedEdgeResult} maxLoss={maxLoss} />
      <RunBalance period={period} />
    </aside>
  );
}

function PlotPanel({ periods, activeIndex }: { periods: PeriodResult[]; activeIndex: number }) {
  return (
    <section className="inspector plot-panel">
      <p className="control-label">Plots</p>
      <LinePlot
        activeIndex={activeIndex}
        color="#1e96c8"
        label="Basin exit"
        values={periods.map((item) => item.totalBasinExitFlow)}
      />
      <LinePlot
        activeIndex={activeIndex}
        color="#d4483c"
        label="Routing loss"
        values={periods.map((item) => item.totalEdgeLoss)}
      />
      <LinePlot
        activeIndex={activeIndex}
        color="#20a66a"
        label="Food"
        values={periods.map((item) => sumNodes(item.nodeResults, (node) => node.irrigation?.foodProduced ?? 0))}
      />
    </section>
  );
}

function LinePlot({
  activeIndex,
  color,
  label,
  values,
}: {
  activeIndex: number;
  color: string;
  label: string;
  values: number[];
}) {
  const width = 280;
  const height = 86;
  const pad = 10;
  const max = Math.max(1, ...values);
  const points = values.map((value, index) => {
    const x = values.length <= 1 ? width / 2 : pad + (index / (values.length - 1)) * (width - pad * 2);
    const y = height - pad - (value / max) * (height - pad * 2);
    return { x, y };
  });
  const active = points[activeIndex] ?? points[0];

  return (
    <div className="line-plot">
      <div>
        <span>{label}</span>
        <strong>{format(values[activeIndex] ?? 0)}</strong>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label} trend`}>
        <path d={`M ${pad} ${height - pad} H ${width - pad}`} />
        <polyline
          fill="none"
          points={points.map((point) => `${point.x},${point.y}`).join(" ")}
          stroke={color}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
        />
        {active && <circle cx={active.x} cy={active.y} fill="#1f2732" r="4" />}
      </svg>
    </div>
  );
}

function NodeInspector({ node, result }: { node: NileNode; result: NodePeriodResult | undefined }) {
  if (!result) return null;

  const storageDelta = result.endingStorage - result.startingStorage;
  const storageLabel = node.capacity ? `${format(result.endingStorage)} / ${format(node.capacity)}` : "n/a";

  return (
    <section className="inspector">
      <div className="inspector-heading">
        <div>
          <p className="control-label">Node</p>
          <h2>{node.name}</h2>
        </div>
        <Activity size={19} />
      </div>
      <dl className="data-list">
        <DataItem label="Incoming" value={format(result.totalIncomingFlow)} />
        <DataItem label="Local inflow" value={format(result.totalLocalInflow)} />
        <DataItem label="Available" value={format(result.totalAvailableWater)} />
        <DataItem label="Outflow" value={format(result.totalDownstreamOutflow)} />
        <DataItem label="Storage" value={storageLabel} />
        <DataItem label="Storage change" value={signed(storageDelta)} tone={storageDelta >= 0 ? "good" : "warn"} />
      </dl>

      <div className="sector-list">
        <SectorBar label="Drinking" value={result.drinkingWater?.actualDelivery ?? 0} target={result.drinkingWater?.totalTarget ?? 0} />
        <SectorBar label="Irrigation" value={result.irrigation?.water.actualDelivery ?? 0} target={result.irrigation?.water.totalTarget ?? 0} />
        <SectorBar label="Energy" value={result.hydropower?.energyGenerated ?? 0} target={result.hydropower?.totalTargetEnergy ?? 0} />
      </div>
    </section>
  );
}

function EdgeInspector({ edge, result, maxLoss }: { edge: NileEdge; result: EdgePeriodResult | undefined; maxLoss: number }) {
  if (!result) return null;

  const lossScale = maxLoss > 0 ? (result.totalLostFlow / maxLoss) * 100 : 0;

  return (
    <section className="inspector">
      <div className="inspector-heading">
        <div>
          <p className="control-label">Reach</p>
          <h2>{edge.label}</h2>
        </div>
        <Droplets size={19} />
      </div>
      <dl className="data-list">
        <DataItem label="Sent" value={format(result.totalRoutedFlow)} />
        <DataItem label="Received" value={format(result.totalReceivedFlow)} />
        <DataItem label="Lost" value={format(result.totalLostFlow)} tone="warn" />
        <DataItem label="Configured loss" value={`${(edge.lossFraction * 100).toFixed(1)}%`} />
      </dl>
      <div className="loss-meter">
        <span style={{ width: `${lossScale}%` }} />
      </div>
    </section>
  );
}

function RunBalance({ period }: { period: PeriodResult }) {
  const totalDemand = sumNodes(period.nodeResults, (node) => {
    return (node.drinkingWater?.totalTarget ?? 0) + (node.irrigation?.water.totalTarget ?? 0);
  });
  const totalDelivered = sumNodes(period.nodeResults, (node) => {
    return (node.drinkingWater?.actualDelivery ?? 0) + (node.irrigation?.water.actualDelivery ?? 0);
  });
  const energy = sumNodes(period.nodeResults, (node) => node.hydropower?.energyGenerated ?? 0);
  const targetEnergy = sumNodes(period.nodeResults, (node) => node.hydropower?.totalTargetEnergy ?? 0);

  return (
    <section className="inspector balance">
      <p className="control-label">Run balance</p>
      <SectorBar label="Demand delivery" value={totalDelivered} target={totalDemand} />
      <SectorBar label="Power target" value={energy} target={targetEnergy} />
      <SectorBar label="Exit retention" value={period.totalBasinExitFlow} target={period.totalIncomingFlow + period.totalLocalInflow} invert />
    </section>
  );
}

function DataItem({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" }) {
  return (
    <div className={tone ? `data-item ${tone}` : "data-item"}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function SectorBar({
  label,
  value,
  target,
  invert = false,
}: {
  label: string;
  value: number;
  target: number;
  invert?: boolean;
}) {
  const ratio = target > 0 ? Math.min(1, value / target) : 0;
  const width = invert ? Math.max(4, 100 - ratio * 100) : ratio * 100;

  return (
    <div className="sector-bar">
      <div>
        <span>{label}</span>
        <strong>{target > 0 ? `${Math.round(ratio * 100)}%` : "n/a"}</strong>
      </div>
      <b>
        <i style={{ width: `${width}%` }} />
      </b>
    </div>
  );
}
