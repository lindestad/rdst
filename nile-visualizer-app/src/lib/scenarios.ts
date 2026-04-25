import type {
  Delivery,
  EdgePeriodResult,
  Hydropower,
  Irrigation,
  NodePeriodResult,
  PeriodResult,
  ScenarioPreset,
  VisualizerDataset,
} from "../types";

export const scenarioPresets: Array<{
  id: ScenarioPreset;
  label: string;
  summary: string;
}> = [
  {
    id: "normal",
    label: "Normal",
    summary: "Raw simulator output.",
  },
  {
    id: "drought",
    label: "Drought",
    summary: "Lower inflows, reservoir drawdown, and unmet demand.",
  },
  {
    id: "extreme_rain",
    label: "Extreme rain",
    summary: "High runoff, more routing pressure, and fuller reservoirs.",
  },
  {
    id: "upstream_holdback",
    label: "Dam holdback",
    summary: "GERD retains more water and downstream releases fall.",
  },
];

export function scenarioLabel(id: ScenarioPreset) {
  return scenarioPresets.find((scenario) => scenario.id === id)?.label ?? id;
}

export function applyScenarioPreset(
  dataset: VisualizerDataset,
  scenario: ScenarioPreset,
): VisualizerDataset {
  if (scenario === "normal") return dataset;

  const periods = dataset.periods.map((period, index) => transformPeriod(period, index, scenario, dataset.periods.length));
  return {
    ...dataset,
    metadata: {
      ...dataset.metadata,
      source: `${dataset.metadata.source} / ${scenarioLabel(scenario)} what-if`,
      horizon: dataset.metadata.horizon,
    },
    periods,
  };
}

function transformPeriod(
  period: PeriodResult,
  index: number,
  scenario: Exclude<ScenarioPreset, "normal">,
  count: number,
): PeriodResult {
  const t = count <= 1 ? 1 : index / (count - 1);
  const nodeResults = period.nodeResults.map((node) => transformNode(node, scenario, t));
  const edgeResults = period.edgeResults.map((edge) => transformEdge(edge, scenario, t));

  return {
    ...period,
    label: scenario === "drought"
      ? `Drought ${index + 1}`
      : scenario === "extreme_rain"
        ? `Rain ${index + 1}`
        : `Holdback ${index + 1}`,
    totalIncomingFlow: sum(nodeResults, (node) => node.totalIncomingFlow),
    totalLocalInflow: sum(nodeResults, (node) => node.totalLocalInflow),
    totalEdgeLoss: sum(edgeResults, (edge) => edge.totalLostFlow),
    totalBasinExitFlow: sum(nodeResults, (node) => node.totalBasinExitOutflow),
    nodeResults,
    edgeResults,
  };
}

function transformNode(
  node: NodePeriodResult,
  scenario: Exclude<ScenarioPreset, "normal">,
  t: number,
): NodePeriodResult {
  if (scenario === "drought") {
    const water = lerp(0.72, 0.42, t);
    const delivery = lerp(0.78, 0.48, t);
    const storage = lerp(0.72, 0.32, t);
    return scaleNode(node, {
      incoming: water,
      downstream: water * 0.88,
      storage,
      delivery,
      energy: water * 0.72,
      exit: water * 0.72,
    });
  }

  if (scenario === "extreme_rain") {
    const water = lerp(1.24, 1.72, t);
    return scaleNode(node, {
      incoming: water,
      downstream: water * 1.06,
      storage: 1.18,
      delivery: 1.08,
      energy: 1.16,
      exit: water * 1.12,
    });
  }

  const isGerd = node.nodeId === "gerd";
  const downstreamImpact = downstreamHoldbackImpact(node.nodeId);
  if (isGerd) {
    return scaleNode(node, {
      incoming: 1,
      downstream: 0.18,
      storage: 1.85,
      delivery: 1,
      energy: 0.28,
      exit: 0.18,
    });
  }

  if (downstreamImpact < 1) {
    return scaleNode(node, {
      incoming: downstreamImpact,
      downstream: downstreamImpact * 0.9,
      storage: Math.max(0.2, downstreamImpact * 0.9),
      delivery: downstreamImpact,
      energy: downstreamImpact * 0.85,
      exit: downstreamImpact * 0.82,
    });
  }

  return { ...node };
}

function transformEdge(
  edge: EdgePeriodResult,
  scenario: Exclude<ScenarioPreset, "normal">,
  t: number,
): EdgePeriodResult {
  if (scenario === "drought") {
    const water = lerp(0.72, 0.42, t);
    return scaleEdge(edge, water, 0.85);
  }

  if (scenario === "extreme_rain") {
    const water = lerp(1.24, 1.72, t);
    return scaleEdge(edge, water, 1.45);
  }

  const impact = edgeHoldbackImpact(edge.edgeId);
  return scaleEdge(edge, impact, impact < 1 ? 0.9 : 1);
}

function scaleNode(
  node: NodePeriodResult,
  factors: {
    incoming: number;
    downstream: number;
    storage: number;
    delivery: number;
    energy: number;
    exit: number;
  },
): NodePeriodResult {
  const endingStorage = Math.max(0, node.endingStorage * factors.storage);
  const startingStorage = Math.max(0, node.startingStorage * factors.storage);
  const totalIncomingFlow = Math.max(0, node.totalIncomingFlow * factors.incoming);
  return {
    ...node,
    totalIncomingFlow,
    totalLocalInflow: Math.max(0, node.totalLocalInflow * factors.incoming),
    startingStorage,
    endingStorage,
    totalAvailableWater: totalIncomingFlow + endingStorage,
    totalDownstreamOutflow: Math.max(0, node.totalDownstreamOutflow * factors.downstream),
    totalBasinExitOutflow: Math.max(0, node.totalBasinExitOutflow * factors.exit),
    drinkingWater: node.drinkingWater ? scaleDelivery(node.drinkingWater, factors.delivery) : null,
    irrigation: node.irrigation ? scaleIrrigation(node.irrigation, factors.delivery) : null,
    hydropower: node.hydropower ? scaleHydropower(node.hydropower, factors.energy) : null,
  };
}

function scaleEdge(edge: EdgePeriodResult, waterFactor: number, lossFactor: number): EdgePeriodResult {
  const totalRoutedFlow = Math.max(0, edge.totalRoutedFlow * waterFactor);
  const totalLostFlow = Math.max(0, edge.totalLostFlow * waterFactor * lossFactor);
  return {
    ...edge,
    totalRoutedFlow,
    totalLostFlow,
    totalReceivedFlow: Math.max(0, totalRoutedFlow - totalLostFlow),
  };
}

function scaleDelivery(delivery: Delivery, factor: number): Delivery {
  const actualDelivery = Math.min(delivery.totalTarget * 1.05, Math.max(0, delivery.actualDelivery * factor));
  return {
    ...delivery,
    actualDelivery,
    shortfallToTarget: Math.max(0, delivery.totalTarget - actualDelivery),
    shortfallToMinimum: Math.max(0, delivery.totalMinimumTarget - actualDelivery),
  };
}

function scaleIrrigation(irrigation: Irrigation, factor: number): Irrigation {
  const water = scaleDelivery(irrigation.water, factor);
  return {
    ...irrigation,
    water,
    foodProduced: Math.max(0, irrigation.foodProduced * factor),
  };
}

function scaleHydropower(hydropower: Hydropower, factor: number): Hydropower {
  const energyGenerated = Math.max(0, hydropower.energyGenerated * factor);
  return {
    ...hydropower,
    turbineFlow: Math.max(0, hydropower.turbineFlow * factor),
    energyGenerated,
    shortfallToTarget: Math.max(0, hydropower.totalTargetEnergy - energyGenerated),
    shortfallToMinimum: Math.max(0, hydropower.totalMinimumEnergy - energyGenerated),
  };
}

function downstreamHoldbackImpact(nodeId: string) {
  if (["roseires", "singa"].includes(nodeId)) return 0.34;
  if (["karthoum", "khartoum", "merowe"].includes(nodeId)) return 0.48;
  if (["aswand", "aswan", "cairo"].includes(nodeId)) return 0.58;
  return 1;
}

function edgeHoldbackImpact(edgeId: string) {
  if (edgeId === "gerd__roseires") return 0.18;
  if (edgeId === "roseires__singa") return 0.34;
  if (edgeId === "singa__merowe") return 0.42;
  if (edgeId === "karthoum__merowe") return 0.55;
  if (edgeId === "merowe__aswand") return 0.58;
  if (edgeId === "aswand__cairo") return 0.62;
  return 1;
}

function lerp(start: number, end: number, t: number) {
  return start + (end - start) * t;
}

function sum<T>(items: T[], selector: (item: T) => number) {
  return items.reduce((total, item) => total + selector(item), 0);
}
