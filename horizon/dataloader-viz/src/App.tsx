import { useMemo, useState, type ChangeEvent } from "react";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Database,
  FileUp,
  GitBranch,
  Layers3,
  RefreshCcw,
  Search,
  TableProperties,
} from "lucide-react";
import { parseBundle, readCsvBundleFromFiles } from "./csv";
import { sampleBundleFiles } from "./sampleBundle";
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
        <div className="title-block">
          <p>Dataloader Tool</p>
          <h1>Bundle Visualizer</h1>
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
