import { smoothPolygonFromGeo } from "../lib/geo";
import { impactZones } from "../lib/riverPaths";
import {
  computeRegionRisk,
  computeZoneRisk,
  regions,
  sectorCopy,
  sectorIcons,
  sectorLabel,
  sectorRiskLevel,
  type RegionDef,
  type RegionRisk,
} from "../lib/risk";
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
  periods,
}: {
  nodes: NileNode[];
  period: PeriodResult;
  periods: PeriodResult[];
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
          const level = ratio < 0.18 ? "critical" : ratio < 0.4 ? "warning" : "none";
          if (level === "none") return null;
          const radius = level === "critical" ? 30 : 24;
          return (
            <g key={`storage-${node.id}`}>
              <circle className={`storage-ring ${level}`} cx={node.x} cy={node.y} r={radius} />
              <text className="storage-label" x={node.x} y={node.y - radius - 6}>
                {level === "critical" ? "Reservoir near empty" : "Storage running low"}
              </text>
              <text className="storage-value" x={node.x} y={node.y - radius - 22}>
                {`${Math.round(ratio * 100)}% of capacity`}
              </text>
            </g>
          );
        })}
      </g>

      <g className="region-pill-layer" pointerEvents="none">
        {regions.map((region) => {
          const risk = computeRegionRisk(region, nodes, resultById, periods);
          if (risk.level === "none" || !risk.worst) return null;
          return <RegionRiskPill key={`pill-${region.id}`} region={region} risk={risk} />;
        })}
      </g>
    </>
  );
}

function RegionRiskPill({ region, risk }: { region: RegionDef; risk: RegionRisk }) {
  if (!risk.worst) return null;
  const copy = sectorCopy[risk.worst.kind];
  const headline = risk.level === "critical" ? copy.critical : copy.warning;
  const Icon = sectorIcons[risk.worst.kind];
  const value = `${Math.round(risk.worst.ratio * 100)}% ${copy.valueSuffix}`;
  const otherKinds = Array.from(risk.byKind.values())
    .filter((sector) => sector !== risk.worst && sectorRiskLevel(sector) !== "none")
    .slice(0, 2);
  const width = 268;
  const height = otherKinds.length > 0 ? 76 : 60;

  return (
    <foreignObject
      x={region.pillAnchor.x - width / 2}
      y={region.pillAnchor.y - height / 2}
      width={width}
      height={height}
      style={{ overflow: "visible" }}
    >
      <div className={`region-pill ${risk.level}`}>
        <div className="region-pill-icon">
          <Icon size={18} strokeWidth={2.2} />
        </div>
        <div className="region-pill-text">
          <strong>
            <span className="region-pill-region">{region.name}</span>
            <span className="region-pill-headline">{headline}</span>
          </strong>
          <span className="region-pill-value">{value}</span>
          {otherKinds.length > 0 && (
            <span className="region-pill-secondary">
              {otherKinds
                .map((sector) => `${sectorLabel(sector.kind)} ${Math.round(sector.ratio * 100)}%`)
                .join(" · ")}
            </span>
          )}
        </div>
      </div>
    </foreignObject>
  );
}
