export type NodeType =
  | "source" | "reservoir" | "reach" | "confluence" | "wetland"
  | "demand_municipal" | "demand_irrigation" | "sink";

export type NodeFeature = {
  type: "Feature";
  geometry: { type: "Point"; coordinates: [number, number] };
  properties: {
    id: string;
    name: string;
    type: NodeType;
    country: string;
    upstream: string[];
    downstream: string[];
  };
};
export type NodesGeoJSON = { type: "FeatureCollection"; features: NodeFeature[] };

export type Timeseries = {
  month: string[];
  values: Record<string, (number | null)[]>;
};

export type Weights = { water: number; food: number; energy: number };

export type ReservoirPolicy = {
  mode: "historical" | "rule_curve" | "manual";
  release_m3s_by_month?: Record<string, number>;
};

export type DemandPolicy = { area_scale?: number; population_scale?: number };
export type Constraints = { min_delta_flow_m3s: number };

export type Policy = {
  reservoirs: Record<string, ReservoirPolicy>;
  demands: Record<string, DemandPolicy>;
  constraints: Constraints;
  weights: Weights;
};

export type Kpi = {
  month: string;
  water_served_pct: number;
  food_tonnes: number;
  energy_gwh: number;
};

export type ScenarioResults = {
  timeseries_per_node: Record<string, Array<Record<string, number | string | null>>>;
  kpi_monthly: Kpi[];
  score: number | null;
  score_breakdown: Record<string, number>;
};

export type Scenario = {
  id: string;
  name: string;
  created_at: string;
  period: [string, string];
  policy: Policy;
  results?: ScenarioResults | null;
};

export type ScenarioSummary = {
  id: string;
  name: string;
  created_at: string;
  score: number | null;
  period: [string, string];
};

export type CompareResponse = {
  scenarios: Record<string, { name: string; score: number | null }>;
  kpi_deltas: Array<{
    month: string;
    water_served_pct: number;
    food_tonnes: number;
    energy_gwh: number;
  }>;
  score_delta: number;
};
