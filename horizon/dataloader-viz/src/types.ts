export type NodeKind = "river" | "reservoir";
export type EntityType = "node" | "edge";

export type NodeRow = {
  scenario_id: string;
  node_id: string;
  name: string;
  node_kind: NodeKind | string;
  latitude: string;
  longitude: string;
  country_code: string;
  subbasin_id: string;
  reservoir_capacity_million_m3: string;
  reservoir_min_storage_million_m3: string;
  initial_storage_million_m3: string;
  food_per_unit_water: string;
  energy_per_unit_water: string;
  notes: string;
};

export type EdgeRow = {
  scenario_id: string;
  edge_id: string;
  from_node_id: string;
  to_node_id: string;
  flow_share: string;
  default_loss_fraction: string;
  travel_time_days: string;
  notes: string;
};

export type TimeSeriesRow = {
  scenario_id: string;
  entity_type: EntityType | string;
  entity_id: string;
  metric: string;
  interval_start: string;
  interval_end: string;
  value: string;
  unit: string;
  source_name: string;
  source_url: string;
  transform: string;
  quality_flag: string;
};

export type CsvBundleFiles = {
  nodes: string;
  edges: string;
  timeSeries: string;
};

export type DataloaderBundle = {
  sourceLabel: string;
  nodes: NodeRow[];
  edges: EdgeRow[];
  timeSeries: TimeSeriesRow[];
};

export type MetricSummary = {
  metric: string;
  rows: number;
  entities: number;
  unit: string;
  sources: string[];
  min: number;
  max: number;
};

export type Diagnostic = {
  label: string;
  detail: string;
  severity: "ok" | "warn" | "error";
};

export type GraphNode = NodeRow & {
  x: number;
  y: number;
  value: number | null;
  seriesRows: TimeSeriesRow[];
};

export type GraphEdge = EdgeRow & {
  path: string;
  value: number | null;
  seriesRows: TimeSeriesRow[];
};
