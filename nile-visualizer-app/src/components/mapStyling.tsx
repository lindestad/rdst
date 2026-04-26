import type { ReactNode } from "react";
import {
  COLOR_CRITICAL,
  COLOR_OK,
  COLOR_WARNING,
  STORAGE_CRITICAL_RATIO,
  STORAGE_WARNING_RATIO,
  STRESS_CRITICAL_RATIO,
  STRESS_WARNING_RATIO,
} from "../config";
import { WATER_VOLUME_UNIT_COMPACT, format } from "../lib/format";
import type {
  EdgePeriodResult,
  Lens,
  NileEdge,
  NileNode,
  NodePeriodResult,
  PeriodResult,
} from "../types";

export function edgeStops(
  lens: Lens,
  edge: NileEdge,
  result: EdgePeriodResult | undefined,
  periods: PeriodResult[],
): ReactNode {
  const baseline = periods[0].edgeResults.find((item) => item.edgeId === edge.id);
  const flowRatio = result && baseline ? result.totalFlow / Math.max(1, baseline.totalFlow) : 1;
  const stressColor =
    flowRatio < STRESS_CRITICAL_RATIO
      ? COLOR_CRITICAL
      : flowRatio < STRESS_WARNING_RATIO
        ? COLOR_WARNING
        : COLOR_OK;

  if (lens === "stress") {
    return (
      <>
        <stop offset="0%" stopColor="#55606e" />
        <stop offset="62%" stopColor="#55606e" />
        <stop offset="100%" stopColor={stressColor} />
      </>
    );
  }

  if (lens === "storage") {
    return (
      <>
        <stop offset="0%" stopColor="#5f6269" />
        <stop offset="100%" stopColor="#8c7a6a" />
      </>
    );
  }

  if (lens === "production") {
    return (
      <>
        <stop offset="0%" stopColor="#2aa579" />
        <stop offset="55%" stopColor="#e2b338" />
        <stop offset="100%" stopColor="#f17f3d" />
      </>
    );
  }

  return (
    <>
      <stop offset="0%" stopColor="#1e96c8" />
      <stop offset="68%" stopColor="#1e96c8" />
      <stop offset="100%" stopColor="#20a66a" />
    </>
  );
}

export function edgeLabel(
  lens: Lens,
  edge: NileEdge,
  result: EdgePeriodResult | undefined,
  periods: PeriodResult[],
) {
  if (!result) return "";

  if (lens === "stress") {
    const baseline = periods[0].edgeResults.find((item) => item.edgeId === edge.id);
    const ratio = baseline ? result.totalFlow / Math.max(1, baseline.totalFlow) : 1;
    return `${Math.round(ratio * 100)}% of baseline`;
  }

  return `${format(result.totalFlow)} ${WATER_VOLUME_UNIT_COMPACT} flow`;
}

export function edgeWidth(result: EdgePeriodResult | undefined, max: number) {
  if (!result) return 3;
  return 2.5 + (result.totalFlow / max) * 7;
}

export function nodeRadius(node: NileNode, result: NodePeriodResult | undefined, max: number) {
  if (!result) return node.kind === "reservoir" ? 8 : 5;
  return (node.kind === "reservoir" ? 7 : 4) + (result.totalAvailableWater / max) * 5;
}

export function nodeFill(
  lens: Lens,
  node: NileNode,
  result: NodePeriodResult | undefined,
  periods: PeriodResult[],
) {
  if (!result) return "#39414c";

  if (lens === "stress") {
    const ratio = worstDeliveryRatio(result);
    if (ratio < STRESS_CRITICAL_RATIO) return COLOR_CRITICAL;
    if (ratio < STRESS_WARNING_RATIO) return COLOR_WARNING;
    return "#2f8f5b";
  }

  if (lens === "storage") {
    if (node.kind !== "reservoir" || !node.capacity) return "#5f6269";
    const ratio = result.endingStorage / node.capacity;
    if (ratio < STORAGE_CRITICAL_RATIO) return COLOR_CRITICAL;
    if (ratio < STORAGE_WARNING_RATIO) return COLOR_WARNING;
    return "#38516d";
  }

  if (lens === "production") {
    if (result.hydropower) return "#b17621";
    if (result.irrigation) return "#2f8f5b";
    if (result.drinkingWater) return "#3a8fab";
    return "#5f6269";
  }

  return node.kind === "reservoir" ? "#38516d" : "#3f6472";
}

function worstDeliveryRatio(result: NodePeriodResult) {
  const ratios: number[] = [];
  if (result.drinkingWater && result.drinkingWater.totalTarget > 0) {
    ratios.push(result.drinkingWater.actualDelivery / result.drinkingWater.totalTarget);
  }
  if (result.irrigation && result.irrigation.water.totalTarget > 0) {
    ratios.push(result.irrigation.water.actualDelivery / result.irrigation.water.totalTarget);
  }
  // NRSM has no hydropower demand target — generation is whatever turbines
  // produce given storage and constraints. So power doesn't contribute to a
  // "shortage" stress score; flow retention does.
  const baseline = result.totalIncomingFlow > 0 ? result.totalDownstreamOutflow / Math.max(1, result.totalIncomingFlow) : 1;
  ratios.push(Math.min(1, baseline));
  return Math.min(1, ...ratios);
}
