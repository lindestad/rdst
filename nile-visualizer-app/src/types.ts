export type Lens = "stress" | "water" | "storage" | "production";

export type NodeKind = "river" | "reservoir";

export type NileNode = {
  id: string;
  name: string;
  shortName: string;
  kind: NodeKind;
  x: number;
  y: number;
  country: string;
  capacity?: number;
  minStorage?: number;
  initialStorage?: number;
};

export type NileEdge = {
  id: string;
  from: string;
  to: string;
  label: string;
  path: string;
  gradient: {
    x1: number;
    y1: number;
    x2: number;
    y2: number;
  };
};

export type Delivery = {
  actualDelivery: number;
  totalTarget: number;
  totalMinimumTarget: number;
  shortfallToTarget: number;
  shortfallToMinimum: number;
};

export type Irrigation = {
  water: Delivery;
  foodProduced: number;
};

// Hydropower is an output of the simulator (production_release × kWh/m³),
// not a demand. NRSM has no "energy target" — we only surface what was
// generated and its EUR value.
export type Hydropower = {
  turbineFlow: number; // m³ released through turbines
  energyGenerated: number; // MWh
  valueEur: number; // monetary value of generated electricity
};

export type NodePeriodResult = {
  nodeId: string;
  totalIncomingFlow: number;
  totalLocalInflow: number;
  startingStorage: number;
  endingStorage: number;
  totalAvailableWater: number;
  totalDownstreamOutflow: number;
  totalBasinExitOutflow: number;
  drinkingWater: Delivery | null;
  irrigation: Irrigation | null;
  hydropower: Hydropower | null;
};

export type EdgePeriodResult = {
  edgeId: string;
  totalFlow: number;
};

export type PeriodResult = {
  periodIndex: number;
  label: string;
  startDay: number;
  endDayExclusive: number;
  totalIncomingFlow: number;
  totalLocalInflow: number;
  totalBasinExitFlow: number;
  nodeResults: NodePeriodResult[];
  edgeResults: EdgePeriodResult[];
};

export type RunOrigin = "packaged" | "uploaded-csv" | "uploaded-json" | "sample";

export type RunMetadata = {
  name: string;
  source: string;
  horizon: string;
  reporting: string;
  units: string;
  origin: RunOrigin;
  runId?: string;
  schemaVersion?: string;
  assembledAt?: string;
};

export type VisualizerDataset = {
  metadata: RunMetadata;
  nodes: NileNode[];
  edges: NileEdge[];
  periods: PeriodResult[];
};
