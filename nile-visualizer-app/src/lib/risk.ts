import {
  Droplets,
  GlassWater,
  Waves,
  Wheat,
  Zap,
  type LucideIcon,
} from "lucide-react";
import {
  DELIVERY_CRITICAL_RATIO,
  DELIVERY_WARNING_RATIO,
  STORAGE_CRITICAL_RATIO,
  STORAGE_WARNING_RATIO,
} from "../config";
import { roundedPoint } from "./geo";
import type { ImpactDimension, ImpactZone } from "./riverPaths";
import type { NileNode, NodePeriodResult, PeriodResult } from "../types";

export type SectorKind = "food" | "drinking" | "power" | "storage" | "flow";

export type SectorRisk = {
  kind: SectorKind;
  ratio: number;
  nodeShortName: string;
};

export type RiskLevel = "none" | "warning" | "critical";

export type RegionRisk = {
  level: RiskLevel;
  worst: SectorRisk | null;
  byKind: Map<SectorKind, SectorRisk>;
};

export type RegionDef = {
  id: string;
  name: string;
  codes: string[];
  match: RegExp;
  centroid: { x: number; y: number };
  pillAnchor: { x: number; y: number };
};

export const regions: RegionDef[] = [
  {
    id: "egy",
    name: "Egypt",
    codes: ["EGY", "EG"],
    match: /egypt|aswan|cairo|delta/i,
    centroid: roundedPoint(31.7, 27.2),
    pillAnchor: roundedPoint(31.4, 27.7),
  },
  {
    id: "sdn",
    name: "Sudan",
    codes: ["SDN", "SD"],
    match: /khartoum|gezira|roseires|merowe|atbara|sudan/i,
    centroid: roundedPoint(32.8, 16.2),
    pillAnchor: roundedPoint(31.8, 17.7),
  },
  {
    id: "ssd",
    name: "South Sudan",
    codes: ["SSD", "SS"],
    match: /sudd|malakal|south[ _]sudan/i,
    centroid: roundedPoint(31.8, 6.8),
    pillAnchor: roundedPoint(31.2, 5.6),
  },
  {
    id: "eth",
    name: "Ethiopia",
    codes: ["ETH", "ET"],
    match: /tana|gerd|ethiopia|atbara_source/i,
    centroid: roundedPoint(36.0, 8.8),
    pillAnchor: roundedPoint(36.25, 8.2),
  },
  {
    id: "uga",
    name: "Uganda",
    codes: ["UGA", "UG"],
    match: /victoria|uganda/i,
    centroid: roundedPoint(32.35, 1.35),
    pillAnchor: roundedPoint(31.75, 0.25),
  },
];

export const sectorCopy: Record<
  SectorKind,
  { critical: string; warning: string; valueSuffix: string }
> = {
  food: { critical: "Food production at risk", warning: "Food allocation strained", valueSuffix: "of crop demand met" },
  drinking: { critical: "Drinking water unmet", warning: "Drinking water strained", valueSuffix: "of city demand met" },
  power: { critical: "Hydropower deficit", warning: "Power below target", valueSuffix: "of energy target" },
  storage: { critical: "Reservoir near empty", warning: "Storage running low", valueSuffix: "of capacity" },
  flow: { critical: "Low downstream flow", warning: "Reduced downstream flow", valueSuffix: "of best period" },
};

export const sectorIcons: Record<SectorKind, LucideIcon> = {
  food: Wheat,
  drinking: GlassWater,
  power: Zap,
  storage: Droplets,
  flow: Waves,
};

export function sectorLabel(kind: SectorKind) {
  switch (kind) {
    case "food":
      return "crops";
    case "drinking":
      return "drinking";
    case "power":
      return "power";
    case "storage":
      return "storage";
    case "flow":
      return "outflow";
  }
}

export function sectorRiskLevel(sector: SectorRisk): RiskLevel {
  if (sector.kind === "storage") {
    if (sector.ratio < STORAGE_CRITICAL_RATIO) return "critical";
    if (sector.ratio < STORAGE_WARNING_RATIO) return "warning";
    return "none";
  }
  if (sector.ratio < DELIVERY_CRITICAL_RATIO) return "critical";
  if (sector.ratio < DELIVERY_WARNING_RATIO) return "warning";
  return "none";
}

export function nodesForRegion(region: RegionDef, nodes: NileNode[]) {
  return nodes.filter((node) => {
    const code = (node.country ?? "").toUpperCase();
    if (code && region.codes.includes(code)) return true;
    if (!code && region.match.test(node.id)) return true;
    return false;
  });
}

export function computeRegionRisk(
  region: RegionDef,
  nodes: NileNode[],
  resultById: Map<string, NodePeriodResult>,
  periods: PeriodResult[],
): RegionRisk {
  const matched = nodesForRegion(region, nodes);
  const sectors: SectorRisk[] = [];

  for (const node of matched) {
    const result = resultById.get(node.id);
    if (!result) continue;

    if (result.drinkingWater && result.drinkingWater.totalTarget > 0) {
      sectors.push({
        kind: "drinking",
        ratio: result.drinkingWater.actualDelivery / result.drinkingWater.totalTarget,
        nodeShortName: node.shortName,
      });
    }
    if (result.irrigation && result.irrigation.water.totalTarget > 0) {
      sectors.push({
        kind: "food",
        ratio: result.irrigation.water.actualDelivery / result.irrigation.water.totalTarget,
        nodeShortName: node.shortName,
      });
    }
    // Hydropower stress isn't computed: NRSM has no energy target. Power
    // impact zones still trigger off storage/flow ratios upstream.
    if (node.capacity && node.capacity > 0) {
      sectors.push({
        kind: "storage",
        ratio: result.endingStorage / node.capacity,
        nodeShortName: node.shortName,
      });
    }
    if (result.totalBasinExitOutflow > 0) {
      const max = Math.max(
        1,
        ...periods.flatMap((entry) =>
          entry.nodeResults
            .filter((candidate) => candidate.nodeId === node.id)
            .map((candidate) => candidate.totalBasinExitOutflow),
        ),
      );
      sectors.push({
        kind: "flow",
        ratio: result.totalBasinExitOutflow / max,
        nodeShortName: node.shortName,
      });
    }
  }

  if (sectors.length === 0) {
    return { level: "none", worst: null, byKind: new Map() };
  }

  const byKind = new Map<SectorKind, SectorRisk>();
  for (const sector of sectors) {
    const existing = byKind.get(sector.kind);
    if (!existing || sector.ratio < existing.ratio) {
      byKind.set(sector.kind, sector);
    }
  }

  const worst = sectors.reduce((acc, candidate) => (candidate.ratio < acc.ratio ? candidate : acc));
  return { level: sectorRiskLevel(worst), worst, byKind };
}

// `intensity` ∈ [0,1] — used to drive opacity continuously so the user can
// see magnitude, not just a discrete bucket. `level` keeps the warning vs
// critical distinction so we can pick a hatching pattern.
export type ZoneRisk = { level: RiskLevel; ratio: number; intensity: number };

export function computeZoneRisk(
  zone: ImpactZone,
  _nodes: NileNode[],
  resultById: Map<string, NodePeriodResult>,
  periods: PeriodResult[],
): ZoneRisk {
  let worst = 1;
  let active = false;

  // Upstream causes contribute via the relevant dimension.
  for (const nodeId of zone.causedBy) {
    const ratio = causedByRatio(zone.dimension, nodeId, resultById, periods);
    if (ratio === null) continue;
    active = true;
    if (ratio < worst) worst = ratio;
  }

  // For delivery zones, in-zone demand-met ratios drive the zone — but only
  // for the kind of demand the zone is built around. Without this, Gezira
  // (food) and Khartoum-muni (drinking) would both fire when either ratio
  // dropped, since they share `karthoum`.
  if (zone.dimension === "delivery" && zone.deliveryNodes) {
    for (const nodeId of zone.deliveryNodes) {
      const result = resultById.get(nodeId);
      if (!result) continue;
      const ratio =
        zone.deliveryKind === "drinking"
          ? ratioOrNull(result.drinkingWater?.actualDelivery, result.drinkingWater?.totalTarget)
          : zone.deliveryKind === "food"
            ? ratioOrNull(result.irrigation?.water.actualDelivery, result.irrigation?.water.totalTarget)
            : null;
      if (ratio === null) continue;
      active = true;
      if (ratio < worst) worst = ratio;
    }
  }

  if (!active) return { level: "none", ratio: 1, intensity: 0 };

  // Critical kicks in below DELIVERY_CRITICAL_RATIO; intensity ramps from
  // DELIVERY_WARNING_RATIO downwards. Below ~0.2 ratio the scribble is at
  // full opacity. This mapping is shared across delivery/flow/power so a
  // 50% drop reads the same regardless of the dimension.
  const intensity = Math.min(1, Math.max(0, (DELIVERY_WARNING_RATIO - worst) / (DELIVERY_WARNING_RATIO - 0.2)));
  const level: RiskLevel =
    worst < DELIVERY_CRITICAL_RATIO ? "critical" : worst < DELIVERY_WARNING_RATIO ? "warning" : "none";

  return { level, ratio: worst, intensity };
}

function causedByRatio(
  dimension: ImpactDimension,
  nodeId: string,
  resultById: Map<string, NodePeriodResult>,
  periods: PeriodResult[],
): number | null {
  const result = resultById.get(nodeId);
  if (!result) return null;

  if (dimension === "power") {
    if (!result.hydropower) return null;
    return baselineRelative(periods, nodeId, result.hydropower.energyGenerated, (n) => n.hydropower?.energyGenerated ?? 0);
  }
  // For flow and for upstream-causes-of-delivery, use downstream release vs
  // historical max for that node. If the upstream is sending much less than
  // its best period, downstream suffers.
  return baselineRelative(periods, nodeId, result.totalDownstreamOutflow, (n) => n.totalDownstreamOutflow);
}

function baselineRelative(
  periods: PeriodResult[],
  nodeId: string,
  current: number,
  pick: (node: NodePeriodResult) => number,
): number {
  const max = Math.max(
    0,
    ...periods.flatMap((entry) =>
      entry.nodeResults.filter((candidate) => candidate.nodeId === nodeId).map(pick),
    ),
  );
  if (max <= 0) return 1;
  return Math.min(1, current / max);
}

function ratioOrNull(actual: number | undefined, target: number | undefined): number | null {
  if (!target || target <= 0 || actual === undefined) return null;
  return actual / target;
}
