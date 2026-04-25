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
import type { ImpactZone } from "./riverPaths";
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
    if (result.hydropower && result.hydropower.totalTargetEnergy > 0) {
      sectors.push({
        kind: "power",
        ratio: result.hydropower.energyGenerated / result.hydropower.totalTargetEnergy,
        nodeShortName: node.shortName,
      });
    }
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

export function computeZoneRisk(
  zone: ImpactZone,
  nodes: NileNode[],
  resultById: Map<string, NodePeriodResult>,
  periods: PeriodResult[],
): { level: RiskLevel; ratio: number } {
  let worst = 1;
  let active = false;

  for (const nodeId of zone.trigger.nodeIds) {
    const result = resultById.get(nodeId);
    if (!result) continue;
    const node = nodes.find((candidate) => candidate.id === nodeId);
    if (!node) continue;

    let ratio = 1;
    switch (zone.trigger.kind) {
      case "drinking":
        if (result.drinkingWater && result.drinkingWater.totalTarget > 0) {
          ratio = result.drinkingWater.actualDelivery / result.drinkingWater.totalTarget;
          active = true;
        }
        break;
      case "food":
        if (result.irrigation && result.irrigation.water.totalTarget > 0) {
          ratio = result.irrigation.water.actualDelivery / result.irrigation.water.totalTarget;
          active = true;
        }
        break;
      case "power":
        if (result.hydropower && result.hydropower.totalTargetEnergy > 0) {
          ratio = result.hydropower.energyGenerated / result.hydropower.totalTargetEnergy;
          active = true;
        }
        break;
      case "storage":
        if (node.capacity && node.capacity > 0) {
          ratio = result.endingStorage / node.capacity;
          active = true;
        }
        break;
      case "flow": {
        const max = Math.max(
          1,
          ...periods.flatMap((entry) =>
            entry.nodeResults
              .filter((candidate) => candidate.nodeId === nodeId)
              .map((candidate) => candidate.totalDownstreamOutflow),
          ),
        );
        if (max > 0) {
          ratio = result.totalDownstreamOutflow / max;
          active = true;
        }
        break;
      }
    }

    if (ratio < worst) worst = ratio;
  }

  if (!active) return { level: "none", ratio: 1 };

  if (zone.trigger.kind === "storage") {
    if (worst < STORAGE_CRITICAL_RATIO) return { level: "critical", ratio: worst };
    if (worst < STORAGE_WARNING_RATIO) return { level: "warning", ratio: worst };
    return { level: "none", ratio: worst };
  }

  if (worst < DELIVERY_CRITICAL_RATIO) return { level: "critical", ratio: worst };
  if (worst < DELIVERY_WARNING_RATIO) return { level: "warning", ratio: worst };
  return { level: "none", ratio: worst };
}
