import type { ReactNode } from "react";
import { format, signed } from "../lib/format";
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
  const delta = result && baseline ? (result.totalReceivedFlow - baseline.totalReceivedFlow) / baseline.totalReceivedFlow : 0;
  const deltaColor = delta >= 0 ? "#20a66a" : "#d4483c";
  const lossOffset = `${Math.max(58, 92 - edge.lossFraction * 900)}%`;

  if (lens === "loss") {
    return (
      <>
        <stop offset="0%" stopColor="#1e96c8" />
        <stop offset={lossOffset} stopColor="#1e96c8" />
        <stop offset="100%" stopColor="#d4483c" />
      </>
    );
  }

  if (lens === "delta") {
    return (
      <>
        <stop offset="0%" stopColor="#55606e" />
        <stop offset="52%" stopColor="#55606e" />
        <stop offset="100%" stopColor={deltaColor} />
      </>
    );
  }

  if (lens === "food") {
    return (
      <>
        <stop offset="0%" stopColor="#2aa579" />
        <stop offset="100%" stopColor="#79bd52" />
      </>
    );
  }

  if (lens === "power") {
    return (
      <>
        <stop offset="0%" stopColor="#e2b338" />
        <stop offset="100%" stopColor="#f17f3d" />
      </>
    );
  }

  if (lens === "drinking") {
    return (
      <>
        <stop offset="0%" stopColor="#4fb5db" />
        <stop offset="100%" stopColor="#e9f8ff" />
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

  if (lens === "loss") {
    return `${format(result.totalLostFlow)} lost`;
  }

  if (lens === "delta") {
    const baseline = periods[0].edgeResults.find((item) => item.edgeId === edge.id);
    const delta = baseline ? result.totalReceivedFlow - baseline.totalReceivedFlow : 0;
    return signed(delta);
  }

  return `${format(result.totalReceivedFlow)} received`;
}

export function edgeWidth(result: EdgePeriodResult | undefined, max: number) {
  if (!result) return 3;
  return 2.5 + (result.totalRoutedFlow / max) * 7;
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

  if (lens === "food" && result.irrigation) return "#2f8f5b";
  if (lens === "power" && result.hydropower) return "#b17621";
  if (lens === "drinking" && result.drinkingWater) return "#3a8fab";
  if (lens === "loss") return node.kind === "reservoir" ? "#73513d" : "#5f6269";

  if (lens === "delta") {
    const baseline = periods[0].nodeResults.find((item) => item.nodeId === node.id);
    const delta = baseline ? result.totalDownstreamOutflow - baseline.totalDownstreamOutflow : 0;
    return delta >= 0 ? "#2f8f5b" : "#a9423a";
  }

  return node.kind === "reservoir" ? "#38516d" : "#3f6472";
}
