import type { NileEdge, NileNode } from "../types";

type Anchor = "start" | "middle" | "end";

export type MapNodeLayout = {
  id: string;
  anchorX: number;
  anchorY: number;
  x: number;
  y: number;
  labelX: number;
  labelY: number;
  labelAnchor: Anchor;
};

export function layoutMapEdges(edges: NileEdge[], nodeLayouts: MapNodeLayout[]): NileEdge[] {
  const layoutById = new Map(nodeLayouts.map((layout) => [layout.id, layout]));
  const incomingGroups = new Map<string, NileEdge[]>();
  const outgoingGroups = new Map<string, NileEdge[]>();

  for (const edge of edges) {
    incomingGroups.set(edge.to, [...(incomingGroups.get(edge.to) ?? []), edge]);
    outgoingGroups.set(edge.from, [...(outgoingGroups.get(edge.from) ?? []), edge]);
  }

  return edges.map((edge) => {
    const from = layoutById.get(edge.from);
    const to = layoutById.get(edge.to);
    if (!from || !to) return edge;

    const incoming = incomingGroups.get(edge.to) ?? [edge];
    const outgoing = outgoingGroups.get(edge.from) ?? [edge];
    const incomingOffset = fanOffset(edge, incoming, 34);
    const outgoingOffset = fanOffset(edge, outgoing, 22);
    const offset = incoming.length > 1 ? incomingOffset : outgoing.length > 1 ? outgoingOffset : 0;

    return {
      ...edge,
      path: routedPath(from, to, offset),
      gradient: {
        x1: from.x,
        y1: from.y,
        x2: to.x,
        y2: to.y,
      },
    };
  });
}

const mapBounds = {
  left: 92,
  right: 948,
  top: 64,
  bottom: 648,
};

export function layoutMapNodes(nodes: NileNode[]): MapNodeLayout[] {
  const positioned = spreadDenseNodes(nodes);
  return placeLabels(nodes, positioned);
}

function spreadDenseNodes(nodes: NileNode[]) {
  const positioned = nodes.map((node) => ({
    id: node.id,
    anchorX: node.x,
    anchorY: node.y,
    x: node.x,
    y: node.y,
  }));

  const minSpacing = 43;
  for (let pass = 0; pass < 70; pass++) {
    for (let i = 0; i < positioned.length; i++) {
      for (let j = i + 1; j < positioned.length; j++) {
        const a = positioned[i];
        const b = positioned[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let distance = Math.hypot(dx, dy);
        if (distance >= minSpacing) continue;

        if (distance < 0.1) {
          const angle = ((i + j + 1) / positioned.length) * Math.PI * 2;
          dx = Math.cos(angle);
          dy = Math.sin(angle);
          distance = 1;
        }

        const push = (minSpacing - distance) * 0.5;
        const ux = dx / distance;
        const uy = dy / distance;
        a.x -= ux * push;
        a.y -= uy * push;
        b.x += ux * push;
        b.y += uy * push;
      }
    }

    for (const node of positioned) {
      node.x += (node.anchorX - node.x) * 0.035;
      node.y += (node.anchorY - node.y) * 0.035;
      node.x = clamp(node.x, mapBounds.left, mapBounds.right);
      node.y = clamp(node.y, mapBounds.top, mapBounds.bottom);
    }
  }

  return positioned;
}

function placeLabels(
  nodes: NileNode[],
  positioned: Array<{ id: string; anchorX: number; anchorY: number; x: number; y: number }>,
): MapNodeLayout[] {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const markerBounds = positioned.map((node) => ({
    left: node.x - 17,
    right: node.x + 17,
    top: node.y - 17,
    bottom: node.y + 17,
  }));
  const occupied = [...markerBounds];

  return positioned
    .map((position) => {
      const node = nodeById.get(position.id);
      const label = chooseLabelPosition(position, node?.shortName ?? position.id, occupied);
      occupied.push(label.bounds);
      return {
        ...position,
        labelX: label.x,
        labelY: label.y,
        labelAnchor: label.anchor,
      };
    });
}

function chooseLabelPosition(
  node: { x: number; y: number; anchorX: number; anchorY: number },
  label: string,
  occupied: Array<{ left: number; right: number; top: number; bottom: number }>,
) {
  const width = Math.max(38, label.length * 6.4 + 12);
  const height = 16;
  const awayX = node.x - node.anchorX;
  const awayY = node.y - node.anchorY;
  const prefersHorizontal = Math.abs(awayX) > Math.abs(awayY);
  const preferred = prefersHorizontal
    ? (awayX >= 0 ? ["e", "ne", "se", "s", "n", "w", "nw", "sw"] : ["w", "nw", "sw", "s", "n", "e", "ne", "se"])
    : (awayY >= 0 ? ["s", "se", "sw", "e", "w", "n", "ne", "nw"] : ["n", "ne", "nw", "e", "w", "s", "se", "sw"]);
  const offsets: Record<string, { dx: number; dy: number; anchor: Anchor }> = {
    n: { dx: 0, dy: -22, anchor: "middle" },
    ne: { dx: 17, dy: -16, anchor: "start" },
    e: { dx: 20, dy: 5, anchor: "start" },
    se: { dx: 17, dy: 24, anchor: "start" },
    s: { dx: 0, dy: 27, anchor: "middle" },
    sw: { dx: -17, dy: 24, anchor: "end" },
    w: { dx: -20, dy: 5, anchor: "end" },
    nw: { dx: -17, dy: -16, anchor: "end" },
  };

  let best: { x: number; y: number; anchor: Anchor; bounds: Rect; score: number } | null = null;
  for (const [rank, key] of preferred.entries()) {
    const offset = offsets[key];
    const x = node.x + offset.dx;
    const y = node.y + offset.dy;
    const bounds = labelBounds(x, y, width, height, offset.anchor);
    const score = rank * 12 + boundsPenalty(bounds) + occupied.reduce((total, rect) => total + overlapArea(bounds, rect), 0);
    if (!best || score < best.score) {
      best = { x, y, anchor: offset.anchor, bounds, score };
    }
  }

  return best ?? {
    x: node.x,
    y: node.y + 27,
    anchor: "middle" as const,
    bounds: labelBounds(node.x, node.y + 27, width, height, "middle"),
  };
}

type Rect = { left: number; right: number; top: number; bottom: number };

function labelBounds(x: number, y: number, width: number, height: number, anchor: Anchor): Rect {
  const left = anchor === "middle" ? x - width / 2 : anchor === "end" ? x - width : x;
  return {
    left,
    right: left + width,
    top: y - height + 3,
    bottom: y + 3,
  };
}

function overlapArea(a: Rect, b: Rect) {
  const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
  const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
  return width * height * 2.5;
}

function boundsPenalty(rect: Rect) {
  const left = Math.max(0, mapBounds.left - rect.left);
  const right = Math.max(0, rect.right - mapBounds.right);
  const top = Math.max(0, mapBounds.top - rect.top);
  const bottom = Math.max(0, rect.bottom - mapBounds.bottom);
  return (left + right + top + bottom) * 30;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function fanOffset(edge: NileEdge, group: NileEdge[], spacing: number) {
  if (group.length <= 1) return 0;
  const ordered = [...group].sort((a, b) => a.id.localeCompare(b.id));
  const index = Math.max(0, ordered.findIndex((candidate) => candidate.id === edge.id));
  return (index - (ordered.length - 1) / 2) * spacing;
}

function routedPath(
  from: { x: number; y: number },
  to: { x: number; y: number },
  offset: number,
) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const distance = Math.max(1, Math.hypot(dx, dy));
  const nx = -dy / distance;
  const ny = dx / distance;
  const curve = Math.max(18, Math.min(58, distance * 0.16));
  const signedCurve = offset === 0 ? curve : offset;
  const c1x = from.x + dx * 0.42 + nx * signedCurve;
  const c1y = from.y + dy * 0.42 + ny * signedCurve;
  const c2x = from.x + dx * 0.58 + nx * signedCurve;
  const c2y = from.y + dy * 0.58 + ny * signedCurve;
  return `M ${round(from.x)} ${round(from.y)} C ${round(c1x)} ${round(c1y)} ${round(c2x)} ${round(c2y)} ${round(to.x)} ${round(to.y)}`;
}

function round(value: number) {
  return Math.round(value * 10) / 10;
}
