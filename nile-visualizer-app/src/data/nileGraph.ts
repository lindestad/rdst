import { pathBetweenNodes, roundedPoint } from "../lib/geo";
import type { NileEdge, NileNode } from "../types";

function nodePosition(longitude: number, latitude: number) {
  return roundedPoint(longitude, latitude);
}

function node(
  id: string,
  name: string,
  shortName: string,
  kind: NileNode["kind"],
  longitude: number,
  latitude: number,
  country: string,
  capacity?: number,
  initialStorage?: number,
): NileNode {
  return {
    id,
    name,
    shortName,
    kind,
    ...nodePosition(longitude, latitude),
    country,
    capacity,
    initialStorage,
  };
}

export const nodes: NileNode[] = [
  node("victoria", "Lake Victoria Outlet", "Victoria", "river", 33.0, -1.0, "UGA"),
  node("southwest", "Sudd / White Nile", "Sudd", "river", 29.5, 8.5, "SSD"),
  node("tana", "Lake Tana Outlet", "Tana", "river", 37.3, 12.0, "ETH"),
  node("gerd", "Grand Ethiopian Renaissance Dam", "GERD", "reservoir", 35.1, 11.2, "ETH", 950, 500),
  node("roseires", "Roseires Dam", "Roseires", "reservoir", 34.4, 11.9, "SDN", 420, 260),
  node("singa", "Sennar / Singa Reach", "Singa", "river", 34.0, 13.2, "SDN"),
  node("ozentari", "Ozentari Headwaters", "Ozentari", "river", 37.2, 13.5, "ETH"),
  node("tsengh", "Tekeze / Tsengh Dam", "Tsengh", "reservoir", 36.5, 14.0, "ETH", 250, 150),
  node("kashm", "Kashm el-Girba Dam", "Kashm", "reservoir", 35.9, 14.9, "SDN", 400, 250),
  node("karthoum", "Khartoum Confluence", "Khartoum", "river", 32.6, 15.6, "SDN"),
  node("merowe", "Merowe Dam", "Merowe", "reservoir", 32.0, 18.7, "SDN", 720, 420),
  node("aswand", "High Aswan Dam", "Aswan", "reservoir", 32.9, 24.0, "EGY", 1600, 900),
  node("cairo", "Cairo / Nile Delta", "Cairo", "river", 31.0, 30.8, "EGY"),
];

const nodeById = new Map(nodes.map((candidate) => [candidate.id, candidate]));

function edge(id: string, fromId: string, toId: string, label: string): NileEdge {
  const from = nodeById.get(fromId);
  const to = nodeById.get(toId);
  return {
    id,
    from: fromId,
    to: toId,
    label,
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
  edge("victoria__southwest", "victoria", "southwest", "Victoria to Sudd"),
  edge("southwest__karthoum", "southwest", "karthoum", "White Nile to Khartoum"),
  edge("tana__gerd", "tana", "gerd", "Lake Tana to GERD"),
  edge("gerd__roseires", "gerd", "roseires", "GERD to Roseires"),
  edge("roseires__singa", "roseires", "singa", "Roseires to Singa"),
  edge("singa__merowe", "singa", "merowe", "Blue Nile to Merowe"),
  edge("ozentari__tsengh", "ozentari", "tsengh", "Ozentari to Tsengh"),
  edge("tsengh__kashm", "tsengh", "kashm", "Tsengh to Kashm"),
  edge("kashm__merowe", "kashm", "merowe", "Atbara to Merowe"),
  edge("karthoum__merowe", "karthoum", "merowe", "Khartoum to Merowe"),
  edge("merowe__aswand", "merowe", "aswand", "Merowe to Aswan"),
  edge("aswand__cairo", "aswand", "cairo", "Aswan to Cairo"),
];
