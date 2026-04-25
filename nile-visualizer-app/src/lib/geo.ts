import type { NileNode } from "../types";
import { rivers } from "./riverPaths";

export const MAP_VIEWBOX = {
  width: 1040,
  height: 720,
  west: 28.4,
  east: 38.9,
  south: -1.2,
  north: 32.2,
  tileZoom: 6,
};

const worldSize = 256 * 2 ** MAP_VIEWBOX.tileZoom;
const northWest = worldPoint(MAP_VIEWBOX.west, MAP_VIEWBOX.north);
const southEast = worldPoint(MAP_VIEWBOX.east, MAP_VIEWBOX.south);
const center = {
  x: (northWest.x + southEast.x) / 2,
  y: (northWest.y + southEast.y) / 2,
};
const scale = MAP_VIEWBOX.height / ((southEast.y - northWest.y) * 1.08);
const viewWorldBounds = {
  left: center.x - MAP_VIEWBOX.width / (2 * scale),
  top: center.y - MAP_VIEWBOX.height / (2 * scale),
  right: center.x + MAP_VIEWBOX.width / (2 * scale),
  bottom: center.y + MAP_VIEWBOX.height / (2 * scale),
};

// Pad the tile-loading region so zoom-out and pan reveal map beyond the basin
// frame. Margin is in screen pixels at scale=1; we convert back to world units.
const TILE_MARGIN_PX = 1300;
const tileWorldBounds = {
  left: viewWorldBounds.left - TILE_MARGIN_PX / scale,
  top: viewWorldBounds.top - TILE_MARGIN_PX / scale,
  right: viewWorldBounds.right + TILE_MARGIN_PX / scale,
  bottom: viewWorldBounds.bottom + TILE_MARGIN_PX / scale,
};

export const osmTiles = buildTiles();

export function projectGeo(longitude: number, latitude: number) {
  const point = worldPoint(longitude, latitude);
  return {
    x: (point.x - viewWorldBounds.left) * scale,
    y: (point.y - viewWorldBounds.top) * scale,
  };
}

type Pt = { x: number; y: number };

const projectedRivers = rivers.map((river) => ({
  id: river.id,
  points: river.coords.map(([lng, lat]) => projectGeo(lng, lat)),
}));

function dist2(a: Pt, b: Pt) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return dx * dx + dy * dy;
}

function nearestIndex(points: Pt[], target: Pt) {
  let bestIdx = 0;
  let bestD = Infinity;
  for (let i = 0; i < points.length; i++) {
    const d = dist2(points[i], target);
    if (d < bestD) {
      bestD = d;
      bestIdx = i;
    }
  }
  return { index: bestIdx, distance: Math.sqrt(bestD) };
}

function pickRiver(from: Pt, to: Pt) {
  let best: { points: Pt[]; fromIdx: number; toIdx: number; score: number } | null = null;
  for (const river of projectedRivers) {
    const a = nearestIndex(river.points, from);
    const b = nearestIndex(river.points, to);
    const score = a.distance + b.distance + Math.abs(a.index - b.index) * 0.1;
    if (!best || score < best.score) {
      best = { points: river.points, fromIdx: a.index, toIdx: b.index, score };
    }
  }
  return best;
}

function smoothCatmullRom(points: Pt[], tension = 0.22) {
  if (points.length < 2) return "";
  let d = `M ${round(points[0].x)} ${round(points[0].y)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) * tension;
    const c1y = p1.y + (p2.y - p0.y) * tension;
    const c2x = p2.x - (p3.x - p1.x) * tension;
    const c2y = p2.y - (p3.y - p1.y) * tension;
    d += ` C ${round(c1x)} ${round(c1y)} ${round(c2x)} ${round(c2y)} ${round(p2.x)} ${round(p2.y)}`;
  }
  return d;
}

export function pathBetweenNodes(from: NileNode | undefined, to: NileNode | undefined) {
  if (!from || !to) return "M 80 360 C 320 300 720 300 960 360";

  const fromPt: Pt = { x: from.x, y: from.y };
  const toPt: Pt = { x: to.x, y: to.y };
  const choice = pickRiver(fromPt, toPt);

  // If both endpoints are reasonably close to a river polyline, follow it.
  // Otherwise fall back to a straight bezier.
  if (choice && choice.score < 240 && choice.fromIdx !== choice.toIdx) {
    const lo = Math.min(choice.fromIdx, choice.toIdx);
    const hi = Math.max(choice.fromIdx, choice.toIdx);
    let middle = choice.points.slice(lo + 1, hi);
    if (choice.fromIdx > choice.toIdx) middle = middle.reverse();
    const points: Pt[] = [fromPt, ...middle, toPt];
    return smoothCatmullRom(points, 0.22);
  }

  const verticalSpan = Math.abs(from.y - to.y);
  const bend = Math.max(24, Math.min(86, verticalSpan * 0.28));
  const cx = (from.x + to.x) / 2;
  const cy = (from.y + to.y) / 2 - bend;
  return `M ${round(from.x)} ${round(from.y)} C ${round(cx)} ${round(cy)} ${round(cx)} ${round(cy)} ${round(to.x)} ${round(to.y)}`;
}

export function smoothPolygonFromGeo(waypoints: Array<[number, number]>): string {
  if (waypoints.length < 3) return "";
  const points = waypoints.map(([lng, lat]) => projectGeo(lng, lat));
  const n = points.length;
  let d = `M ${round(points[0].x)} ${round(points[0].y)}`;
  const tension = 0.18;

  for (let i = 0; i < n; i++) {
    const p0 = points[(i - 1 + n) % n];
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const p3 = points[(i + 2) % n];
    const c1x = p1.x + (p2.x - p0.x) * tension;
    const c1y = p1.y + (p2.y - p0.y) * tension;
    const c2x = p2.x - (p3.x - p1.x) * tension;
    const c2y = p2.y - (p3.y - p1.y) * tension;
    d += ` C ${round(c1x)} ${round(c1y)} ${round(c2x)} ${round(c2y)} ${round(p2.x)} ${round(p2.y)}`;
  }
  d += " Z";
  return d;
}

export function roundedPoint(longitude: number, latitude: number) {
  const point = projectGeo(longitude, latitude);
  return {
    x: round(point.x),
    y: round(point.y),
  };
}

function mercatorY(latitude: number) {
  const clamped = Math.max(-85.05112878, Math.min(85.05112878, latitude));
  const radians = clamped * Math.PI / 180;
  return (1 - Math.log(Math.tan(radians) + 1 / Math.cos(radians)) / Math.PI) / 2;
}

function worldPoint(longitude: number, latitude: number) {
  return {
    x: ((longitude + 180) / 360) * worldSize,
    y: mercatorY(latitude) * worldSize,
  };
}

function buildTiles() {
  const minX = Math.floor(tileWorldBounds.left / 256);
  const maxX = Math.floor(tileWorldBounds.right / 256);
  const minY = Math.floor(tileWorldBounds.top / 256);
  const maxY = Math.floor(tileWorldBounds.bottom / 256);
  const tiles: Array<{ key: string; href: string; x: number; y: number; width: number; height: number }> = [];
  const tileCount = 2 ** MAP_VIEWBOX.tileZoom;

  for (let tileY = minY; tileY <= maxY; tileY++) {
    if (tileY < 0 || tileY >= tileCount) continue;
    for (let tileX = minX; tileX <= maxX; tileX++) {
      const wrappedX = ((tileX % tileCount) + tileCount) % tileCount;
      tiles.push({
        key: `${MAP_VIEWBOX.tileZoom}-${wrappedX}-${tileY}`,
        href: `https://tile.openstreetmap.org/${MAP_VIEWBOX.tileZoom}/${wrappedX}/${tileY}.png`,
        x: round((tileX * 256 - viewWorldBounds.left) * scale),
        y: round((tileY * 256 - viewWorldBounds.top) * scale),
        width: round(256 * scale + 0.5),
        height: round(256 * scale + 0.5),
      });
    }
  }

  return tiles;
}

function round(value: number) {
  return Math.round(value * 10) / 10;
}
