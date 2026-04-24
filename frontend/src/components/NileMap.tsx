import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { setNdviOverlay } from "../lib/ndvi";
import { useStore } from "../state/store";
import { NodeInspector } from "./NodeInspector";

export function NileMap() {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { nodes, runningResults, scrubMonth, overlays } = useStore();

  // Initial mount
  useEffect(() => {
    if (!ref.current) return;
    const map = new maplibregl.Map({
      container: ref.current,
      style: "/nile-style.json",
      center: [32, 15],
      zoom: 3.6,
    });
    mapRef.current = map;
    map.on("error", (e) => console.error("[NileMap] map error", e?.error ?? e));
    map.on("load", () => console.debug("[NileMap] load fired; size",
      map.getCanvas().width, "x", map.getCanvas().height));
    map.on("click", "node-circle", (e) => {
      const id = (e.features?.[0]?.properties as any)?.id;
      if (id) setSelectedId(id as string);
    });
    map.on("mouseenter", "node-circle", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "node-circle", () => {
      map.getCanvas().style.cursor = "";
    });
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // Node layer — wait for the map's `load` event, since isStyleLoaded() can
  // stay false past load. We skip the text-label layer on purpose: symbol
  // layers with text-field require a `glyphs` URL in the style, which our
  // minimal OSM-raster style doesn't include.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !nodes) return;
    let cancelled = false;

    const apply = () => {
      if (cancelled || !mapRef.current) return;
      const m = mapRef.current;
      const enriched = enrichNodesWithResults(nodes, runningResults);
      console.debug("[NileMap] applying", enriched.features.length, "node features");
      const src = m.getSource("nodes") as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData(enriched);
        return;
      }
      m.addSource("nodes", { type: "geojson", data: enriched });
      m.addLayer({
        id: "node-circle",
        type: "circle",
        source: "nodes",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "radius_px"], 0, 3, 30, 22],
          "circle-color": [
            "case",
            ["==", ["get", "type"], "reservoir"], "#60a5fa",
            ["==", ["get", "type"], "wetland"], "#10b981",
            ["==", ["get", "type"], "demand_irrigation"], "#f59e0b",
            ["==", ["get", "type"], "demand_municipal"], "#fb923c",
            ["==", ["get", "type"], "sink"], "#6366f1",
            "#3b82f6",
          ],
          "circle-stroke-color": "#0b1220",
          "circle-stroke-width": 1.5,
        },
      });
    };

    if (map.loaded()) apply();
    else {
      const onLoad = () => apply();
      map.once("load", onLoad);
    }
    return () => { cancelled = true; };
  }, [nodes, runningResults]);

  // NDVI overlay
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let cancelled = false;
    const apply = () => {
      if (cancelled || !mapRef.current) return;
      setNdviOverlay(
        mapRef.current,
        scrubMonth ?? lastMonth(runningResults),
        overlays.ndvi,
      );
    };
    if (map.loaded()) apply();
    else map.once("load", apply);
    return () => { cancelled = true; };
  }, [overlays.ndvi, scrubMonth, runningResults]);

  return (
    <>
      <div
        ref={ref}
        className="absolute inset-0 bg-slate-700"
        style={{ minHeight: 200 }}
      />
      {selectedId && (
        <NodeInspector nodeId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </>
  );
}

function enrichNodesWithResults(
  nodes: GeoJSON.FeatureCollection,
  r: ReturnType<typeof useStore.getState>["runningResults"],
) {
  const copy = structuredClone(nodes) as GeoJSON.FeatureCollection;
  copy.features.forEach((f: any) => {
    f.properties.radius_px = 10;
    if (r?.results) {
      const ts = r.results.timeseries_per_node?.[f.properties.id];
      if (ts?.length) {
        const last = ts[ts.length - 1] as Record<string, number>;
        if ("storage_mcm" in last) {
          f.properties.radius_px = Math.sqrt(last.storage_mcm / 1000) + 4;
        } else if ("outflow_m3s" in last) {
          f.properties.radius_px = Math.sqrt(last.outflow_m3s / 10) + 3;
        }
      }
    }
  });
  return copy;
}

function lastMonth(
  r: ReturnType<typeof useStore.getState>["runningResults"],
): string | null {
  const kpis = r?.results?.kpi_monthly;
  return kpis && kpis.length > 0 ? kpis[kpis.length - 1].month : null;
}
