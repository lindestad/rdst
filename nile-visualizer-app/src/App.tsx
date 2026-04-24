import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Droplets,
  GlassWater,
  Pause,
  Play,
  TrendingUp,
  Waves,
  Wheat,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { edges, nodes, periods } from "./data/nile";
import type { EdgePeriodResult, Lens, NileEdge, NileNode, NodePeriodResult } from "./types";

const lensOptions: Array<{ id: Lens; label: string; Icon: LucideIcon }> = [
  { id: "flow", label: "Flow", Icon: Waves },
  { id: "loss", label: "Loss", Icon: Droplets },
  { id: "delta", label: "Change", Icon: TrendingUp },
  { id: "food", label: "Food", Icon: Wheat },
  { id: "power", label: "Power", Icon: Zap },
  { id: "drinking", label: "Drinking", Icon: GlassWater },
];

const scenarioSummary = {
  name: "Nile MVP Demo",
  horizon: "90 days",
  reporting: "30-day months",
  nodes: nodes.length,
  edges: edges.length,
};

function App() {
  const [lens, setLens] = useState<Lens>("flow");
  const [periodIndex, setPeriodIndex] = useState(0);
  const [selectedNodeId, setSelectedNodeId] = useState("gerd");
  const [selectedEdgeId, setSelectedEdgeId] = useState("aswan_to_delta");
  const [isPlaying, setIsPlaying] = useState(true);

  const period = periods[periodIndex];
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? nodes[0];
  const selectedNodeResult = period.nodeResults.find((node) => node.nodeId === selectedNode.id);
  const selectedEdge = edges.find((edge) => edge.id === selectedEdgeId) ?? edges[0];
  const selectedEdgeResult = period.edgeResults.find((edge) => edge.edgeId === selectedEdge.id);

  const maxEdgeFlow = useMemo(
    () => Math.max(...periods.flatMap((item) => item.edgeResults.map((edge) => edge.totalRoutedFlow))),
    [],
  );
  const maxNodeAvailable = useMemo(
    () => Math.max(...periods.flatMap((item) => item.nodeResults.map((node) => node.totalAvailableWater))),
    [],
  );
  const maxLoss = useMemo(
    () => Math.max(...periods.flatMap((item) => item.edgeResults.map((edge) => edge.totalLostFlow))),
    [],
  );

  useEffect(() => {
    if (!isPlaying) {
      return;
    }

    const timer = window.setInterval(() => {
      setPeriodIndex((current) => (current + 1) % periods.length);
    }, 2200);

    return () => window.clearInterval(timer);
  }, [isPlaying]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="app-kicker">NRSM Visualizer</p>
          <h1>Nile basin run</h1>
        </div>

        <div className="scenario-strip" aria-label="Scenario summary">
          <SummaryItem label="Scenario" value={scenarioSummary.name} />
          <SummaryItem label="Horizon" value={scenarioSummary.horizon} />
          <SummaryItem label="Reporting" value={scenarioSummary.reporting} />
          <SummaryItem label="Graph" value={`${scenarioSummary.nodes} nodes / ${scenarioSummary.edges} edges`} />
        </div>
      </header>

      <section className="workspace">
        <aside className="left-rail" aria-label="Simulation controls">
          <div className="control-group">
            <p className="control-label">Lens</p>
            <div className="tool-grid">
              {lensOptions.map(({ id, label, Icon }) => (
                <button
                  className={`tool-button ${lens === id ? "active" : ""}`}
                  key={id}
                  onClick={() => setLens(id)}
                  title={`${label} lens`}
                  aria-label={`${label} lens`}
                  type="button"
                >
                  <Icon size={18} strokeWidth={2.1} />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="control-group">
            <p className="control-label">Period</p>
            <div className="period-row">
              <button
                className="icon-button"
                onClick={() => setIsPlaying((current) => !current)}
                type="button"
                title={isPlaying ? "Pause playback" : "Play playback"}
                aria-label={isPlaying ? "Pause playback" : "Play playback"}
              >
                {isPlaying ? <Pause size={18} /> : <Play size={18} />}
              </button>
              <div className="segmented" role="tablist" aria-label="Reporting period">
                {periods.map((item) => (
                  <button
                    className={item.periodIndex === periodIndex ? "active" : ""}
                    key={item.periodIndex}
                    onClick={() => {
                      setPeriodIndex(item.periodIndex);
                      setIsPlaying(false);
                    }}
                    role="tab"
                    aria-selected={item.periodIndex === periodIndex}
                    type="button"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <MetricStack period={period} />

          <div className="control-group compact">
            <p className="control-label">Monthly trend</p>
            <div className="spark-grid">
              <Sparkline label="Exit flow" values={periods.map((item) => item.totalBasinExitFlow)} activeIndex={periodIndex} />
              <Sparkline label="Edge loss" values={periods.map((item) => item.totalEdgeLoss)} activeIndex={periodIndex} />
              <Sparkline
                label="Energy"
                values={periods.map((item) => sumNodes(item.nodeResults, (node) => node.hydropower?.energyGenerated ?? 0))}
                activeIndex={periodIndex}
              />
            </div>
          </div>
        </aside>

        <section className="map-surface" aria-label="Nile basin network">
          <div className="map-toolbar">
            <div>
              <p className="control-label">Active window</p>
              <strong>
                Days {period.startDay + 1}-{period.endDayExclusive}
              </strong>
            </div>
            <div className="legend">
              <span className="legend-item sent">Sent</span>
              <span className="legend-item received">Received</span>
              <span className="legend-item loss">Loss / delta</span>
            </div>
          </div>

          <svg className="basin-map" viewBox="0 0 1040 620" role="img" aria-label="Nile simulator graph">
            <defs>
              {edges.map((edge) => {
                const edgeResult = period.edgeResults.find((result) => result.edgeId === edge.id);
                return (
                  <linearGradient
                    gradientUnits="userSpaceOnUse"
                    id={`edge-gradient-${edge.id}`}
                    key={edge.id}
                    x1={edge.gradient.x1}
                    x2={edge.gradient.x2}
                    y1={edge.gradient.y1}
                    y2={edge.gradient.y2}
                  >
                    {edgeStops(lens, edge, edgeResult)}
                  </linearGradient>
                );
              })}
            </defs>

            <g className="basin-basemap">
              <path d="M80 108 C180 70 330 72 444 132 C564 194 650 160 770 104 C864 60 942 88 980 164 C1014 232 990 310 932 378 C856 468 782 512 654 512 C526 514 476 442 374 456 C264 470 166 446 112 374 C56 298 38 178 80 108 Z" />
              <path d="M86 520 C205 462 290 540 396 514 C520 482 568 552 704 544 C812 538 890 478 976 430" />
            </g>

            <g className="edge-layer">
              {edges.map((edge) => {
                const edgeResult = period.edgeResults.find((result) => result.edgeId === edge.id);
                const strokeWidth = edgeWidth(edgeResult, maxEdgeFlow);

                return (
                  <g className="edge-group" key={edge.id}>
                    <path className="edge-shadow" d={edge.path} strokeWidth={strokeWidth + 10} />
                    <path
                      className={`edge-line ${selectedEdge.id === edge.id ? "selected" : ""}`}
                      d={edge.path}
                      onClick={() => setSelectedEdgeId(edge.id)}
                      stroke={`url(#edge-gradient-${edge.id})`}
                      strokeWidth={strokeWidth}
                    />
                    <text className="edge-loss-label">
                      <textPath href={`#edge-label-${edge.id}`} startOffset="50%">
                        {edgeLabel(lens, edge, edgeResult)}
                      </textPath>
                    </text>
                    <path className="edge-label-path" d={edge.path} id={`edge-label-${edge.id}`} />
                  </g>
                );
              })}
            </g>

            <g className="node-layer">
              {nodes.map((node) => {
                const nodeResult = period.nodeResults.find((result) => result.nodeId === node.id);
                const radius = nodeRadius(node, nodeResult, maxNodeAvailable);
                const fill = nodeFill(lens, node, nodeResult);

                return (
                  <g
                    className={`node ${selectedNode.id === node.id ? "selected" : ""}`}
                    key={node.id}
                    onClick={() => setSelectedNodeId(node.id)}
                    transform={`translate(${node.x} ${node.y})`}
                  >
                    <circle className="node-pulse" r={radius + 12} />
                    <circle className="node-body" fill={fill} r={radius} />
                    <circle className="node-ring" r={radius + 4} />
                    <text className="node-label" y={radius + 27}>
                      {node.shortName}
                    </text>
                    <text className="node-sublabel" y={radius + 44}>
                      {node.kind === "reservoir" ? "reservoir" : node.country}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        </section>

        <aside className="right-rail" aria-label="Selected details">
          <NodeInspector node={selectedNode} result={selectedNodeResult} />
          <EdgeInspector edge={selectedEdge} result={selectedEdgeResult} maxLoss={maxLoss} />
          <RunBalance period={period} />
        </aside>
      </section>
    </main>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="summary-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MetricStack({ period }: { period: (typeof periods)[number] }) {
  const drinking = sumNodes(period.nodeResults, (node) => node.drinkingWater?.actualDelivery ?? 0);
  const irrigation = sumNodes(period.nodeResults, (node) => node.irrigation?.water.actualDelivery ?? 0);
  const food = sumNodes(period.nodeResults, (node) => node.irrigation?.foodProduced ?? 0);
  const energy = sumNodes(period.nodeResults, (node) => node.hydropower?.energyGenerated ?? 0);

  return (
    <div className="metric-stack">
      <Metric label="Exit flow" value={format(period.totalBasinExitFlow)} accent="blue" />
      <Metric label="Edge loss" value={format(period.totalEdgeLoss)} accent="red" />
      <Metric label="Food" value={format(food)} accent="green" />
      <Metric label="Energy" value={format(energy)} accent="yellow" />
      <Metric label="Drinking" value={format(drinking)} accent="cyan" />
      <Metric label="Irrigation" value={format(irrigation)} accent="violet" />
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className={`metric ${accent}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Sparkline({ label, values, activeIndex }: { label: string; values: number[]; activeIndex: number }) {
  const max = Math.max(...values);

  return (
    <div className="sparkline">
      <span>{label}</span>
      <div className="bar-row">
        {values.map((value, index) => (
          <i
            className={index === activeIndex ? "active" : ""}
            key={`${label}-${index}`}
            style={{ height: `${Math.max(18, (value / max) * 58)}px` }}
          />
        ))}
      </div>
    </div>
  );
}

function NodeInspector({ node, result }: { node: NileNode; result: NodePeriodResult | undefined }) {
  if (!result) {
    return null;
  }

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
  if (!result) {
    return null;
  }

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

function RunBalance({ period }: { period: (typeof periods)[number] }) {
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

function SectorBar({ label, value, target, invert = false }: { label: string; value: number; target: number; invert?: boolean }) {
  const ratio = target > 0 ? Math.min(1, value / target) : 0;
  const width = invert ? Math.max(4, 100 - ratio * 100) : ratio * 100;

  return (
    <div className="sector-bar">
      <div>
        <span>{label}</span>
        <strong>
          {target > 0 ? `${Math.round(ratio * 100)}%` : "n/a"}
        </strong>
      </div>
      <b>
        <i style={{ width: `${width}%` }} />
      </b>
    </div>
  );
}

function edgeStops(lens: Lens, edge: NileEdge, result: EdgePeriodResult | undefined) {
  const baseline = periods[0].edgeResults.find((item) => item.edgeId === edge.id);
  const delta = result && baseline ? (result.totalReceivedFlow - baseline.totalReceivedFlow) / baseline.totalReceivedFlow : 0;
  const deltaColor = delta >= 0 ? "#20a66a" : "#d4483c";
  const lossOffset = `${Math.max(58, 92 - edge.lossFraction * 900)}%`;

  if (lens === "loss") {
    return (
      <>
        <stop offset="0%" stopColor="#1e96c8" />
        <stop offset={lossOffset} stopColor="#1e96c8" />
        <stop offset="100%" stopColor="#d4483c" />
      </>
    );
  }

  if (lens === "delta") {
    return (
      <>
        <stop offset="0%" stopColor="#55606e" />
        <stop offset="52%" stopColor="#55606e" />
        <stop offset="100%" stopColor={deltaColor} />
      </>
    );
  }

  if (lens === "food") {
    return (
      <>
        <stop offset="0%" stopColor="#2aa579" />
        <stop offset="100%" stopColor="#79bd52" />
      </>
    );
  }

  if (lens === "power") {
    return (
      <>
        <stop offset="0%" stopColor="#e2b338" />
        <stop offset="100%" stopColor="#f17f3d" />
      </>
    );
  }

  if (lens === "drinking") {
    return (
      <>
        <stop offset="0%" stopColor="#4fb5db" />
        <stop offset="100%" stopColor="#e9f8ff" />
      </>
    );
  }

  return (
    <>
      <stop offset="0%" stopColor="#1e96c8" />
      <stop offset="68%" stopColor="#1e96c8" />
      <stop offset="100%" stopColor="#20a66a" />
    </>
  );
}

function edgeLabel(lens: Lens, edge: NileEdge, result: EdgePeriodResult | undefined) {
  if (!result) {
    return "";
  }

  if (lens === "loss") {
    return `${format(result.totalLostFlow)} lost`;
  }

  if (lens === "delta") {
    const baseline = periods[0].edgeResults.find((item) => item.edgeId === edge.id);
    const delta = baseline ? result.totalReceivedFlow - baseline.totalReceivedFlow : 0;
    return signed(delta);
  }

  return `${format(result.totalReceivedFlow)} received`;
}

function edgeWidth(result: EdgePeriodResult | undefined, max: number) {
  if (!result) {
    return 8;
  }

  return 7 + (result.totalRoutedFlow / max) * 19;
}

function nodeRadius(node: NileNode, result: NodePeriodResult | undefined, max: number) {
  if (!result) {
    return node.kind === "reservoir" ? 34 : 29;
  }

  return (node.kind === "reservoir" ? 31 : 27) + (result.totalAvailableWater / max) * 22;
}

function nodeFill(lens: Lens, node: NileNode, result: NodePeriodResult | undefined) {
  if (!result) {
    return "#39414c";
  }

  if (lens === "food" && result.irrigation) {
    return "#2f8f5b";
  }

  if (lens === "power" && result.hydropower) {
    return "#b17621";
  }

  if (lens === "drinking" && result.drinkingWater) {
    return "#3a8fab";
  }

  if (lens === "loss") {
    return node.kind === "reservoir" ? "#73513d" : "#5f6269";
  }

  if (lens === "delta") {
    const baseline = periods[0].nodeResults.find((item) => item.nodeId === node.id);
    const delta = baseline ? result.totalDownstreamOutflow - baseline.totalDownstreamOutflow : 0;
    return delta >= 0 ? "#2f8f5b" : "#a9423a";
  }

  return node.kind === "reservoir" ? "#38516d" : "#3f6472";
}

function sumNodes(nodesToSum: NodePeriodResult[], selector: (node: NodePeriodResult) => number) {
  return nodesToSum.reduce((total, node) => total + selector(node), 0);
}

function format(value: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: value >= 100 ? 0 : 1,
  }).format(value);
}

function signed(value: number) {
  const rounded = format(Math.abs(value));
  return value >= 0 ? `+${rounded}` : `-${rounded}`;
}

export default App;
