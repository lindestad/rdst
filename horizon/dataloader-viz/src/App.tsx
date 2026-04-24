import { useMemo, useState, type ChangeEvent } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  Database,
  FileUp,
  GitBranch,
  LayoutGrid,
  Layers3,
  Plus,
  RefreshCcw,
  Search,
  TableProperties,
} from "lucide-react";
import { parseBundle, readCsvBundleFromFiles } from "./csv";
import { sampleBundleFiles } from "./sampleBundle";
import { visualizers, type VisualizerDefinition, type VisualizerId } from "./visualizers";
import type {
  DataloaderBundle,
  Diagnostic,
  EdgeRow,
  EntityType,
  GraphEdge,
  GraphNode,
  MetricSummary,
  NodeRow,
  TimeSeriesRow,
} from "./types";

const viewBox = { width: 1040, height: 680, padding: 58 };

const sampleBundle = parseBundle("Sample Nile normalized bundle", sampleBundleFiles);

function App() {
  const [activeVisualizerId, setActiveVisualizerId] = useState<VisualizerId | null>(null);
  const activeVisualizer = visualizers.find((visualizer) => visualizer.id === activeVisualizerId);

  if (!activeVisualizer) {
    return <VisualizerHome onOpen={setActiveVisualizerId} />;
  }

  if (activeVisualizer.id === "source-coverage") {
    return <SourceCoverageVisualizer onBack={() => setActiveVisualizerId(null)} visualizer={activeVisualizer} />;
  }

  return <BundleVisualizer onBack={() => setActiveVisualizerId(null)} visualizer={activeVisualizer} />;
}

function BundleVisualizer({ onBack, visualizer }: { onBack: () => void; visualizer: VisualizerDefinition }) {
  const [bundle, setBundle] = useState<DataloaderBundle>(sampleBundle);
  const [loadError, setLoadError] = useState("");
  const [selectedMetric, setSelectedMetric] = useState("");
  const [selectedWindow, setSelectedWindow] = useState("");
  const [selectedEntityKey, setSelectedEntityKey] = useState("node:gerd");
  const [query, setQuery] = useState("");

  const model = useMemo(() => buildModel(bundle, selectedMetric, selectedWindow), [bundle, selectedMetric, selectedWindow]);
  const activeMetric = selectedMetric || model.metricSummaries[0]?.metric || "";
  const activeWindow = selectedWindow || model.windows[0] || "";
  const activeModel = useMemo(() => buildModel(bundle, activeMetric, activeWindow), [bundle, activeMetric, activeWindow]);
  const selectedEntity = getSelectedEntity(selectedEntityKey, activeModel.nodes, activeModel.edges);

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files?.length) {
      return;
    }

    try {
      const csvBundle = await readCsvBundleFromFiles(files);
      const nextBundle = parseBundle("Uploaded CSV bundle", csvBundle);
      setBundle(nextBundle);
      setLoadError("");
      setSelectedMetric("");
      setSelectedWindow("");
      setSelectedEntityKey(`node:${nextBundle.nodes[0]?.node_id ?? ""}`);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load the CSV bundle.");
    } finally {
      event.target.value = "";
    }
  }

  const filteredRows = activeModel.filteredRows.filter((row) => {
    const haystack = [row.entity_type, row.entity_id, row.metric, row.source_name, row.quality_flag].join(" ").toLowerCase();
    return haystack.includes(query.toLowerCase());
  });

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="title-row">
          <button className="icon-shell" onClick={onBack} title="Back to visualizers" type="button">
            <ArrowLeft size={18} />
          </button>
          <div className="title-block">
            <p>{visualizer.eyebrow}</p>
            <h1>{visualizer.name}</h1>
          </div>
        </div>
        <div className="top-actions">
          <label className="upload-button" title="Load nodes.csv, edges.csv, and time_series.csv">
            <FileUp size={18} />
            <span>Load CSVs</span>
            <input accept=".csv,text/csv" multiple onChange={handleFiles} type="file" />
          </label>
          <button className="ghost-button" onClick={() => setBundle(sampleBundle)} title="Reload sample bundle" type="button">
            <RefreshCcw size={17} />
            <span>Sample</span>
          </button>
        </div>
      </header>

      {loadError ? (
        <div className="error-strip">
          <AlertTriangle size={16} />
          <span>{loadError}</span>
        </div>
      ) : null}

      <section className="workspace">
        <aside className="left-rail" aria-label="Bundle controls">
          <section className="panel">
            <PanelHeading icon={<Database size={17} />} label="Bundle" />
            <div className="stat-grid">
              <Stat label="Nodes" value={bundle.nodes.length.toString()} />
              <Stat label="Edges" value={bundle.edges.length.toString()} />
              <Stat label="Series rows" value={bundle.timeSeries.length.toString()} />
              <Stat label="Scenarios" value={activeModel.scenarios.length.toString()} />
            </div>
          </section>

          <section className="panel">
            <PanelHeading icon={<Layers3 size={17} />} label="Lens" />
            <label className="field">
              <span>Metric</span>
              <select onChange={(event) => setSelectedMetric(event.target.value)} value={activeMetric}>
                {activeModel.metricSummaries.map((summary) => (
                  <option key={summary.metric} value={summary.metric}>
                    {summary.metric}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Window</span>
              <select onChange={(event) => setSelectedWindow(event.target.value)} value={activeWindow}>
                {activeModel.windows.map((window) => (
                  <option key={window} value={window}>
                    {window}
                  </option>
                ))}
              </select>
            </label>
          </section>

          <section className="panel diagnostics-panel">
            <PanelHeading icon={<CheckCircle2 size={17} />} label="Diagnostics" />
            <div className="diagnostic-list">
              {activeModel.diagnostics.map((diagnostic) => (
                <div className={`diagnostic ${diagnostic.severity}`} key={diagnostic.label}>
                  <strong>{diagnostic.label}</strong>
                  <span>{diagnostic.detail}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <PanelHeading icon={<BarChart3 size={17} />} label="Metrics" />
            <div className="metric-list">
              {activeModel.metricSummaries.map((summary) => (
                <button
                  className={summary.metric === activeMetric ? "metric-row active" : "metric-row"}
                  key={summary.metric}
                  onClick={() => setSelectedMetric(summary.metric)}
                  type="button"
                >
                  <span>{summary.metric}</span>
                  <strong>{summary.rows}</strong>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className="canvas-area" aria-label="Dataloader graph visualization">
          <div className="map-toolbar">
            <div>
              <p>{bundle.sourceLabel}</p>
              <h2>{activeMetric || "No metric selected"}</h2>
            </div>
            <div className="toolbar-summary">
              <span>{activeWindow || "No interval"}</span>
              <strong>{activeModel.activeUnit || "unit unknown"}</strong>
            </div>
          </div>

          <svg className="network-map" viewBox={`0 0 ${viewBox.width} ${viewBox.height}`} role="img" aria-label="Normalized dataloader graph">
            <defs>
              <filter id="nodeShadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="5" floodColor="#1d2c33" floodOpacity="0.25" stdDeviation="5" />
              </filter>
            </defs>
            <g className="basin-shape">
              <path d="M214 82 C352 112 494 172 612 284 C744 410 855 490 942 570" />
              <path d="M166 628 C280 578 374 588 480 532 C618 460 702 444 842 468" />
            </g>
            <g className="edge-layer">
              {activeModel.edges.map((edge) => (
                <g key={edge.edge_id}>
                  <path className="edge-hit" d={edge.path} onClick={() => setSelectedEntityKey(`edge:${edge.edge_id}`)} />
                  <path
                    className={selectedEntityKey === `edge:${edge.edge_id}` ? "edge-line selected" : "edge-line"}
                    d={edge.path}
                    onClick={() => setSelectedEntityKey(`edge:${edge.edge_id}`)}
                    stroke={valueColor(edge.value, activeModel.valueExtent)}
                    strokeWidth={edgeWidth(edge.value, activeModel.valueExtent)}
                  />
                </g>
              ))}
            </g>
            <g className="node-layer">
              {activeModel.nodes.map((node) => (
                <g
                  className={selectedEntityKey === `node:${node.node_id}` ? "node selected" : "node"}
                  key={node.node_id}
                  onClick={() => setSelectedEntityKey(`node:${node.node_id}`)}
                  transform={`translate(${node.x} ${node.y})`}
                >
                  <circle className="node-glow" r={nodeRadius(node.value, activeModel.valueExtent) + 12} />
                  <circle
                    className="node-body"
                    fill={valueColor(node.value, activeModel.valueExtent, node.node_kind === "reservoir")}
                    r={nodeRadius(node.value, activeModel.valueExtent)}
                  />
                  <circle className="node-ring" r={nodeRadius(node.value, activeModel.valueExtent) + 4} />
                  <text className="node-label" y={nodeRadius(node.value, activeModel.valueExtent) + 25}>
                    {shortName(node.name || node.node_id)}
                  </text>
                  <text className="node-meta" y={nodeRadius(node.value, activeModel.valueExtent) + 41}>
                    {node.country_code || node.node_kind}
                  </text>
                </g>
              ))}
            </g>
          </svg>

          <div className="timeline-panel">
            <PanelHeading icon={<BarChart3 size={17} />} label="Metric Timeline" />
            <div className="timeline-bars">
              {activeModel.timeline.map((bar) => (
                <button
                  className={bar.window === activeWindow ? "timeline-bar active" : "timeline-bar"}
                  key={bar.window}
                  onClick={() => setSelectedWindow(bar.window)}
                  title={`${bar.window}: ${formatNumber(bar.total)}`}
                  type="button"
                >
                  <i style={{ height: `${Math.max(10, bar.percent)}%` }} />
                  <span>{bar.label}</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <aside className="right-rail" aria-label="Details and rows">
          <section className="panel inspector">
            <PanelHeading icon={<GitBranch size={17} />} label="Selection" />
            {selectedEntity ? <EntityInspector entity={selectedEntity} metric={activeMetric} /> : <p className="empty-note">Select a node or reach.</p>}
          </section>

          <section className="panel">
            <PanelHeading icon={<Search size={17} />} label="Series Rows" />
            <label className="search-box">
              <Search size={15} />
              <input onChange={(event) => setQuery(event.target.value)} placeholder="Filter rows" value={query} />
            </label>
            <div className="row-table" role="table" aria-label="Filtered time series rows">
              {filteredRows.slice(0, 36).map((row, index) => (
                <button
                  className="series-row"
                  key={`${row.entity_type}-${row.entity_id}-${row.metric}-${row.interval_start}-${index}`}
                  onClick={() => setSelectedEntityKey(`${row.entity_type}:${row.entity_id}`)}
                  type="button"
                >
                  <span>{row.entity_id}</span>
                  <strong>{formatNumber(toNumber(row.value))}</strong>
                  <em>{row.quality_flag || "unflagged"}</em>
                </button>
              ))}
            </div>
          </section>

          <section className="panel coverage-panel">
            <PanelHeading icon={<TableProperties size={17} />} label="Coverage" />
            {activeModel.metricSummaries.slice(0, 8).map((summary) => (
              <div className="coverage-row" key={summary.metric}>
                <span>{summary.metric}</span>
                <strong>{summary.entities} entities</strong>
                <em>{summary.sources.join(", ") || "unknown source"}</em>
              </div>
            ))}
          </section>
        </aside>
      </section>
    </main>
  );
}

function SourceCoverageVisualizer({ onBack, visualizer }: { onBack: () => void; visualizer: VisualizerDefinition }) {
  const [bundle, setBundle] = useState<DataloaderBundle>(sampleBundle);
  const [loadError, setLoadError] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [selectedMetric, setSelectedMetric] = useState("");

  const model = useMemo(() => buildCoverageModel(bundle), [bundle]);
  const activeSource = selectedSource || model.sources[0] || "";
  const activeMetric = selectedMetric || model.metrics[0] || "";
  const activeCell = model.cells.get(coverageKey(activeSource, activeMetric));
  const sourceRows = bundle.timeSeries.filter((row) => sourceName(row) === activeSource);

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    if (!files?.length) {
      return;
    }

    try {
      const csvBundle = await readCsvBundleFromFiles(files);
      const nextBundle = parseBundle("Uploaded CSV bundle", csvBundle);
      setBundle(nextBundle);
      setLoadError("");
      setSelectedSource("");
      setSelectedMetric("");
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load the CSV bundle.");
    } finally {
      event.target.value = "";
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="title-row">
          <button className="icon-shell" onClick={onBack} title="Back to visualizers" type="button">
            <ArrowLeft size={18} />
          </button>
          <div className="title-block">
            <p>{visualizer.eyebrow}</p>
            <h1>{visualizer.name}</h1>
          </div>
        </div>
        <div className="top-actions">
          <label className="upload-button" title="Load nodes.csv, edges.csv, and time_series.csv">
            <FileUp size={18} />
            <span>Load CSVs</span>
            <input accept=".csv,text/csv" multiple onChange={handleFiles} type="file" />
          </label>
          <button className="ghost-button" onClick={() => setBundle(sampleBundle)} title="Reload sample bundle" type="button">
            <RefreshCcw size={17} />
            <span>Sample</span>
          </button>
        </div>
      </header>

      {loadError ? (
        <div className="error-strip">
          <AlertTriangle size={16} />
          <span>{loadError}</span>
        </div>
      ) : null}

      <section className="coverage-workspace">
        <aside className="coverage-sidebar" aria-label="Coverage filters">
          <section className="panel">
            <PanelHeading icon={<Database size={17} />} label="Coverage" />
            <div className="stat-grid">
              <Stat label="Sources" value={model.sources.length.toString()} />
              <Stat label="Metrics" value={model.metrics.length.toString()} />
              <Stat label="Flagged rows" value={model.flaggedRows.toString()} />
              <Stat label="Units" value={model.units.length.toString()} />
            </div>
          </section>

          <section className="panel">
            <PanelHeading icon={<TableProperties size={17} />} label="Sources" />
            <div className="source-list">
              {model.sourceSummaries.map((summary) => (
                <button
                  className={summary.source === activeSource ? "source-button active" : "source-button"}
                  key={summary.source}
                  onClick={() => setSelectedSource(summary.source)}
                  type="button"
                >
                  <span>{summary.source}</span>
                  <strong>{summary.rows}</strong>
                  <em>{summary.metrics} metrics / {summary.entities} entities</em>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className="coverage-main" aria-label="Source coverage matrix">
          <div className="coverage-title">
            <div>
              <p>{bundle.sourceLabel}</p>
              <h2>Sources by normalized metric</h2>
            </div>
            <div className="coverage-legend">
              <span className="legend-full">Covered</span>
              <span className="legend-warn">QA review</span>
              <span className="legend-empty">Missing</span>
            </div>
          </div>

          <div className="matrix-scroll">
            <div className="coverage-matrix" style={{ gridTemplateColumns: `220px repeat(${Math.max(1, model.metrics.length)}, minmax(132px, 1fr))` }}>
              <div className="matrix-corner">Source</div>
              {model.metrics.map((metric) => (
                <button
                  className={metric === activeMetric ? "matrix-heading active" : "matrix-heading"}
                  key={metric}
                  onClick={() => setSelectedMetric(metric)}
                  title={metric}
                  type="button"
                >
                  {metric}
                </button>
              ))}
              {model.sources.map((source) => (
                <CoverageMatrixRow
                  activeMetric={activeMetric}
                  activeSource={activeSource}
                  cells={model.cells}
                  key={source}
                  metrics={model.metrics}
                  onSelect={(nextSource, nextMetric) => {
                    setSelectedSource(nextSource);
                    setSelectedMetric(nextMetric);
                  }}
                  source={source}
                />
              ))}
            </div>
          </div>
        </section>

        <aside className="coverage-detail" aria-label="Coverage detail">
          <section className="panel inspector">
            <PanelHeading icon={<Search size={17} />} label="Selected Cell" />
            {activeCell ? (
              <div className="entity-details">
                <h2>{activeSource}</h2>
                <dl className="detail-grid">
                  <Detail label="Metric" value={activeMetric} />
                  <Detail label="Rows" value={activeCell.rows.toString()} />
                  <Detail label="Entities" value={activeCell.entities.toString()} />
                  <Detail label="Flags" value={activeCell.flaggedRows.toString()} />
                </dl>
                <div className="unit-strip">
                  {activeCell.units.map((unit) => (
                    <span key={unit}>{unit}</span>
                  ))}
                </div>
              </div>
            ) : (
              <p className="empty-note">No rows for this source and metric.</p>
            )}
          </section>

          <section className="panel">
            <PanelHeading icon={<GitBranch size={17} />} label="Source Entities" />
            <div className="entity-chip-list">
              {unique(sourceRows.map((row) => `${row.entity_type}:${row.entity_id}`)).slice(0, 28).map((entity) => (
                <span key={entity}>{entity}</span>
              ))}
            </div>
          </section>

          <section className="panel">
            <PanelHeading icon={<CheckCircle2 size={17} />} label="QA Rows" />
            <div className="row-table compact-table">
              {sourceRows
                .filter((row) => row.quality_flag && !["ok", "pass", "valid"].includes(row.quality_flag.toLowerCase()))
                .slice(0, 18)
                .map((row, index) => (
                  <button className="series-row" key={`${row.entity_id}-${row.metric}-${index}`} onClick={() => setSelectedMetric(row.metric)} type="button">
                    <span>{row.metric}</span>
                    <strong>{row.quality_flag}</strong>
                    <em>{row.entity_id}</em>
                  </button>
                ))}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

function CoverageMatrixRow({
  activeMetric,
  activeSource,
  cells,
  metrics,
  onSelect,
  source,
}: {
  activeMetric: string;
  activeSource: string;
  cells: Map<string, CoverageCell>;
  metrics: string[];
  onSelect: (source: string, metric: string) => void;
  source: string;
}) {
  return (
    <>
      <button className={source === activeSource ? "matrix-source active" : "matrix-source"} onClick={() => onSelect(source, activeMetric)} type="button">
        {source}
      </button>
      {metrics.map((metric) => {
        const cell = cells.get(coverageKey(source, metric));
        const isActive = source === activeSource && metric === activeMetric;
        const className = ["matrix-cell", cell ? "covered" : "empty", cell?.flaggedRows ? "warn" : "", isActive ? "active" : ""].filter(Boolean).join(" ");
        return (
          <button className={className} key={`${source}-${metric}`} onClick={() => onSelect(source, metric)} type="button">
            <strong>{cell?.rows ?? 0}</strong>
            <span>{cell ? `${cell.entities} entities` : "missing"}</span>
          </button>
        );
      })}
    </>
  );
}

function VisualizerHome({ onOpen }: { onOpen: (id: VisualizerId) => void }) {
  return (
    <main className="home-shell">
      <header className="home-header">
        <div className="title-block">
          <p>Horizon Dataloader</p>
          <h1>Visualization Console</h1>
        </div>
        <div className="home-status">
          <LayoutGrid size={17} />
          <span>{visualizers.length} ready visualizer</span>
        </div>
      </header>

      <section className="home-stage" aria-label="Available visualizers">
        <div className="home-intro">
          <h2>Select a data view</h2>
          <p>Each visualizer is a focused surface for one normalized data shape. We can add more cards here as new dataloader outputs become real.</p>
        </div>

        <div className="visualizer-grid">
          {visualizers.map((visualizer) => (
            <VisualizerCard key={visualizer.id} onOpen={onOpen} visualizer={visualizer} />
          ))}
          <article className="visualizer-card planned-card" aria-label="Future visualizer slot">
            <div className="planned-preview">
              <Plus size={26} />
            </div>
            <div className="visualizer-copy">
              <p>Next slot</p>
              <h3>Future Dataset View</h3>
              <span>Reserved for raster QA, source inventories, scenario assembly, or optimizer traces.</span>
            </div>
          </article>
        </div>
      </section>
    </main>
  );
}

function VisualizerCard({ onOpen, visualizer }: { onOpen: (id: VisualizerId) => void; visualizer: VisualizerDefinition }) {
  return (
    <button className="visualizer-card" onClick={() => onOpen(visualizer.id)} type="button">
      <VisualizerPreview visualizer={visualizer} />
      <div className="visualizer-copy">
        <p>{visualizer.eyebrow}</p>
        <h3>{visualizer.name}</h3>
        <span>{visualizer.summary}</span>
      </div>
      <div className="visualizer-stats">
        {visualizer.stats.map((stat) => (
          <div key={stat.label}>
            <strong>{stat.value}</strong>
            <span>{stat.label}</span>
          </div>
        ))}
      </div>
      <div className="open-visualizer">
        <span>Open</span>
        <ChevronRight size={17} />
      </div>
    </button>
  );
}

function VisualizerPreview({ visualizer }: { visualizer: VisualizerDefinition }) {
  if (visualizer.id === "source-coverage") {
    return (
      <svg className="visualizer-preview source-preview" viewBox="0 0 320 180" role="img" aria-label={`${visualizer.name} preview`}>
        <defs>
          <linearGradient id="sourcePreviewHeat" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#47c7bd" />
            <stop offset="100%" stopColor="#d7a84b" />
          </linearGradient>
        </defs>
        <rect className="preview-backdrop" x="0" y="0" width="320" height="180" rx="8" />
        <rect className="preview-panel" x="18" y="20" width="284" height="138" rx="7" />
        <g className="preview-labels">
          <rect x="35" y="42" width="56" height="7" rx="3" />
          <rect x="35" y="75" width="72" height="7" rx="3" />
          <rect x="35" y="108" width="48" height="7" rx="3" />
          <rect x="128" y="32" width="36" height="6" rx="3" />
          <rect x="178" y="32" width="42" height="6" rx="3" />
          <rect x="234" y="32" width="34" height="6" rx="3" />
        </g>
        <g className="preview-heatmap">
          <rect x="128" y="52" width="34" height="24" rx="5" />
          <rect x="178" y="52" width="34" height="24" rx="5" />
          <rect x="234" y="52" width="34" height="24" rx="5" className="soft" />
          <rect x="128" y="85" width="34" height="24" rx="5" className="warn" />
          <rect x="178" y="85" width="34" height="24" rx="5" className="soft" />
          <rect x="234" y="85" width="34" height="24" rx="5" />
          <rect x="128" y="118" width="34" height="24" rx="5" className="empty" />
          <rect x="178" y="118" width="34" height="24" rx="5" />
          <rect x="234" y="118" width="34" height="24" rx="5" className="warn" />
        </g>
      </svg>
    );
  }

  return (
    <svg className="visualizer-preview network-preview" viewBox="0 0 320 180" role="img" aria-label={`${visualizer.name} preview`}>
      <defs>
        <linearGradient id="networkPreviewFlow" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="#6aa9d8" />
          <stop offset="55%" stopColor="#47c7bd" />
          <stop offset="100%" stopColor="#71c586" />
        </linearGradient>
      </defs>
      <rect className="preview-backdrop" x="0" y="0" width="320" height="180" rx="8" />
      <path className="preview-basin" d="M35 134 C92 98 122 118 165 78 C206 40 255 58 288 86" />
      <path className="preview-edge wide" d="M50 128 C84 106 100 110 122 92" />
      <path className="preview-edge" d="M122 92 C148 78 162 80 184 102" />
      <path className="preview-edge wide" d="M184 102 C214 124 242 96 270 84" />
      <g className="preview-node-cluster">
        <circle cx="50" cy="128" r="12" />
        <circle cx="122" cy="92" r="16" className="reservoir" />
        <circle cx="184" cy="102" r="11" />
        <circle cx="270" cy="84" r="15" className="reservoir" />
      </g>
      <g className="preview-metrics">
        <rect x="28" y="24" width="58" height="8" rx="4" />
        <rect x="28" y="40" width="38" height="8" rx="4" />
        <rect x="222" y="134" width="62" height="8" rx="4" />
        <rect x="242" y="150" width="42" height="8" rx="4" />
      </g>
    </svg>
  );
}

function PanelHeading({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="panel-heading">
      {icon}
      <h3>{label}</h3>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EntityInspector({ entity, metric }: { entity: GraphNode | GraphEdge; metric: string }) {
  const id = "node_id" in entity ? entity.node_id : entity.edge_id;
  const label = "node_id" in entity ? entity.name || entity.node_id : `${entity.from_node_id} -> ${entity.to_node_id}`;
  const kind = "node_id" in entity ? entity.node_kind : "reach";
  const value = entity.value;
  const rows = entity.seriesRows.filter((row) => row.metric === metric);

  return (
    <div className="entity-details">
      <h2>{label}</h2>
      <dl className="detail-grid">
        <Detail label="ID" value={id} />
        <Detail label="Kind" value={kind} />
        <Detail label="Value" value={value === null ? "No row" : formatNumber(value)} />
        <Detail label="Rows" value={entity.seriesRows.length.toString()} />
      </dl>
      <div className="provenance-list">
        {rows.slice(0, 5).map((row) => (
          <div className="provenance" key={`${row.interval_start}-${row.metric}-${row.source_name}`}>
            <strong>{row.interval_start}</strong>
            <span>{row.source_name || "unknown source"}</span>
            <em>{row.transform || "no transform noted"}</em>
          </div>
        ))}
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

type CoverageCell = {
  source: string;
  metric: string;
  rows: number;
  entities: number;
  flaggedRows: number;
  units: string[];
};

function buildCoverageModel(bundle: DataloaderBundle) {
  const sources = unique(bundle.timeSeries.map(sourceName)).sort((a, b) => a.localeCompare(b));
  const metrics = unique(bundle.timeSeries.map((row) => row.metric).filter(Boolean)).sort((a, b) => a.localeCompare(b));
  const units = unique(bundle.timeSeries.map((row) => row.unit).filter(Boolean)).sort((a, b) => a.localeCompare(b));
  const cells = new Map<string, CoverageCell>();

  sources.forEach((source) => {
    metrics.forEach((metric) => {
      const rows = bundle.timeSeries.filter((row) => sourceName(row) === source && row.metric === metric);
      if (!rows.length) {
        return;
      }

      cells.set(coverageKey(source, metric), {
        source,
        metric,
        rows: rows.length,
        entities: unique(rows.map((row) => `${row.entity_type}:${row.entity_id}`)).length,
        flaggedRows: rows.filter(isReviewRow).length,
        units: unique(rows.map((row) => row.unit).filter(Boolean)),
      });
    });
  });

  return {
    cells,
    flaggedRows: bundle.timeSeries.filter(isReviewRow).length,
    metrics,
    sources,
    sourceSummaries: sources.map((source) => {
      const rows = bundle.timeSeries.filter((row) => sourceName(row) === source);
      return {
        source,
        rows: rows.length,
        metrics: unique(rows.map((row) => row.metric)).length,
        entities: unique(rows.map((row) => `${row.entity_type}:${row.entity_id}`)).length,
      };
    }),
    units,
  };
}

function buildModel(bundle: DataloaderBundle, metricPreference: string, windowPreference: string) {
  const metricSummaries = summarizeMetrics(bundle.timeSeries);
  const metric = metricPreference || metricSummaries[0]?.metric || "";
  const windows = unique(bundle.timeSeries.map((row) => row.interval_start && row.interval_end ? `${row.interval_start} to ${row.interval_end}` : "undated"));
  const window = windowPreference || windows[0] || "";
  const filteredRows = bundle.timeSeries.filter((row) => row.metric === metric && rowWindow(row) === window);
  const rowMap = new Map(filteredRows.map((row) => [`${row.entity_type}:${row.entity_id}`, row]));
  const allRowsByEntity = groupRows(bundle.timeSeries);
  const nodePositions = positionNodes(bundle.nodes);

  const nodes: GraphNode[] = bundle.nodes.map((node) => ({
    ...node,
    ...nodePositions.get(node.node_id),
    value: valueFor(rowMap.get(`node:${node.node_id}`)),
    seriesRows: allRowsByEntity.get(`node:${node.node_id}`) ?? [],
  })) as GraphNode[];

  const nodesById = new Map(nodes.map((node) => [node.node_id, node]));
  const edges: GraphEdge[] = bundle.edges.map((edge) => {
    const from = nodesById.get(edge.from_node_id);
    const to = nodesById.get(edge.to_node_id);
    return {
      ...edge,
      path: edgePath(from, to),
      value: valueFor(rowMap.get(`edge:${edge.edge_id}`)),
      seriesRows: allRowsByEntity.get(`edge:${edge.edge_id}`) ?? [],
    };
  });

  const values = [...nodes.map((node) => node.value), ...edges.map((edge) => edge.value)].filter((value): value is number => value !== null);
  const valueExtent = Math.max(1, ...values.map((value) => Math.abs(value)));
  const activeSummary = metricSummaries.find((summary) => summary.metric === metric);

  return {
    activeUnit: activeSummary?.unit ?? "",
    diagnostics: buildDiagnostics(bundle),
    edges,
    filteredRows,
    metricSummaries,
    nodes,
    scenarios: unique([...bundle.nodes, ...bundle.edges, ...bundle.timeSeries].map((row) => row.scenario_id).filter(Boolean)),
    timeline: buildTimeline(bundle.timeSeries, metric),
    valueExtent,
    windows,
  };
}

function sourceName(row: TimeSeriesRow) {
  return row.source_name || "Unknown source";
}

function coverageKey(source: string, metric: string) {
  return `${source}::${metric}`;
}

function isReviewRow(row: TimeSeriesRow) {
  return Boolean(row.quality_flag && !["ok", "pass", "valid"].includes(row.quality_flag.toLowerCase()));
}

function summarizeMetrics(rows: TimeSeriesRow[]): MetricSummary[] {
  return unique(rows.map((row) => row.metric).filter(Boolean))
    .map((metric) => {
      const metricRows = rows.filter((row) => row.metric === metric);
      const values = metricRows.map((row) => toNumber(row.value)).filter((value) => Number.isFinite(value));
      return {
        metric,
        rows: metricRows.length,
        entities: unique(metricRows.map((row) => `${row.entity_type}:${row.entity_id}`)).length,
        unit: unique(metricRows.map((row) => row.unit).filter(Boolean))[0] ?? "",
        sources: unique(metricRows.map((row) => row.source_name).filter(Boolean)).slice(0, 3),
        min: Math.min(...values),
        max: Math.max(...values),
      };
    })
    .sort((a, b) => b.rows - a.rows);
}

function buildDiagnostics(bundle: DataloaderBundle): Diagnostic[] {
  const nodeIds = new Set(bundle.nodes.map((node) => node.node_id));
  const edgeIds = new Set(bundle.edges.map((edge) => edge.edge_id));
  const missingEdgeRefs = bundle.edges.filter((edge) => !nodeIds.has(edge.from_node_id) || !nodeIds.has(edge.to_node_id));
  const missingSeriesRefs = bundle.timeSeries.filter((row) => {
    if (row.entity_type === "node") {
      return !nodeIds.has(row.entity_id);
    }
    if (row.entity_type === "edge") {
      return !edgeIds.has(row.entity_id);
    }
    return true;
  });
  const nonNumeric = bundle.timeSeries.filter((row) => !Number.isFinite(toNumber(row.value)));
  const reviewFlags = bundle.timeSeries.filter((row) => row.quality_flag && !["ok", "pass", "valid"].includes(row.quality_flag.toLowerCase()));

  return [
    diagnostic("Topology refs", missingEdgeRefs.length, "edge endpoint issue", "All edges resolve to known nodes"),
    diagnostic("Series refs", missingSeriesRefs.length, "time-series reference issue", "All series rows resolve to known entities"),
    diagnostic("Numeric values", nonNumeric.length, "non-numeric value", "All metric values parse as numbers"),
    diagnostic("QA flags", reviewFlags.length, "row flagged for review", "No quality flags need review", "warn"),
  ];
}

function diagnostic(label: string, count: number, singular: string, okText: string, severity: Diagnostic["severity"] = "error"): Diagnostic {
  return {
    label,
    detail: count > 0 ? `${count} ${singular}${count === 1 ? "" : "s"}` : okText,
    severity: count > 0 ? severity : "ok",
  };
}

function buildTimeline(rows: TimeSeriesRow[], metric: string) {
  const totals = unique(rows.filter((row) => row.metric === metric).map(rowWindow)).map((window) => {
    const total = rows
      .filter((row) => row.metric === metric && rowWindow(row) === window)
      .reduce((sum, row) => sum + Math.max(0, toNumber(row.value)), 0);
    return { window, total };
  });
  const max = Math.max(1, ...totals.map((item) => item.total));

  return totals.map((item, index) => ({
    ...item,
    label: `T${index + 1}`,
    percent: (item.total / max) * 100,
  }));
}

function positionNodes(nodes: NodeRow[]) {
  const coordinates = nodes
    .map((node) => ({ node, lat: toNumber(node.latitude), lon: toNumber(node.longitude) }))
    .filter((item) => Number.isFinite(item.lat) && Number.isFinite(item.lon));
  const latValues = coordinates.map((item) => item.lat);
  const lonValues = coordinates.map((item) => item.lon);
  const minLat = Math.min(...latValues);
  const maxLat = Math.max(...latValues);
  const minLon = Math.min(...lonValues);
  const maxLon = Math.max(...lonValues);
  const positions = new Map<string, { x: number; y: number }>();

  nodes.forEach((node, index) => {
    const lat = toNumber(node.latitude);
    const lon = toNumber(node.longitude);
    if (Number.isFinite(lat) && Number.isFinite(lon) && maxLat !== minLat && maxLon !== minLon) {
      positions.set(node.node_id, {
        x: viewBox.padding + ((lon - minLon) / (maxLon - minLon)) * (viewBox.width - viewBox.padding * 2),
        y: viewBox.height - viewBox.padding - ((lat - minLat) / (maxLat - minLat)) * (viewBox.height - viewBox.padding * 2),
      });
      return;
    }

    positions.set(node.node_id, {
      x: viewBox.padding + (index / Math.max(1, nodes.length - 1)) * (viewBox.width - viewBox.padding * 2),
      y: viewBox.height / 2 + Math.sin(index * 0.9) * 180,
    });
  });

  return positions;
}

function groupRows(rows: TimeSeriesRow[]) {
  const grouped = new Map<string, TimeSeriesRow[]>();
  rows.forEach((row) => {
    const key = `${row.entity_type}:${row.entity_id}`;
    grouped.set(key, [...(grouped.get(key) ?? []), row]);
  });
  return grouped;
}

function getSelectedEntity(key: string, nodes: GraphNode[], edges: GraphEdge[]) {
  const [type, id] = key.split(":") as [EntityType, string];
  return type === "node" ? nodes.find((node) => node.node_id === id) : edges.find((edge) => edge.edge_id === id);
}

function edgePath(from: GraphNode | undefined, to: GraphNode | undefined) {
  if (!from || !to) {
    return "M 0 0";
  }
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const bend = Math.max(-80, Math.min(80, dx * 0.16));
  return `M ${from.x} ${from.y} C ${from.x + dx * 0.35} ${from.y + dy * 0.2 - bend}, ${from.x + dx * 0.65} ${from.y + dy * 0.8 + bend}, ${to.x} ${to.y}`;
}

function rowWindow(row: TimeSeriesRow) {
  return row.interval_start && row.interval_end ? `${row.interval_start} to ${row.interval_end}` : "undated";
}

function valueFor(row: TimeSeriesRow | undefined) {
  if (!row) {
    return null;
  }
  const value = toNumber(row.value);
  return Number.isFinite(value) ? value : null;
}

function valueColor(value: number | null, extent: number, reservoir = false) {
  if (value === null) {
    return reservoir ? "#8a805f" : "#77848b";
  }
  const ratio = Math.min(1, Math.abs(value) / extent);
  const hue = value >= 0 ? 184 - ratio * 52 : 18;
  const light = 48 - ratio * 16;
  return `hsl(${hue} 64% ${light}%)`;
}

function edgeWidth(value: number | null, extent: number) {
  if (value === null) {
    return 5;
  }
  return 6 + (Math.abs(value) / extent) * 18;
}

function nodeRadius(value: number | null, extent: number) {
  if (value === null) {
    return 20;
  }
  return 21 + (Math.abs(value) / extent) * 23;
}

function unique<T>(values: T[]) {
  return Array.from(new Set(values));
}

function toNumber(value: string | number | undefined) {
  if (typeof value === "number") {
    return value;
  }
  return Number(value ?? "");
}

function formatNumber(value: number) {
  if (!Number.isFinite(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: Math.abs(value) >= 100 ? 0 : 2 }).format(value);
}

function shortName(name: string) {
  return name
    .replace("Irrigation Scheme", "Irrigation")
    .replace("Municipal Demand", "Municipal")
    .replace("Headwaters", "Headwaters")
    .slice(0, 20);
}

export default App;
