import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  BookOpen,
  Droplets,
  FileJson,
  Github,
  GlassWater,
  Globe2,
  MapPinned,
  Network,
  Pause,
  Play,
  RotateCcw,
  Satellite,
  ShieldCheck,
  Target,
  TrendingUp,
  Users,
  Waves,
  Wheat,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { datasetFromCsvFiles, datasetFromFile } from "./adapters/nrsm";
import { sampleDataset } from "./data/nile";
import type {
  EdgePeriodResult,
  Delivery,
  Lens,
  NileEdge,
  NileNode,
  NodePeriodResult,
  PeriodResult,
  VisualizerDataset,
} from "./types";

type SitePage = "visualization" | "pitch" | "team";

const lensOptions: Array<{ id: Lens; label: string; Icon: LucideIcon }> = [
  { id: "flow", label: "Flow", Icon: Waves },
  { id: "loss", label: "Loss", Icon: Droplets },
  { id: "delta", label: "Change", Icon: TrendingUp },
  { id: "food", label: "Food", Icon: Wheat },
  { id: "power", label: "Power", Icon: Zap },
  { id: "drinking", label: "Drinking", Icon: GlassWater },
];

const sitePages: Array<{ id: SitePage; label: string; Icon: LucideIcon }> = [
  { id: "visualization", label: "Visualization", Icon: Network },
  { id: "pitch", label: "Pitch", Icon: BookOpen },
  { id: "team", label: "Team", Icon: Users },
];

const pitchCards: Array<{ title: string; body: string; Icon: LucideIcon }> = [
  {
    title: "The problem",
    body: "Water allocation decisions are often discussed through separate spreadsheets, maps, and sector models. That makes tradeoffs hard to see and harder to explain.",
    Icon: Globe2,
  },
  {
    title: "The solution",
    body: "Fairwater turns simulator runs into a shared visual workspace for river flow, reservoir releases, agriculture, municipal demand, and energy output.",
    Icon: Target,
  },
  {
    title: "The evidence layer",
    body: "A Rust simulation core produces reproducible outputs, while the web interface translates those outputs into plots, basin state, and sector indicators.",
    Icon: Satellite,
  },
  {
    title: "The outcome",
    body: "Teams can compare scenarios, identify stress points, and communicate the consequences of policy choices without hiding the underlying model assumptions.",
    Icon: ShieldCheck,
  },
];

const teamMembers = [
  {
    tag: "01",
    name: "Member 1",
    role: "Project lead / pitch",
    focus: "Fill in name, role, affiliation, and contribution.",
  },
  {
    tag: "02",
    name: "Member 2",
    role: "Simulation lead",
    focus: "Fill in name, role, affiliation, and contribution.",
  },
  {
    tag: "03",
    name: "Member 3",
    role: "Data and Earth observation",
    focus: "Fill in name, role, affiliation, and contribution.",
  },
  {
    tag: "04",
    name: "Member 4",
    role: "Visualization and UX",
    focus: "Fill in name, role, affiliation, and contribution.",
  },
  {
    tag: "05",
    name: "Member 5",
    role: "Validation / domain insight",
    focus: "Fill in name, role, affiliation, and contribution.",
  },
];

function App() {
  const [page, setPage] = useState<SitePage>(readPageFromHash);
  const [dataset, setDataset] = useState<VisualizerDataset>(sampleDataset);
  const [lens, setLens] = useState<Lens>("flow");
  const [periodIndex, setPeriodIndex] = useState(0);
  const [selectedNodeId, setSelectedNodeId] = useState(sampleDataset.nodes[0].id);
  const [selectedEdgeId, setSelectedEdgeId] = useState(sampleDataset.edges[0].id);
  const [isPlaying, setIsPlaying] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const { metadata, nodes, edges, periods } = dataset;
  const activePeriodIndex = Math.min(periodIndex, periods.length - 1);

  const period = periods[activePeriodIndex];
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? nodes[0];
  const selectedNodeResult = period.nodeResults.find((node) => node.nodeId === selectedNode.id);
  const selectedEdge = edges.find((edge) => edge.id === selectedEdgeId) ?? edges[0];
  const selectedEdgeResult = period.edgeResults.find((edge) => edge.edgeId === selectedEdge.id);

  const maxEdgeFlow = useMemo(
    () => Math.max(1, ...periods.flatMap((item) => item.edgeResults.map((edge) => edge.totalRoutedFlow))),
    [periods],
  );
  const maxNodeAvailable = useMemo(
    () => Math.max(1, ...periods.flatMap((item) => item.nodeResults.map((node) => node.totalAvailableWater))),
    [periods],
  );
  const maxLoss = useMemo(
    () => Math.max(1, ...periods.flatMap((item) => item.edgeResults.map((edge) => edge.totalLostFlow))),
    [periods],
  );

  useEffect(() => {
    const sync = () => setPage(readPageFromHash());
    window.addEventListener("hashchange", sync);
    if (!window.location.hash) {
      window.history.replaceState(null, "", "#/visualization");
    }
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  useEffect(() => {
    if (!isPlaying || page !== "visualization") {
      return;
    }

    const timer = window.setInterval(() => {
      setPeriodIndex((current) => (current + 1) % periods.length);
    }, 2200);

    return () => window.clearInterval(timer);
  }, [isPlaying, page, periods.length]);

  useEffect(() => {
    setPeriodIndex(0);
    setSelectedNodeId(dataset.nodes[0]?.id ?? "");
    setSelectedEdgeId(dataset.edges[0]?.id ?? "");
  }, [dataset]);

  async function loadFile(file: File | null) {
    if (!file) return;
    try {
      const next = await datasetFromFile(file);
      setDataset(next);
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load simulator output.");
    }
  }

  async function loadCsvFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    try {
      const next = await datasetFromCsvFiles(files);
      setDataset(next);
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load NRSM CSV results.");
    }
  }

  function navigate(nextPage: SitePage) {
    window.location.hash = `/${nextPage}`;
    setPage(nextPage);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <p className="app-kicker">Fairwater</p>
          <h1>River basin decisions made visible</h1>
          <nav className="site-nav" aria-label="Site pages">
            {sitePages.map(({ id, label, Icon }) => (
              <button
                className={page === id ? "active" : ""}
                key={id}
                onClick={() => navigate(id)}
                type="button"
              >
                <Icon size={16} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
        </div>

        {page === "visualization" ? (
          <div className="scenario-strip" aria-label="Scenario summary">
            <SummaryItem label="Scenario" value={metadata.name} />
            <SummaryItem label="Source" value={metadata.source} />
            <SummaryItem label="Reporting" value={metadata.reporting} />
            <SummaryItem label="Graph" value={`${nodes.length} nodes / ${edges.length} edges`} />
          </div>
        ) : (
          <div className="site-summary">
            <SummaryItem label="Project" value="Fairwater" />
            <SummaryItem label="Focus" value="Water, food, energy" />
            <SummaryItem label="Engine" value="NRSM Rust" />
          </div>
        )}

        {page === "visualization" && <div className="file-tools">
          <label className="file-button secondary" title="Load NRSM --results-dir CSV files">
            <FileJson size={18} />
            <span>Load CSVs</span>
            <input
              accept=".csv,text/csv"
              multiple
              onChange={(event) => void loadCsvFiles(event.currentTarget.files)}
              type="file"
              {...({ webkitdirectory: "" } as Record<string, string>)}
            />
          </label>
          <label className="file-button" title="Load NRSM JSON output">
            <FileJson size={18} />
            <span>Load JSON</span>
            <input
              accept="application/json,.json"
              onChange={(event) => void loadFile(event.currentTarget.files?.[0] ?? null)}
              type="file"
            />
          </label>
          <button
            className="icon-button"
            onClick={() => {
              setDataset(sampleDataset);
              setLoadError(null);
            }}
            title="Reset to sample run"
            type="button"
          >
            <RotateCcw size={17} />
          </button>
        </div>}
      </header>
      {loadError && <div className="load-error">{loadError}</div>}

      {page === "pitch" ? (
        <PitchPage onOpenVisualization={() => navigate("visualization")} />
      ) : page === "team" ? (
        <TeamPage onOpenVisualization={() => navigate("visualization")} />
      ) : (
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
              <div className="period-slider">
                <strong>{period.label}</strong>
                <input
                  aria-label="Reporting period"
                  max={periods.length - 1}
                  min={0}
                  onChange={(event) => {
                    setPeriodIndex(Number(event.currentTarget.value));
                    setIsPlaying(false);
                  }}
                  step={1}
                  type="range"
                  value={activePeriodIndex}
                />
              </div>
            </div>
          </div>

          <MetricStack period={period} />

          <div className="control-group compact">
            <p className="control-label">Monthly trend</p>
            <div className="spark-grid">
              <Sparkline label="Exit flow" values={periods.map((item) => item.totalBasinExitFlow)} activeIndex={activePeriodIndex} />
              <Sparkline label="Edge loss" values={periods.map((item) => item.totalEdgeLoss)} activeIndex={activePeriodIndex} />
              <Sparkline
                label="Energy"
                values={periods.map((item) => sumNodes(item.nodeResults, (node) => node.hydropower?.energyGenerated ?? 0))}
                activeIndex={activePeriodIndex}
              />
            </div>
          </div>
        </aside>

        <section className="map-surface" aria-label="Nile basin decision map">
          <div className="map-toolbar">
            <div>
              <p className="control-label">Active window</p>
              <strong>
                Days {period.startDay + 1}-{period.endDayExclusive}
              </strong>
            </div>
            <div className="legend">
              <span className="legend-item flow">River flow</span>
              <span className="legend-item warning">Moderate risk</span>
              <span className="legend-item critical">High risk</span>
              <span className="risk-note">Risk areas show where allocation choices constrain food, cities, storage, or Delta flow.</span>
            </div>
          </div>

          <svg className="basin-map" viewBox="0 0 1040 720" role="img" aria-label="Nile simulator graph">
            <defs>
              <filter id="risk-blur" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="12" />
              </filter>
              <pattern id="warning-risk-pattern" width="16" height="16" patternTransform="rotate(35)" patternUnits="userSpaceOnUse">
                <rect fill="#d89b24" height="16" opacity="0.58" width="16" />
                <path d="M0 0 L0 16" stroke="#9b6816" strokeWidth="4" opacity="0.44" />
              </pattern>
              <pattern id="critical-risk-pattern" width="16" height="16" patternTransform="rotate(35)" patternUnits="userSpaceOnUse">
                <rect fill="#d4483c" height="16" opacity="0.66" width="16" />
                <path d="M0 0 L0 16" stroke="#8d3028" strokeWidth="4" opacity="0.5" />
              </pattern>
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
                    {edgeStops(lens, edge, edgeResult, periods)}
                  </linearGradient>
                );
              })}
            </defs>

            <g className="basin-basemap">
              <rect x="70" y="42" width="900" height="626" rx="8" />
              <path className="country-boundary" d="M250 82 L266 214 L240 338 L302 484 L450 652" />
              <path className="country-boundary" d="M430 120 L456 294 L438 360 L356 486" />
              <path className="country-boundary" d="M610 138 L612 286 L532 392 L662 458 L882 450" />
              <path className="country-boundary" d="M252 82 C346 106 388 108 430 120" />
              <path className="country-boundary" d="M438 360 C498 316 560 290 612 286" />
              <text x="332" y="102">Egypt</text>
              <text x="438" y="322">Sudan</text>
              <text x="720" y="390">Ethiopia</text>
              <text x="320" y="522">South Sudan</text>
              <text x="510" y="638">Uganda</text>
            </g>

            <ImpactOverlays nodes={nodes} period={period} periods={periods} />

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
                        {edgeLabel(lens, edge, edgeResult, periods)}
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
                const fill = nodeFill(lens, node, nodeResult, periods);

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
          <PlotPanel periods={periods} activeIndex={activePeriodIndex} />
          <NodeInspector node={selectedNode} result={selectedNodeResult} />
          <EdgeInspector edge={selectedEdge} result={selectedEdgeResult} maxLoss={maxLoss} />
          <RunBalance period={period} />
        </aside>
      </section>
      )}
    </main>
  );
}

function PitchPage({ onOpenVisualization }: { onOpenVisualization: () => void }) {
  return (
    <section className="content-page pitch-page">
      <div className="content-hero">
        <div>
          <p className="app-kicker">Fairwater pitch</p>
          <h2>Transparent scenario planning for shared river basins</h2>
          <p>
            Fairwater helps decision-makers and technical teams explore how
            reservoir operations, drought stress, irrigation demand, and
            municipal needs affect downstream flow, food production, and energy.
          </p>
          <div className="hero-actions">
            <button className="file-button" onClick={onOpenVisualization} type="button">
              <BarChart3 size={18} />
              <span>Open visualization</span>
            </button>
            <a className="text-link-button" href="https://github.com/lindestad/rdst" rel="noreferrer" target="_blank">
              <Github size={18} />
              <span>Repository</span>
            </a>
          </div>
        </div>
        <div className="pitch-visual" aria-label="Basin concept visual">
          <svg viewBox="0 0 520 320" role="img">
            <path className="land" d="M34 78 C112 28 206 44 276 76 C352 112 422 82 484 132 C538 176 498 258 410 278 C318 300 270 248 196 268 C114 290 38 236 26 162 C20 126 18 96 34 78 Z" />
            <path className="river-main" d="M64 246 C134 198 176 206 226 172 C280 134 314 142 366 106 C402 80 444 80 482 58" />
            <path className="river-branch" d="M74 80 C136 116 160 152 226 172" />
            <path className="river-branch" d="M162 282 C190 230 210 204 226 172" />
            <circle className="map-node source" cx="74" cy="80" r="13" />
            <circle className="map-node reservoir" cx="264" cy="146" r="18" />
            <circle className="map-node city" cx="366" cy="106" r="13" />
            <circle className="map-node farm" cx="196" cy="254" r="15" />
            <circle className="map-node delta" cx="482" cy="58" r="16" />
          </svg>
        </div>
      </div>

      <div className="pitch-grid">
        {pitchCards.map(({ title, body, Icon }) => (
          <article className="story-card" key={title}>
            <Icon size={22} />
            <h3>{title}</h3>
            <p>{body}</p>
          </article>
        ))}
      </div>

      <section className="wide-band">
        <div>
          <p className="app-kicker">Pitch</p>
          <h2>From simulator output to shared evidence</h2>
        </div>
        <p>
          The current prototype converts NRSM outputs into a browser-based basin
          view. Line widths show routed water, panels surface sector outcomes,
          and plots summarize basin balance. The product direction is a simple
          web workspace where users can upload or select scenarios, inspect
          tradeoffs, and export evidence for discussion.
        </p>
      </section>

      <section className="pitch-outline">
        <div>
          <p className="app-kicker">Pitch skeleton</p>
          <h2>Storyline to complete</h2>
        </div>
        <dl>
          <div>
            <dt>Problem</dt>
            <dd>Fragmented water planning makes basin tradeoffs difficult to compare and communicate.</dd>
          </div>
          <div>
            <dt>Users</dt>
            <dd>Water agencies, energy planners, agriculture analysts, basin researchers, and public-interest teams.</dd>
          </div>
          <div>
            <dt>Product</dt>
            <dd>A lightweight web interface for simulation runs, maps, sector KPIs, and scenario evidence.</dd>
          </div>
          <div>
            <dt>Data and model</dt>
            <dd>NRSM simulator outputs today, with a path toward hydrology, climate, and Earth observation inputs.</dd>
          </div>
          <div>
            <dt>Demo</dt>
            <dd>Load a saved run, scrub the period, select a stress point, and explain flow, food, and energy impacts.</dd>
          </div>
          <div>
            <dt>Next step</dt>
            <dd>Finalize scenario export, add comparison mode, improve basin geometry, and publish under the Fairwater domain.</dd>
          </div>
        </dl>
      </section>
    </section>
  );
}

function TeamPage({ onOpenVisualization }: { onOpenVisualization: () => void }) {
  return (
    <section className="content-page team-page">
      <div className="content-hero compact-hero">
        <div>
          <p className="app-kicker">Team</p>
          <h2>Fairwater team</h2>
          <p>
            Five contributors are building the simulator, data pathway,
            visualization, validation, and pitch. Replace these cards with names,
            roles, affiliations, and contact links when ready.
          </p>
        </div>
        <button className="file-button" onClick={onOpenVisualization} type="button">
          <MapPinned size={18} />
          <span>View basin run</span>
        </button>
      </div>

      <div className="team-grid">
        {teamMembers.map((member) => (
          <article className="team-card" key={member.name}>
            <div className="avatar-mark">{member.tag}</div>
            <div>
              <h3>{member.name}</h3>
              <strong>{member.role}</strong>
              <p>{member.focus}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
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

function ImpactOverlays({
  nodes,
  period,
  periods,
}: {
  nodes: NileNode[];
  period: PeriodResult;
  periods: PeriodResult[];
}) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const resultById = new Map(period.nodeResults.map((result) => [result.nodeId, result]));
  const foodNodes = nodes.filter((node) => {
    const result = resultById.get(node.id);
    return Boolean(result?.irrigation) || /ag|irrigation|delta/i.test(node.id);
  });
  const municipalNodes = nodes.filter((node) => {
    const result = resultById.get(node.id);
    return Boolean(result?.drinkingWater) || /cairo|khartoum|municipal|delta/i.test(node.id);
  });
  const reservoirNodes = nodes.filter((node) => node.kind === "reservoir");
  const deltaNode = nodeById.get("nile_delta") ?? nodeById.get("delta");
  const deltaResult = deltaNode ? resultById.get(deltaNode.id) : undefined;
  const deltaStress = deltaResult ? flowStress(deltaResult.totalBasinExitOutflow, periods) : null;

  return (
    <g className="impact-layer" pointerEvents="none">
      {foodNodes.map((node) => {
        const stress = foodStress(node.id, resultById.get(node.id), periods);
        if (stress.level === "none") return null;
        return (
          <g className="risk-cluster" key={`food-${node.id}`}>
            <ellipse
              className={`impact-zone ${stress.level}`}
              cx={node.x}
              cy={node.y}
              rx={stress.radiusX}
              ry={stress.radiusY}
            />
            <text className="impact-label" x={node.x} y={node.y - stress.radiusY - 8}>
              {stress.label}
            </text>
            <text className="impact-value" x={node.x} y={node.y + 5}>
              {stress.value}
            </text>
          </g>
        );
      })}

      {municipalNodes.map((node) => {
        const stress = demandStress(resultById.get(node.id)?.drinkingWater ?? null, "water demand");
        if (stress.level === "none") return null;
        return (
          <g className="risk-cluster" key={`municipal-${node.id}`}>
            <circle className={`impact-ring ${stress.level}`} cx={node.x} cy={node.y} r={stress.radius} />
            <text className="impact-label" x={node.x + stress.radius + 8} y={node.y + 4}>
              {stress.label}
            </text>
            <text className="impact-value side" x={node.x + stress.radius + 8} y={node.y + 20}>
              {stress.value}
            </text>
          </g>
        );
      })}

      {reservoirNodes.map((node) => {
        const stress = reservoirStress(node, resultById.get(node.id));
        if (stress.level === "none") return null;
        return (
          <g className="risk-cluster" key={`reservoir-${node.id}`}>
            <circle className={`impact-ring ${stress.level}`} cx={node.x} cy={node.y} r={stress.radius} />
            <text className="impact-label" x={node.x + stress.radius + 8} y={node.y - 6}>
              {stress.label}
            </text>
            <text className="impact-value side" x={node.x + stress.radius + 8} y={node.y + 10}>
              {stress.value}
            </text>
          </g>
        );
      })}

      {deltaNode && deltaStress && deltaStress.level !== "none" && (
        <g className="risk-cluster">
          <ellipse
            className={`impact-zone ${deltaStress.level}`}
            cx={deltaNode.x}
            cy={deltaNode.y}
            rx="118"
            ry="60"
          />
          <text className="impact-label" x={deltaNode.x - 92} y={deltaNode.y + 84}>
            {deltaStress.label}
          </text>
          <text className="impact-value side" x={deltaNode.x - 92} y={deltaNode.y + 102}>
            {deltaStress.value}
          </text>
        </g>
      )}
    </g>
  );
}

function foodStress(
  nodeId: string,
  result: NodePeriodResult | undefined,
  periods: PeriodResult[],
) {
  const target = result?.irrigation?.water.totalTarget ?? 0;
  const delivered = result?.irrigation?.water.actualDelivery ?? 0;
  const currentFood = result?.irrigation?.foodProduced ?? 0;
  const maxFood = Math.max(
    0,
    ...periods.map((period) => {
      const node = period.nodeResults.find((candidate) => candidate.nodeId === nodeId);
      return node?.irrigation?.foodProduced ?? 0;
    }),
  );
  const ratio = target > 0 ? delivered / target : maxFood > 0 ? currentFood / maxFood : 1;
  const level = stressLevel(ratio);
  return {
    level,
    label: level === "critical" ? "Food production at risk" : level === "warning" ? "Food pressure" : "",
    value: `${Math.round(ratio * 100)}% of reference`,
    radiusX: /egypt|delta/i.test(nodeId) ? 148 : 100,
    radiusY: /egypt|delta/i.test(nodeId) ? 72 : 58,
  };
}

function demandStress(delivery: Delivery | null, label: string) {
  if (!delivery || delivery.totalTarget <= 0) {
    return { level: "none" as const, label: "", value: "", radius: 0 };
  }
  const ratio = delivery.actualDelivery / delivery.totalTarget;
  const level = stressLevel(ratio);
  return {
    level,
    label: level === "critical" ? `Unmet ${label}` : level === "warning" ? `${label} pressure` : "",
    value: `${Math.round(ratio * 100)}% served`,
    radius: level === "critical" ? 66 : 52,
  };
}

function reservoirStress(node: NileNode, result: NodePeriodResult | undefined) {
  if (!node.capacity || !result) {
    return { level: "none" as const, label: "", value: "", radius: 0 };
  }
  const ratio = result.endingStorage / node.capacity;
  const level = ratio < 0.18 ? "critical" : ratio < 0.4 ? "warning" : "none";
  return {
    level,
    label: level === "critical" ? "Low storage" : level === "warning" ? "Storage watch" : "",
    value: `${Math.round(ratio * 100)}% full`,
    radius: level === "critical" ? 74 : 58,
  };
}

function flowStress(value: number, periods: PeriodResult[]) {
  const max = Math.max(1, ...periods.map((period) => period.totalBasinExitFlow));
  const ratio = value / max;
  const level = stressLevel(ratio);
  return {
    level,
    label: level === "critical" ? "Low downstream flow" : level === "warning" ? "Reduced downstream flow" : "",
    value: `${Math.round(ratio * 100)}% of best period`,
  };
}

function stressLevel(ratio: number): "none" | "warning" | "critical" {
  if (ratio < 0.75) return "critical";
  if (ratio < 0.97) return "warning";
  return "none";
}

function MetricStack({ period }: { period: PeriodResult }) {
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

function edgeStops(
  lens: Lens,
  edge: NileEdge,
  result: EdgePeriodResult | undefined,
  periods: PeriodResult[],
) {
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

function edgeLabel(
  lens: Lens,
  edge: NileEdge,
  result: EdgePeriodResult | undefined,
  periods: PeriodResult[],
) {
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
    return 5;
  }

  return 4 + (result.totalRoutedFlow / max) * 15;
}

function nodeRadius(node: NileNode, result: NodePeriodResult | undefined, max: number) {
  if (!result) {
    return node.kind === "reservoir" ? 15 : 11;
  }

  return (node.kind === "reservoir" ? 13 : 9) + (result.totalAvailableWater / max) * 10;
}

function nodeFill(
  lens: Lens,
  node: NileNode,
  result: NodePeriodResult | undefined,
  periods: PeriodResult[],
) {
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

function readPageFromHash(): SitePage {
  const raw = window.location.hash.replace(/^#\/?/, "");
  return sitePages.some((item) => item.id === raw) ? (raw as SitePage) : "visualization";
}

export default App;
