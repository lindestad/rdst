export type Lens = "stress" | "water" | "storage" | "production";

export type ScenarioPreset = "normal" | "drought" | "extreme_rain" | "upstream_holdback";

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
  lossFraction: number;
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

export type Hydropower = {
  turbineFlow: number;
  energyGenerated: number;
  totalTargetEnergy: number;
  totalMinimumEnergy: number;
  shortfallToTarget: number;
  shortfallToMinimum: number;
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
  totalRoutedFlow: number;
  totalLostFlow: number;
  totalReceivedFlow: number;
};

export type PeriodResult = {
  periodIndex: number;
  label: string;
  startDay: number;
  endDayExclusive: number;
  totalIncomingFlow: number;
  totalLocalInflow: number;
  totalEdgeLoss: number;
  totalBasinExitFlow: number;
  nodeResults: NodePeriodResult[];
  edgeResults: EdgePeriodResult[];
};

export type RunMetadata = {
  name: string;
  source: string;
  horizon: string;
  reporting: string;
  units: string;
};

export type VisualizerDataset = {
  metadata: RunMetadata;
  nodes: NileNode[];
  edges: NileEdge[];
  periods: PeriodResult[];
};
