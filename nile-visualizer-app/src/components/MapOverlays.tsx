import { STORAGE_CRITICAL_RATIO, STORAGE_WARNING_RATIO } from "../config";
import { smoothPolygonFromGeo } from "../lib/geo";
import { impactZones } from "../lib/riverPaths";
import { computeZoneRisk, regions } from "../lib/risk";
import type { NileNode, NodePeriodResult, PeriodResult } from "../types";

export function ImpactZoneOverlay({
  nodes,
  period,
  periods,
}: {
  nodes: NileNode[];
  period: PeriodResult;
  periods: PeriodResult[];
}) {
  const resultById = new Map(period.nodeResults.map((result) => [result.nodeId, result]));

  return (
    <g className="impact-zone-layer" pointerEvents="none">
      {impactZones.map((zone) => {
        const risk = computeZoneRisk(zone, nodes, resultById, periods);
        if (risk.level === "none") return null;
        const path = smoothPolygonFromGeo(zone.geo);
        if (!path) return null;
        const scribble = risk.level === "critical" ? "url(#scribble-critical)" : "url(#scribble-warning)";
        return (
          <g className={`impact-zone ${risk.level}`} key={`zone-${zone.id}`}>
            <path className="impact-zone-wash" d={path} />
            <path className="impact-zone-scribble" d={path} fill={scribble} />
          </g>
        );
      })}
    </g>
  );
}

export function CountryLabels() {
  return (
    <g className="country-label-layer" pointerEvents="none">
      {regions.map((region) => (
        <text
          className="country-label"
          key={`country-${region.id}`}
          x={region.centroid.x}
          y={region.centroid.y}
        >
          {region.name.toUpperCase()}
        </text>
      ))}
    </g>
  );
}

export function RegionAnnotations({
  nodes,
  period,
  selectedNodeId,
}: {
  nodes: NileNode[];
  period: PeriodResult;
  periods: PeriodResult[];
  selectedNodeId: string;
}) {
  const resultById = new Map(period.nodeResults.map((result) => [result.nodeId, result]));
  const reservoirNodes = nodes.filter((node) => node.kind === "reservoir");

  return (
    <>
      <g className="reservoir-badge-layer" pointerEvents="none">
        {reservoirNodes.map((node) => {
          const result = resultById.get(node.id);
          if (!result || !node.capacity) return null;
          const ratio = result.endingStorage / node.capacity;
          const level =
            ratio < STORAGE_CRITICAL_RATIO
              ? "critical"
              : ratio < STORAGE_WARNING_RATIO
                ? "warning"
                : "none";
          if (level === "none") return null;
          const radius = level === "critical" ? 24 : 20;
          const isSelected = node.id === selectedNodeId;
          return (
            <g key={`storage-${node.id}`}>
              <circle
                className={`storage-ring ${level} ${isSelected ? "selected" : ""}`}
                cx={node.x}
                cy={node.y}
                r={radius}
              />
              <title>
                {`${node.name}: ${Math.round(ratio * 100)}% of capacity`}
              </title>
              {isSelected && (
                <>
                  <text className="storage-label" x={node.x} y={node.y - radius - 6}>
                    {level === "critical" ? "Reservoir near empty" : "Storage running low"}
                  </text>
                  <text className="storage-value" x={node.x} y={node.y - radius - 22}>
                    {`${Math.round(ratio * 100)}% of capacity`}
                  </text>
                </>
              )}
            </g>
          );
        })}
      </g>
    </>
  );
}
