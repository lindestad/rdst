import { Activity, Droplets } from "lucide-react";
import {
  ENERGY_UNIT,
  WATER_VOLUME_UNIT,
  format,
  signed,
  sumNodes,
} from "../lib/format";
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
};

export function RightRail({
  selectedNode,
  selectedNodeResult,
  selectedEdge,
  selectedEdgeResult,
  periods,
  activePeriodIndex,
  period,
}: RightRailProps) {
  return (
    <aside className="right-rail" aria-label="Selected details">
      <PlotPanel periods={periods} activeIndex={activePeriodIndex} />
      <NodeInspector node={selectedNode} result={selectedNodeResult} />
      <EdgeInspector edge={selectedEdge} result={selectedEdgeResult} />
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
        unit={WATER_VOLUME_UNIT}
        values={periods.map((item) => item.totalBasinExitFlow)}
      />
      <LinePlot
        activeIndex={activeIndex}
        color="#b17621"
        label="Energy"
        unit={ENERGY_UNIT}
        values={periods.map((item) => sumNodes(item.nodeResults, (node) => node.hydropower?.energyGenerated ?? 0))}
      />
      <LinePlot
        activeIndex={activeIndex}
        color="#20a66a"
        label="Food produced"
        unit="units"
        values={periods.map((item) => sumNodes(item.nodeResults, (node) => node.irrigation?.foodProduced ?? 0))}
      />
    </section>
  );
}

function LinePlot({
  activeIndex,
  color,
  label,
  unit,
  values,
}: {
  activeIndex: number;
  color: string;
  label: string;
  unit: string;
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
        <strong>
          {format(values[activeIndex] ?? 0)} <em>{unit}</em>
        </strong>
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
  const storageLabel = node.capacity
    ? `${format(result.endingStorage)} / ${format(node.capacity)} ${WATER_VOLUME_UNIT}`
    : "n/a";
  const hp = result.hydropower;

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
        <DataItem label="Inflow" value={`${format(result.totalIncomingFlow)} ${WATER_VOLUME_UNIT}`} />
        <DataItem label="Available" value={`${format(result.totalAvailableWater)} ${WATER_VOLUME_UNIT}`} />
        <DataItem label="Outflow" value={`${format(result.totalDownstreamOutflow)} ${WATER_VOLUME_UNIT}`} />
        <DataItem label="Storage" value={storageLabel} />
        <DataItem
          label="Storage Δ"
          value={`${signed(storageDelta)} ${WATER_VOLUME_UNIT}`}
          tone={storageDelta >= 0 ? "good" : "warn"}
        />
        {hp && (
          <DataItem
            label="Energy"
            value={`${format(hp.energyGenerated)} ${ENERGY_UNIT}`}
          />
        )}
      </dl>

      <div className="sector-list">
        <SectorBar
          label="Drinking"
          value={result.drinkingWater?.actualDelivery ?? 0}
          target={result.drinkingWater?.totalTarget ?? 0}
          unit={WATER_VOLUME_UNIT}
        />
        <SectorBar
          label="Irrigation"
          value={result.irrigation?.water.actualDelivery ?? 0}
          target={result.irrigation?.water.totalTarget ?? 0}
          unit={WATER_VOLUME_UNIT}
        />
      </div>
    </section>
  );
}

function EdgeInspector({ edge, result }: { edge: NileEdge; result: EdgePeriodResult | undefined }) {
  if (!result) return null;

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
        <DataItem label="Flow" value={`${format(result.totalFlow)} ${WATER_VOLUME_UNIT}`} />
        <DataItem label="From" value={edge.from} />
        <DataItem label="To" value={edge.to} />
      </dl>
    </section>
  );
}

function RunBalance({ period }: { period: PeriodResult }) {
  const drinkDemand = sumNodes(period.nodeResults, (n) => n.drinkingWater?.totalTarget ?? 0);
  const drinkDelivered = sumNodes(period.nodeResults, (n) => n.drinkingWater?.actualDelivery ?? 0);
  const foodDemand = sumNodes(period.nodeResults, (n) => n.irrigation?.water.totalTarget ?? 0);
  const foodDelivered = sumNodes(period.nodeResults, (n) => n.irrigation?.water.actualDelivery ?? 0);

  return (
    <section className="inspector balance">
      <p className="control-label">Period balance</p>
      <SectorBar label="Drinking met" value={drinkDelivered} target={drinkDemand} unit={WATER_VOLUME_UNIT} />
      <SectorBar label="Food water met" value={foodDelivered} target={foodDemand} unit={WATER_VOLUME_UNIT} />
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
  unit,
  invert = false,
}: {
  label: string;
  value: number;
  target: number;
  unit?: string;
  invert?: boolean;
}) {
  const ratio = target > 0 ? Math.min(1, value / target) : 0;
  const width = invert ? Math.max(4, 100 - ratio * 100) : ratio * 100;
  const tooltip = target > 0 ? `${format(value)} / ${format(target)}${unit ? ` ${unit}` : ""}` : "no demand";

  return (
    <div className="sector-bar" title={tooltip}>
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
