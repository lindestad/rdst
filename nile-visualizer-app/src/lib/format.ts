import type { NodePeriodResult } from "../types";

export const WATER_VOLUME_UNIT = "million m³";
export const WATER_VOLUME_UNIT_COMPACT = "Mm³";
export const ENERGY_UNIT = "TWh";

export function sumNodes(
  nodesToSum: NodePeriodResult[],
  selector: (node: NodePeriodResult) => number,
) {
  return nodesToSum.reduce((total, node) => total + selector(node), 0);
}

export function format(value: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: value >= 100 ? 0 : 1,
  }).format(value);
}

export function signed(value: number) {
  const rounded = format(Math.abs(value));
  return value >= 0 ? `+${rounded}` : `-${rounded}`;
}
