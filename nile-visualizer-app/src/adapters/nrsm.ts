import { edges as fallbackEdges, nodes as fallbackNodes } from "../data/nileGraph";
import { pathBetweenNodes } from "../lib/geo";
import type {
  Delivery,
  EdgePeriodResult,
  Hydropower,
  Irrigation,
  NileEdge,
  NileNode,
  NodePeriodResult,
  PeriodResult,
  RunMetadata,
  VisualizerDataset,
} from "../types";

type RawGraph = {
  nodes?: Array<Partial<NileNode> & { id: string; label?: string; type?: string }>;
  edges?: Array<Partial<NileEdge> & { id?: string; from: string; to: string; fraction?: number }>;
};

type RawGraphNode = NonNullable<RawGraph["nodes"]>[number];
type RawGraphEdge = NonNullable<RawGraph["edges"]>[number];

type RawRustNodeResult = {
  node_id: string;
  reservoir_level?: number;
  production_release?: number;
  energy_value?: number;
  evaporation?: number;
  food_produced?: number;
  drink_water_met?: number;
  unmet_drink_water?: number;
  spill?: number;
  downstream_release?: number;
  total_inflow?: number;
};

type RawRustPeriod = {
  period_index?: number;
  start_day?: number;
  end_day_exclusive?: number;
  node_results?: RawRustNodeResult[];
};

type RawRustResult = {
  engine_time_step?: string;
  timestep_days?: number;
  reporting?: string;
  summary?: Record<string, number>;
  periods?: RawRustPeriod[];
};

type ResultCsvRow = {
  period_index: string;
  start_day: string;
  end_day_exclusive: string;
  duration_days: string;
  node_id?: string;
  reservoir_level?: string;
  total_inflow: string;
  evaporation?: string;
  drink_water_met?: string;
  unmet_drink_water?: string;
  food_produced?: string;
  production_release?: string;
  spill?: string;
  release_for_routing?: string;
  downstream_release: string;
  routing_loss?: string;
  energy_value?: string;
};

type RawVisualizerFile = {
  schema_version?: string;
  metadata?: Partial<RunMetadata>;
  scenario?: { name?: string };
  graph?: RawGraph;
  result?: RawRustResult;
  nodes?: VisualizerDataset["nodes"];
  edges?: VisualizerDataset["edges"];
  periods?: VisualizerDataset["periods"] | RawRustPeriod[];
};

const terminalKinds = new Set(["sink", "delta", "terminal"]);

export async function datasetFromFile(file: File): Promise<VisualizerDataset> {
  const text = await file.text();
  const parsed = JSON.parse(text) as unknown;
  return datasetFromUnknown(parsed, file.name);
}

export async function datasetFromCsvFiles(files: FileList | File[]): Promise<VisualizerDataset> {
  const fileArray = Array.from(files).filter((file) => file.name.toLowerCase().endsWith(".csv"));
  const nodeFiles = fileArray.filter((file) => file.name.toLowerCase() !== "summary.csv");
  if (nodeFiles.length === 0) {
    throw new Error("Select the node CSV files from an NRSM --results-dir output.");
  }

  const rowsByNode = new Map<string, ResultCsvRow[]>();
  for (const file of nodeFiles) {
    const rows = parseCsv(await file.text()) as ResultCsvRow[];
    const nodeId = rows.find((row) => row.node_id)?.node_id ?? file.name.replace(/\.csv$/i, "");
    rowsByNode.set(nodeId, rows);
  }

  return datasetFromCsvRows(selectNileMvpRows(rowsByNode), {
    name: "NRSM saved results",
    source: "results-dir CSV",
    reporting: "saved CSV",
  });
}

export function datasetFromCsvTextByNode(
  csvByNode: Record<string, string>,
  metadata: Partial<RunMetadata> = {},
): VisualizerDataset {
  const rowsByNode = new Map(
    Object.entries(csvByNode).map(([nodeId, content]) => [nodeId, parseCsv(content) as ResultCsvRow[]]),
  );
  return datasetFromCsvRows(rowsByNode, metadata);
}

function datasetFromCsvRows(
  rowsByNode: Map<string, ResultCsvRow[]>,
  metadata: Partial<RunMetadata> = {},
): VisualizerDataset {
  const resultNodes = Array.from(rowsByNode.keys());
  const nodes = normalizeNodes(
    fallbackNodes
      .filter((candidate) => resultNodes.includes(candidate.id))
      .map((candidate) => ({ ...candidate })),
    { periods: [] },
  );
  const known = new Set(nodes.map((candidate) => candidate.id));
  for (const id of resultNodes) {
    if (!known.has(id)) {
      nodes.push({
        id,
        name: titleFromId(id),
        shortName: shortName(id),
        kind: "river",
        ...fallbackPosition(nodes.length, resultNodes.length),
        country: "",
      });
    }
  }

  const edges = normalizeEdges(
    fallbackEdges.filter((candidate) => known.has(candidate.from) && known.has(candidate.to)),
    nodes,
  );
  const periodIndexes = Array.from(
    new Set(Array.from(rowsByNode.values()).flatMap((rows) => rows.map((row) => numberFrom(row.period_index)))),
  ).sort((a, b) => a - b);
  const periods = periodIndexes.map((periodIndex, index) => {
    return csvRowsToPeriod(periodIndex, index, nodes, edges, rowsByNode);
  });

  return {
    metadata: {
      name: metadata.name ?? "NRSM saved results",
      source: metadata.source ?? "results-dir CSV",
      horizon: metadata.horizon ?? `${periods.length} reporting periods`,
      reporting: metadata.reporting ?? "saved CSV",
      units: metadata.units ?? "model units per reporting period",
    },
    nodes,
    edges,
    periods,
  };
}

function selectNileMvpRows(rowsByNode: Map<string, ResultCsvRow[]>) {
  const fallbackIds = new Set(fallbackNodes.map((node) => node.id));
  const matchingRows = new Map(
    Array.from(rowsByNode.entries()).filter(([nodeId]) => fallbackIds.has(nodeId)),
  );

  return matchingRows.size >= 6 && matchingRows.size < rowsByNode.size ? matchingRows : rowsByNode;
}

export function datasetFromUnknown(input: unknown, source = "Uploaded file"): VisualizerDataset {
  if (!isRecord(input)) {
    throw new Error("Simulator output must be a JSON object.");
  }

  const payload = input as RawVisualizerFile;
  if (looksLikeVisualizerDataset(payload)) {
    return normalizeVisualizerDataset(payload as VisualizerDataset, source);
  }

  const rustResult = payload.result ?? (looksLikeRustResult(payload) ? (payload as RawRustResult) : null);
  if (!rustResult) {
    throw new Error("Expected either a VisualizerDataset or an NRSM Rust SimulationResult.");
  }

  return datasetFromRustResult(rustResult, {
    graph: payload.graph,
    metadata: {
      name: payload.metadata?.name ?? payload.scenario?.name ?? "NRSM simulator run",
      source,
      horizon: payload.metadata?.horizon,
      reporting: payload.metadata?.reporting,
      units: payload.metadata?.units,
    },
  });
}

export function datasetFromRustResult(
  result: RawRustResult,
  options: { graph?: RawGraph; metadata?: Partial<RunMetadata> } = {},
): VisualizerDataset {
  if (!Array.isArray(result.periods) || result.periods.length === 0) {
    throw new Error("NRSM result has no periods.");
  }

  const nodes = normalizeNodes(options.graph?.nodes, result);
  const edges = normalizeEdges(options.graph?.edges, nodes);
  const periods = result.periods.map((period, index) => {
    return rustPeriodToVisualizerPeriod(period, index, nodes, edges);
  });

  const timestep = result.timestep_days ? `${result.timestep_days} day timestep` : "daily engine";
  const metadata: RunMetadata = {
    name: options.metadata?.name ?? "NRSM simulator run",
    source: options.metadata?.source ?? "NRSM JSON",
    horizon: options.metadata?.horizon ?? `${periods.length} reporting periods`,
    reporting: options.metadata?.reporting ?? `${result.reporting ?? "raw"} / ${timestep}`,
    units: options.metadata?.units ?? "model units per reporting period",
  };

  return { metadata, nodes, edges, periods };
}

function normalizeVisualizerDataset(dataset: VisualizerDataset, source: string): VisualizerDataset {
  if (!dataset.nodes?.length || !dataset.edges?.length || !dataset.periods?.length) {
    throw new Error("VisualizerDataset requires nodes, edges, and periods.");
  }

  return {
    metadata: {
      name: dataset.metadata?.name ?? "Simulator run",
      source: dataset.metadata?.source ?? source,
      horizon: dataset.metadata?.horizon ?? `${dataset.periods.length} periods`,
      reporting: dataset.metadata?.reporting ?? "periodic",
      units: dataset.metadata?.units ?? "model units",
    },
    nodes: dataset.nodes,
    edges: dataset.edges,
    periods: dataset.periods,
  };
}

function normalizeNodes(rawNodes: RawGraph["nodes"], result: RawRustResult): NileNode[] {
  const periodNodeIds = new Set(
    result.periods?.flatMap((period) => period.node_results?.map((node) => node.node_id) ?? []) ?? [],
  );

  const byId = new Map(fallbackNodes.map((node) => [node.id, node]));
  const source: RawGraphNode[] = rawNodes?.length
    ? rawNodes
    : Array.from(periodNodeIds).map((id) => byId.get(id) ?? { id });

  return source.map((raw, index) => {
    const fallback = byId.get(raw.id);
    const position = fallback ?? fallbackPosition(index, source.length);
    const kind = normalizeKind(raw.kind ?? raw.type ?? fallback?.kind);
    return {
      id: raw.id,
      name: raw.name ?? raw.label ?? fallback?.name ?? titleFromId(raw.id),
      shortName: raw.shortName ?? fallback?.shortName ?? shortName(raw.name ?? raw.label ?? raw.id),
      kind,
      x: raw.x ?? position.x,
      y: raw.y ?? position.y,
      country: raw.country ?? fallback?.country ?? "",
      capacity: raw.capacity ?? fallback?.capacity,
      minStorage: raw.minStorage ?? fallback?.minStorage,
      initialStorage: raw.initialStorage ?? fallback?.initialStorage,
    };
  });
}

function normalizeEdges(rawEdges: RawGraph["edges"], nodes: NileNode[]): NileEdge[] {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const byId = new Map(fallbackEdges.map((edge) => [edge.id, edge]));
  const source: RawGraphEdge[] = rawEdges?.length
    ? rawEdges
    : fallbackEdges.filter((edge) => nodeIds.has(edge.from) && nodeIds.has(edge.to));

  return source.map((raw) => {
    const fallback = raw.id ? byId.get(raw.id) : undefined;
    const id = raw.id ?? `${raw.from}_to_${raw.to}`;
    const from = nodes.find((node) => node.id === raw.from);
    const to = nodes.find((node) => node.id === raw.to);
    const path = raw.path ?? fallback?.path ?? pathBetween(from, to);
    return {
      id,
      from: raw.from,
      to: raw.to,
      label: raw.label ?? fallback?.label ?? `${titleFromId(raw.from)} to ${titleFromId(raw.to)}`,
      lossFraction: raw.lossFraction ?? fallback?.lossFraction ?? Math.max(0, 1 - (raw.fraction ?? 1)),
      path,
      gradient: raw.gradient ?? fallback?.gradient ?? {
        x1: from?.x ?? 0,
        y1: from?.y ?? 0,
        x2: to?.x ?? 0,
        y2: to?.y ?? 0,
      },
    };
  });
}

function rustPeriodToVisualizerPeriod(
  period: RawRustPeriod,
  index: number,
  nodes: NileNode[],
  edges: NileEdge[],
): PeriodResult {
  const byNode = new Map((period.node_results ?? []).map((node) => [node.node_id, node]));
  const nodeResults = nodes.map((node) => rustNodeToVisualizerNode(node, byNode.get(node.id), index, edges));
  const edgeResults = edges.map((edge) => edgeResultFromNodes(edge, byNode, edges));

  return {
    periodIndex: period.period_index ?? index,
    label: `Period ${index + 1}`,
    startDay: period.start_day ?? index,
    endDayExclusive: period.end_day_exclusive ?? index + 1,
    totalIncomingFlow: sum(nodeResults, (node) => node.totalIncomingFlow),
    totalLocalInflow: sum(nodeResults, (node) => node.totalLocalInflow),
    totalEdgeLoss: sum(edgeResults, (edge) => edge.totalLostFlow),
    totalBasinExitFlow: sum(nodeResults, (node) => node.totalBasinExitOutflow),
    nodeResults,
    edgeResults,
  };
}

function rustNodeToVisualizerNode(
  node: NileNode,
  result: RawRustNodeResult | undefined,
  periodIndex: number,
  edges: NileEdge[],
): NodePeriodResult {
  const totalInflow = numeric(result?.total_inflow);
  const downstream = numeric(result?.downstream_release);
  const storage = numeric(result?.reservoir_level, node.initialStorage ?? 0);
  const outgoingCount = edges.filter((edge) => edge.from === node.id).length;
  const isTerminal = outgoingCount === 0 || terminalKinds.has(node.kind);
  const releaseForExit = numeric(result?.production_release) + numeric(result?.spill);
  const drinkTarget = numeric(result?.drink_water_met) + numeric(result?.unmet_drink_water);
  const foodProduced = numeric(result?.food_produced);
  const energy = numeric(result?.energy_value);

  return {
    nodeId: node.id,
    totalIncomingFlow: totalInflow,
    totalLocalInflow: 0,
    startingStorage: periodIndex === 0 ? node.initialStorage ?? storage : storage,
    endingStorage: storage,
    totalAvailableWater: totalInflow + storage,
    totalDownstreamOutflow: downstream,
    totalBasinExitOutflow: isTerminal ? downstream || releaseForExit : 0,
    drinkingWater: drinkTarget > 0 ? delivery(numeric(result?.drink_water_met), drinkTarget) : null,
    irrigation: foodProduced > 0 ? irrigation(foodProduced) : null,
    hydropower: energy > 0 ? hydropower(numeric(result?.production_release), energy) : null,
  };
}

function edgeResultFromNodes(
  edge: NileEdge,
  byNode: Map<string, RawRustNodeResult>,
  edges: NileEdge[],
): EdgePeriodResult {
  const from = byNode.get(edge.from);
  const outgoing = edges.filter((candidate) => candidate.from === edge.from);
  const share = outgoing.length > 0 ? 1 / outgoing.length : 1;
  const sent = numeric(from?.downstream_release) * share;
  const received = sent * (1 - edge.lossFraction);
  return {
    edgeId: edge.id,
    totalRoutedFlow: sent,
    totalLostFlow: Math.max(0, sent - received),
    totalReceivedFlow: received,
  };
}

function csvRowsToPeriod(
  periodIndex: number,
  index: number,
  nodes: NileNode[],
  edges: NileEdge[],
  rowsByNode: Map<string, ResultCsvRow[]>,
): PeriodResult {
  const rowByNode = new Map(
    Array.from(rowsByNode.entries()).flatMap(([nodeId, rows]) => {
      const row = rows.find((candidate) => numberFrom(candidate.period_index) === periodIndex);
      return row ? [[nodeId, row] as const] : [];
    }),
  );
  const first = Array.from(rowByNode.values())[0];
  const nodeResults = nodes.map((node) => csvRowToNodeResult(node, rowByNode.get(node.id), index, edges));
  const edgeResults = edges.map((edge) => edgeResultFromCsv(edge, rowByNode, edges));

  return {
    periodIndex,
    label: `Period ${periodIndex + 1}`,
    startDay: numberFrom(first?.start_day, index),
    endDayExclusive: numberFrom(first?.end_day_exclusive, index + 1),
    totalIncomingFlow: sum(nodeResults, (node) => node.totalIncomingFlow),
    totalLocalInflow: sum(nodeResults, (node) => node.totalLocalInflow),
    totalEdgeLoss: sum(edgeResults, (edge) => edge.totalLostFlow),
    totalBasinExitFlow: sum(nodeResults, (node) => node.totalBasinExitOutflow),
    nodeResults,
    edgeResults,
  };
}

function csvRowToNodeResult(
  node: NileNode,
  row: ResultCsvRow | undefined,
  periodIndex: number,
  edges: NileEdge[],
): NodePeriodResult {
  const storage = numberFrom(row?.reservoir_level, node.initialStorage ?? 0);
  const totalInflow = numberFrom(row?.total_inflow);
  const downstream = numberFrom(row?.downstream_release);
  const outgoingCount = edges.filter((edge) => edge.from === node.id).length;
  const releaseForRouting = numberFrom(row?.release_for_routing)
    || numberFrom(row?.production_release) + numberFrom(row?.spill);
  const drinkTarget = numberFrom(row?.drink_water_met) + numberFrom(row?.unmet_drink_water);
  const foodProduced = numberFrom(row?.food_produced);
  const energy = numberFrom(row?.energy_value);

  return {
    nodeId: node.id,
    totalIncomingFlow: totalInflow,
    totalLocalInflow: 0,
    startingStorage: periodIndex === 0 ? node.initialStorage ?? storage : storage,
    endingStorage: storage,
    totalAvailableWater: totalInflow + storage,
    totalDownstreamOutflow: downstream,
    totalBasinExitOutflow: outgoingCount === 0 ? totalInflow - numberFrom(row?.evaporation) : 0,
    drinkingWater: drinkTarget > 0 ? delivery(numberFrom(row?.drink_water_met), drinkTarget) : null,
    irrigation: foodProduced > 0 ? irrigation(foodProduced) : null,
    hydropower: energy > 0 ? hydropower(numberFrom(row?.production_release), energy) : null,
  };
}

function edgeResultFromCsv(
  edge: NileEdge,
  rowByNode: Map<string, ResultCsvRow>,
  edges: NileEdge[],
): EdgePeriodResult {
  const from = rowByNode.get(edge.from);
  const outgoing = edges.filter((candidate) => candidate.from === edge.from);
  const share = outgoing.length > 0 ? 1 / outgoing.length : 1;
  const sent = numberFrom(from?.downstream_release) * share;
  const loss = numberFrom(from?.routing_loss) * share;
  return {
    edgeId: edge.id,
    totalRoutedFlow: sent,
    totalLostFlow: loss,
    totalReceivedFlow: Math.max(0, sent - loss),
  };
}

function delivery(actualDelivery: number, totalTarget: number): Delivery {
  return {
    actualDelivery,
    totalTarget,
    totalMinimumTarget: totalTarget,
    shortfallToTarget: Math.max(0, totalTarget - actualDelivery),
    shortfallToMinimum: Math.max(0, totalTarget - actualDelivery),
  };
}

function irrigation(foodProduced: number): Irrigation {
  return {
    water: delivery(foodProduced, foodProduced),
    foodProduced,
  };
}

function hydropower(turbineFlow: number, energyGenerated: number): Hydropower {
  return {
    turbineFlow,
    energyGenerated,
    totalTargetEnergy: energyGenerated,
    totalMinimumEnergy: energyGenerated,
    shortfallToTarget: 0,
    shortfallToMinimum: 0,
  };
}

function normalizeKind(value: unknown): NileNode["kind"] {
  return value === "reservoir" ? "reservoir" : "river";
}

function fallbackPosition(index: number, count: number) {
  const t = count <= 1 ? 0 : index / (count - 1);
  return {
    x: 110 + t * 820,
    y: 150 + Math.sin(t * Math.PI * 1.35) * 230 + (index % 2) * 80,
  };
}

function pathBetween(from: NileNode | undefined, to: NileNode | undefined) {
  return pathBetweenNodes(from, to);
}

function titleFromId(id: string) {
  return id.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function shortName(value: string) {
  const words = titleFromId(value).split(" ");
  if (words.length <= 2) return words.join(" ");
  return words.slice(0, 2).join(" ");
}

function numeric(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function numberFrom(value: unknown, fallback = 0) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string" || value.trim() === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseCsv(content: string): Array<Record<string, string>> {
  const lines = content.split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length === 0) return [];
  const headers = splitCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const fields = splitCsvLine(line);
    return Object.fromEntries(headers.map((header, index) => [header, fields[index] ?? ""]));
  });
}

function splitCsvLine(line: string) {
  const fields: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index++) {
    const char = line[index];
    if (char === '"' && line[index + 1] === '"') {
      current += '"';
      index++;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      fields.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  fields.push(current);
  return fields;
}

function sum<T>(items: T[], selector: (item: T) => number) {
  return items.reduce((total, item) => total + selector(item), 0);
}

function looksLikeVisualizerDataset(value: RawVisualizerFile) {
  return Array.isArray(value.nodes) && Array.isArray(value.edges) && Array.isArray(value.periods)
    && value.periods.some((period) => "nodeResults" in (period as Record<string, unknown>));
}

function looksLikeRustResult(value: RawVisualizerFile | RawRustResult) {
  return Array.isArray(value.periods)
    && value.periods.some((period) => "node_results" in (period as Record<string, unknown>));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === "object" && !Array.isArray(value);
}
