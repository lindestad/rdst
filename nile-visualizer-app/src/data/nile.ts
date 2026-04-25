import type {
  Delivery,
  EdgePeriodResult,
  Hydropower,
  Irrigation,
  NileEdge,
  NileNode,
  NodePeriodResult,
  PeriodResult,
  VisualizerDataset,
} from "../types";
import { pathBetweenNodes, roundedPoint } from "../lib/geo";

function nodePosition(longitude: number, latitude: number) {
  return roundedPoint(longitude, latitude);
}

export const nodes: NileNode[] = [
  {
    id: "white_nile_headwaters",
    name: "Lake Victoria Outlet",
    shortName: "Victoria",
    kind: "river",
    ...nodePosition(33.19, 0.42),
    country: "UGA",
  },
  {
    id: "blue_nile_headwaters",
    name: "Lake Tana Outlet",
    shortName: "Tana",
    kind: "river",
    ...nodePosition(37.38, 11.6),
    country: "ETH",
  },
  {
    id: "gerd",
    name: "GERD",
    shortName: "GERD",
    kind: "reservoir",
    ...nodePosition(35.09, 11.22),
    country: "ETH",
    capacity: 950,
    minStorage: 250,
    initialStorage: 500,
  },
  {
    id: "khartoum",
    name: "Khartoum Confluence",
    shortName: "Khartoum",
    kind: "river",
    ...nodePosition(32.53, 15.6),
    country: "SDN",
  },
  {
    id: "aswan",
    name: "High Aswan",
    shortName: "Aswan",
    kind: "reservoir",
    ...nodePosition(32.88, 23.97),
    country: "EGY",
    capacity: 1600,
    minStorage: 500,
    initialStorage: 900,
  },
  {
    id: "nile_delta",
    name: "Nile Delta",
    shortName: "Delta",
    kind: "river",
    ...nodePosition(31.5, 31.5),
    country: "EGY",
  },
];

const nodeById = new Map(nodes.map((node) => [node.id, node]));

function sampleEdge(
  id: string,
  fromId: string,
  toId: string,
  label: string,
  lossFraction: number,
): NileEdge {
  const from = nodeById.get(fromId);
  const to = nodeById.get(toId);
  return {
    id,
    from: fromId,
    to: toId,
    label,
    lossFraction,
    path: pathBetweenNodes(from, to),
    gradient: {
      x1: from?.x ?? 0,
      y1: from?.y ?? 0,
      x2: to?.x ?? 0,
      y2: to?.y ?? 0,
    },
  };
}

export const edges: NileEdge[] = [
  sampleEdge("white_to_khartoum", "white_nile_headwaters", "khartoum", "White Nile to Khartoum", 0.02),
  sampleEdge("blue_to_gerd", "blue_nile_headwaters", "gerd", "Blue Nile to GERD", 0.01),
  sampleEdge("gerd_to_khartoum", "gerd", "khartoum", "GERD to Khartoum", 0.015),
  sampleEdge("khartoum_to_aswan", "khartoum", "aswan", "Khartoum to Aswan", 0.025),
  sampleEdge("aswan_to_delta", "aswan", "nile_delta", "Aswan to Delta", 0.03),
];

export const periods: PeriodResult[] = [
  {
    periodIndex: 0,
    label: "Month 1",
    startDay: 0,
    endDayExclusive: 30,
    totalIncomingFlow: 45289.11648,
    totalLocalInflow: 15750,
    totalEdgeLoss: 1005.50752,
    totalBasinExitFlow: 6014.49248,
    nodeResults: [
      nodeResult("white_nile_headwaters", 0, 8400, 0, 0, 8400, 8400, 0),
      nodeResult("blue_nile_headwaters", 0, 6600, 0, 0, 6600, 6600, 0),
      nodeResult("gerd", 6534, 0, 500, 250, 16722, 6784, 0, null, null, {
        turbineFlow: 6580.2,
        energyGenerated: 4474.536,
        totalTargetEnergy: 4350,
        totalMinimumEnergy: 3300,
        shortfallToTarget: 0,
        shortfallToMinimum: 0,
      }),
      nodeResult("khartoum", 14914.24, 600, 0, 0, 15514.24, 13114.24, 0, delivery(750, 750, 540), irrigation(1650, 1650, 1050, 3465)),
      nodeResult("aswan", 12786.384, 150, 900, 1600, 57398.06525, 11396.384, 0, delivery(840, 840, 600), null, {
        turbineFlow: 8700,
        energyGenerated: 5133,
        totalTargetEnergy: 5100,
        totalMinimumEnergy: 3900,
        shortfallToTarget: 0,
        shortfallToMinimum: 0,
      }),
      nodeResult("nile_delta", 11054.49248, 0, 0, 0, 11054.49248, 6014.49248, 6014.49248, delivery(1440, 1440, 1050), irrigation(3600, 3600, 2400, 6480)),
    ],
    edgeResults: [
      edgeResult("white_to_khartoum", 8400, 168, 8232),
      edgeResult("blue_to_gerd", 6600, 66, 6534),
      edgeResult("gerd_to_khartoum", 6784, 101.76, 6682.24),
      edgeResult("khartoum_to_aswan", 13114.24, 327.856, 12786.384),
      edgeResult("aswan_to_delta", 11396.384, 341.89152, 11054.49248),
    ],
  },
  {
    periodIndex: 1,
    label: "Month 2",
    startDay: 30,
    endDayExclusive: 60,
    totalIncomingFlow: 46206.17175,
    totalLocalInflow: 16200,
    totalEdgeLoss: 1012.10325,
    totalBasinExitFlow: 6385.89675,
    nodeResults: [
      nodeResult("white_nile_headwaters", 0, 7650, 0, 0, 7650, 7650, 0),
      nodeResult("blue_nile_headwaters", 0, 7800, 0, 0, 7800, 7800, 0),
      nodeResult("gerd", 7722, 0, 250, 772, 22791, 7200, 0, null, null, {
        turbineFlow: 6600,
        energyGenerated: 4488,
        totalTargetEnergy: 4350,
        totalMinimumEnergy: 3300,
        shortfallToTarget: 0,
        shortfallToMinimum: 0,
      }),
      nodeResult("khartoum", 14589, 600, 0, 0, 15189, 12789, 0, delivery(750, 750, 540), irrigation(1650, 1650, 1050, 3465)),
      nodeResult("aswan", 12469.275, 150, 1600, 1600, 60619.275, 11779.275, 0, delivery(840, 840, 600), null, {
        turbineFlow: 8700,
        energyGenerated: 5133,
        totalTargetEnergy: 5100,
        totalMinimumEnergy: 3900,
        shortfallToTarget: 0,
        shortfallToMinimum: 0,
      }),
      nodeResult("nile_delta", 11425.89675, 0, 0, 0, 11425.89675, 6385.89675, 6385.89675, delivery(1440, 1440, 1050), irrigation(3600, 3600, 2400, 6480)),
    ],
    edgeResults: [
      edgeResult("white_to_khartoum", 7650, 153, 7497),
      edgeResult("blue_to_gerd", 7800, 78, 7722),
      edgeResult("gerd_to_khartoum", 7200, 108, 7092),
      edgeResult("khartoum_to_aswan", 12789, 319.725, 12469.275),
      edgeResult("aswan_to_delta", 11779.275, 353.37825, 11425.89675),
    ],
  },
  {
    periodIndex: 2,
    label: "Month 3 (drought)",
    startDay: 60,
    endDayExclusive: 90,
    totalIncomingFlow: 22063.09,
    totalLocalInflow: 7930,
    totalEdgeLoss: 428.534,
    totalBasinExitFlow: 1900,
    nodeResults: [
      nodeResult("white_nile_headwaters", 0, 4500, 0, 0, 4500, 4500, 0),
      nodeResult("blue_nile_headwaters", 0, 3000, 0, 0, 3000, 3000, 0),
      nodeResult("gerd", 2970, 0, 772, 150, 3742, 3000, 0, null, null, {
        turbineFlow: 3000,
        energyGenerated: 2040,
        totalTargetEnergy: 4350,
        totalMinimumEnergy: 3300,
        shortfallToTarget: 2310,
        shortfallToMinimum: 1260,
      }),
      nodeResult("khartoum", 7365, 350, 0, 0, 7715, 5435, 0, delivery(680, 750, 540), irrigation(1050, 1650, 1050, 2205)),
      nodeResult("aswan", 5299.125, 80, 1600, 250, 6929.125, 4288.625, 0, delivery(720, 840, 600), null, {
        turbineFlow: 4400,
        energyGenerated: 2596,
        totalTargetEnergy: 5100,
        totalMinimumEnergy: 3900,
        shortfallToTarget: 2504,
        shortfallToMinimum: 1304,
      }),
      nodeResult("nile_delta", 4159.966, 0, 0, 0, 4159.966, 1900, 1900, delivery(1280, 1440, 1050), irrigation(2200, 3600, 2400, 3960)),
    ],
    edgeResults: [
      edgeResult("white_to_khartoum", 4500, 90, 4410),
      edgeResult("blue_to_gerd", 3000, 30, 2970),
      edgeResult("gerd_to_khartoum", 3000, 45, 2955),
      edgeResult("khartoum_to_aswan", 5435, 135.875, 5299.125),
      edgeResult("aswan_to_delta", 4288.625, 128.659, 4159.966),
    ],
  },
];

export const sampleDataset: VisualizerDataset = {
  metadata: {
    name: "Nile MVP Demo",
    source: "Packaged sample",
    horizon: "90 days",
    reporting: "30-day periods",
    units: "NRSM water units",
  },
  nodes,
  edges,
  periods,
};

function delivery(actualDelivery: number, totalTarget: number, totalMinimumTarget: number): Delivery {
  return {
    actualDelivery,
    totalTarget,
    totalMinimumTarget,
    shortfallToTarget: Math.max(0, totalTarget - actualDelivery),
    shortfallToMinimum: Math.max(0, totalMinimumTarget - actualDelivery),
  };
}

function irrigation(
  actualDelivery: number,
  totalTarget: number,
  totalMinimumTarget: number,
  foodProduced: number,
): Irrigation {
  return {
    water: delivery(actualDelivery, totalTarget, totalMinimumTarget),
    foodProduced,
  };
}

function edgeResult(
  edgeId: string,
  totalRoutedFlow: number,
  totalLostFlow: number,
  totalReceivedFlow: number,
): EdgePeriodResult {
  return {
    edgeId,
    totalRoutedFlow,
    totalLostFlow,
    totalReceivedFlow,
  };
}

function nodeResult(
  nodeId: string,
  totalIncomingFlow: number,
  totalLocalInflow: number,
  startingStorage: number,
  endingStorage: number,
  totalAvailableWater: number,
  totalDownstreamOutflow: number,
  totalBasinExitOutflow: number,
  drinkingWater: Delivery | null = null,
  irrigation: Irrigation | null = null,
  hydropower: Hydropower | null = null,
): NodePeriodResult {
  return {
    nodeId,
    totalIncomingFlow,
    totalLocalInflow,
    startingStorage,
    endingStorage,
    totalAvailableWater,
    totalDownstreamOutflow,
    totalBasinExitOutflow,
    drinkingWater,
    irrigation,
    hydropower,
  };
}
