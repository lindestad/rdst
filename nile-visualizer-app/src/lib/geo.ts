import type { NileNode } from "../types";

export const MAP_VIEWBOX = {
  width: 1040,
  height: 720,
  west: 28.4,
  east: 38.9,
  south: -1.2,
  north: 32.2,
  tileZoom: 5,
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

export const osmTiles = buildTiles();

export function projectGeo(longitude: number, latitude: number) {
  const point = worldPoint(longitude, latitude);
  return {
    x: (point.x - viewWorldBounds.left) * scale,
    y: (point.y - viewWorldBounds.top) * scale,
  };
}

export function pathBetweenNodes(from: NileNode | undefined, to: NileNode | undefined) {
  if (!from || !to) return "M 80 360 C 320 300 720 300 960 360";
  const verticalSpan = Math.abs(from.y - to.y);
  const bend = Math.max(24, Math.min(86, verticalSpan * 0.28));
  const cx = (from.x + to.x) / 2;
  const cy = (from.y + to.y) / 2 - bend;
  return `M ${round(from.x)} ${round(from.y)} C ${round(cx)} ${round(cy)} ${round(cx)} ${round(cy)} ${round(to.x)} ${round(to.y)}`;
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
  const minX = Math.floor(viewWorldBounds.left / 256);
  const maxX = Math.floor(viewWorldBounds.right / 256);
  const minY = Math.floor(viewWorldBounds.top / 256);
  const maxY = Math.floor(viewWorldBounds.bottom / 256);
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
