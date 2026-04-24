import type maplibregl from "maplibre-gl";

const TILE_BASE = (import.meta as any).env?.VITE_TILE_BASE ?? "/tiles";

const ZONES: Array<{ id: string; bbox: [number, number, number, number] }> = [
  { id: "gezira", bbox: [32.5, 13.5, 33.6, 14.8] },
  { id: "egypt_delta", bbox: [30.0, 30.0, 32.2, 31.5] },
];

export function setNdviOverlay(
  map: maplibregl.Map,
  month: string | null,
  visible: boolean,
) {
  for (const z of ZONES) {
    const sid = `ndvi-${z.id}`;
    const lid = `ndvi-layer-${z.id}`;
    if (!visible || !month) {
      if (map.getLayer(lid)) map.removeLayer(lid);
      if (map.getSource(sid)) map.removeSource(sid);
      continue;
    }
    const url = `${TILE_BASE}/ndvi/${z.id}/${month}/{z}/{x}/{y}.png`;
    const existing = map.getSource(sid) as maplibregl.RasterTileSource | undefined;
    if (!existing) {
      map.addSource(sid, {
        type: "raster",
        tiles: [url],
        tileSize: 256,
        bounds: z.bbox,
        // Dataloader currently pre-renders only z=7 tiles. Clamp requests to
        // that zoom so MapLibre doesn't spam 404s at lower zoom levels.
        minzoom: 7,
        maxzoom: 7,
      });
      map.addLayer({
        id: lid, type: "raster", source: sid,
        paint: { "raster-opacity": 0.6 },
      });
    } else {
      (existing as any).setTiles([url]);
    }
  }
}
