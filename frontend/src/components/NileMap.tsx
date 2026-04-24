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

  // Node layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !nodes) return;
    let cancelled = false;
    const apply = () => {
      if (cancelled) return;
      // Retry on next styledata event if the style isn't ready yet —
      // avoids the `once("load")` footgun where the load has already fired.
      if (!map.isStyleLoaded()) {
        console.debug("[NileMap] style not loaded; retrying on styledata");
        map.once("styledata", apply);
        return;
      }
      const enriched = enrichNodesWithResults(nodes, runningResults);
      console.debug("[NileMap] applying node layer",
        enriched.features.length, "features");
      const src = map.getSource("nodes") as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData(enriched);
        return;
      }
      map.addSource("nodes", { type: "geojson", data: enriched });
      map.addLayer({
        id: "node-circle", type: "circle", source: "nodes",
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
      map.addLayer({
        id: "node-label", type: "symbol", source: "nodes",
        layout: {
          "text-field": ["get", "name"],
          "text-offset": [0, 1.2],
          "text-size": 11,
        },
        paint: {
          "text-color": "#0f172a",
          "text-halo-color": "#f8fafc",
          "text-halo-width": 1,
        },
      });
    };
    apply();
    return () => { cancelled = true; };
  }, [nodes, runningResults]);

  // NDVI overlay
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let cancelled = false;
    const apply = () => {
      if (cancelled) return;
      if (!map.isStyleLoaded()) {
        map.once("styledata", apply);
        return;
      }
      setNdviOverlay(map, scrubMonth ?? lastMonth(runningResults), overlays.ndvi);
    };
    apply();
    return () => { cancelled = true; };
  }, [overlays.ndvi, scrubMonth, runningResults]);

  return (
    <>
      <div ref={ref} className="absolute inset-0" />
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
