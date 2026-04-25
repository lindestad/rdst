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

export const nodes: NileNode[] = [
  {
    id: "white_nile_headwaters",
    name: "Lake Victoria Outlet",
    shortName: "Victoria",
    kind: "river",
    x: 497,
    y: 642,
    country: "UGA",
  },
  {
    id: "blue_nile_headwaters",
    name: "Lake Tana Outlet",
    shortName: "Tana",
    kind: "river",
    x: 878,
    y: 435,
    country: "ETH",
  },
  {
    id: "gerd",
    name: "GERD",
    shortName: "GERD",
    kind: "reservoir",
    x: 670,
    y: 442,
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
    x: 437,
    y: 361,
    country: "SDN",
  },
  {
    id: "aswan",
    name: "High Aswan",
    shortName: "Aswan",
    kind: "reservoir",
    x: 469,
    y: 206,
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
    x: 343,
    y: 66,
    country: "EGY",
  },
];

export const edges: NileEdge[] = [
  {
    id: "white_to_khartoum",
    from: "white_nile_headwaters",
    to: "khartoum",
    label: "White Nile to Khartoum",
    lossFraction: 0.02,
    path: "M 497 642 C 378 555 346 452 437 361",
    gradient: { x1: 497, y1: 642, x2: 437, y2: 361 },
  },
  {
    id: "blue_to_gerd",
    from: "blue_nile_headwaters",
    to: "gerd",
    label: "Blue Nile to GERD",
    lossFraction: 0.01,
    path: "M 878 435 C 778 429 724 438 670 442",
    gradient: { x1: 878, y1: 435, x2: 670, y2: 442 },
  },
  {
    id: "gerd_to_khartoum",
    from: "gerd",
    to: "khartoum",
    label: "GERD to Khartoum",
    lossFraction: 0.015,
    path: "M 670 442 C 590 403 512 386 437 361",
    gradient: { x1: 670, y1: 442, x2: 437, y2: 361 },
  },
  {
    id: "khartoum_to_aswan",
    from: "khartoum",
    to: "aswan",
    label: "Khartoum to Aswan",
    lossFraction: 0.025,
    path: "M 437 361 C 526 302 418 254 469 206",
    gradient: { x1: 437, y1: 361, x2: 469, y2: 206 },
  },
  {
    id: "aswan_to_delta",
    from: "aswan",
    to: "nile_delta",
    label: "Aswan to Delta",
    lossFraction: 0.03,
    path: "M 469 206 C 410 154 358 112 343 66",
    gradient: { x1: 469, y1: 206, x2: 343, y2: 66 },
  },
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
    label: "Month 3",
    startDay: 60,
    endDayExclusive: 90,
    totalIncomingFlow: 41277.6075,
    totalLocalInflow: 14100,
    totalEdgeLoss: 912.1425,
    totalBasinExitFlow: 5270.8575,
    nodeResults: [
      nodeResult("white_nile_headwaters", 0, 7050, 0, 0, 7050, 7050, 0),
      nodeResult("blue_nile_headwaters", 0, 6300, 0, 0, 6300, 6300, 0),
      nodeResult("gerd", 6237, 0, 772, 409, 24133.5, 6600, 0, null, null, {
        turbineFlow: 6600,
        energyGenerated: 4488,
        totalTargetEnergy: 4350,
        totalMinimumEnergy: 3300,
        shortfallToTarget: 0,
        shortfallToMinimum: 0,
      }),
      nodeResult("khartoum", 13410, 600, 0, 0, 14010, 11610, 0, delivery(750, 750, 540), irrigation(1650, 1650, 1050, 3465)),
      nodeResult("aswan", 11319.75, 150, 1600, 1600, 59469.75, 10629.75, 0, delivery(840, 840, 600), null, {
        turbineFlow: 8700,
        energyGenerated: 5133,
        totalTargetEnergy: 5100,
        totalMinimumEnergy: 3900,
        shortfallToTarget: 0,
        shortfallToMinimum: 0,
      }),
      nodeResult("nile_delta", 10310.8575, 0, 0, 0, 10310.8575, 5270.8575, 5270.8575, delivery(1440, 1440, 1050), irrigation(3600, 3600, 2400, 6480)),
    ],
    edgeResults: [
      edgeResult("white_to_khartoum", 7050, 141, 6909),
      edgeResult("blue_to_gerd", 6300, 63, 6237),
      edgeResult("gerd_to_khartoum", 6600, 99, 6501),
      edgeResult("khartoum_to_aswan", 11610, 290.25, 11319.75),
      edgeResult("aswan_to_delta", 10629.75, 318.8925, 10310.8575),
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
