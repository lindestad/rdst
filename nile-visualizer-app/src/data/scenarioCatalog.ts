import { datasetFromCsvTextByNode } from "../adapters/nrsm";
import type { VisualizerDataset } from "../types";

type ScenarioGroup = "Default" | "Past" | "Future" | "Extremes" | "Smoke";

export type PackagedScenarioRun = {
  id: string;
  label: string;
  group: ScenarioGroup;
  horizon: string;
  reporting: string;
  summary: string;
};

const scenarioCsvFiles = import.meta.glob("./results/scenarios/**/*.csv", {
  eager: true,
  import: "default",
  query: "?raw",
}) as Record<string, string>;

export const defaultScenarioRunId = "scenario";

export const packagedScenarioRuns: PackagedScenarioRun[] = [
  {
    id: "scenario",
    label: "Default demo",
    group: "Default",
    horizon: "90 days",
    reporting: "30-day periods",
    summary: "Baseline Nile MVP simulator run.",
  },
  {
    id: "past__1963-september-30d",
    label: "1963 wet September",
    group: "Past",
    horizon: "30 days",
    reporting: "daily",
    summary: "Historic wet-season run.",
  },
  {
    id: "past__2005-jan-7d-baseline",
    label: "2005 January baseline",
    group: "Past",
    horizon: "7 days",
    reporting: "daily",
    summary: "Short baseline smoke run.",
  },
  {
    id: "past__2005-q1-90d-baseline",
    label: "2005 Q1 baseline",
    group: "Past",
    horizon: "90 days",
    reporting: "30-day periods",
    summary: "Quarterly baseline.",
  },
  {
    id: "past__2010-dry-season-180d",
    label: "2010 dry season",
    group: "Past",
    horizon: "180 days",
    reporting: "30-day periods",
    summary: "Lower inflow and higher evaporation.",
  },
  {
    id: "past__2012-wet-season-120d",
    label: "2012 wet season",
    group: "Past",
    horizon: "120 days",
    reporting: "30-day periods",
    summary: "Higher inflow wet-season run.",
  },
  {
    id: "past__2015-low-storage-30d",
    label: "2015 low storage",
    group: "Past",
    horizon: "30 days",
    reporting: "daily",
    summary: "Lower starting reservoir storage.",
  },
  {
    id: "past__2018-energy-prices-365d",
    label: "2018 energy prices",
    group: "Past",
    horizon: "365 days",
    reporting: "30-day periods",
    summary: "Higher hydropower price scenario.",
  },
  {
    id: "past__2020-full-year-balanced",
    label: "2020 balanced year",
    group: "Past",
    horizon: "365 days",
    reporting: "30-day periods",
    summary: "Full-year balanced operation.",
  },
  {
    id: "past__2024-hot-60d",
    label: "2024 hot short run",
    group: "Past",
    horizon: "60 days",
    reporting: "daily",
    summary: "Hot short operational window.",
  },
  {
    id: "past__2026-spring-45d",
    label: "2026 spring check",
    group: "Past",
    horizon: "45 days",
    reporting: "daily",
    summary: "Recent operations check.",
  },
  {
    id: "future__2027-30d-operations-check",
    label: "2027 operations check",
    group: "Future",
    horizon: "30 days",
    reporting: "daily",
    summary: "Near-term operations check.",
  },
  {
    id: "future__2030-flood-pulse-45d",
    label: "2030 flood pulse",
    group: "Future",
    horizon: "45 days",
    reporting: "daily",
    summary: "High inflow pulse.",
  },
  {
    id: "future__2030-full-year-growth",
    label: "2030 demand growth",
    group: "Future",
    horizon: "365 days",
    reporting: "30-day periods",
    summary: "Full-year demand growth.",
  },
  {
    id: "future__2035-two-year-dry",
    label: "2035 two-year dry",
    group: "Future",
    horizon: "730 days",
    reporting: "30-day periods",
    summary: "Extended dry run.",
  },
  {
    id: "future__2040-energy-transition-365d",
    label: "2040 energy transition",
    group: "Future",
    horizon: "365 days",
    reporting: "30-day periods",
    summary: "Lower energy price scenario.",
  },
  {
    id: "future__2045-demand-growth-180d",
    label: "2045 demand growth",
    group: "Future",
    horizon: "180 days",
    reporting: "30-day periods",
    summary: "Higher drinking and food demand.",
  },
  {
    id: "future__2050-five-year-stress",
    label: "2050 five-year stress",
    group: "Future",
    horizon: "1826 days",
    reporting: "30-day periods",
    summary: "Long stress test.",
  },
  {
    id: "future__2060-hot-low-inflow-90d",
    label: "2060 hot low inflow",
    group: "Future",
    horizon: "90 days",
    reporting: "30-day periods",
    summary: "Hot and low inflow.",
  },
  {
    id: "future__2075-short-emergency-14d",
    label: "2075 emergency",
    group: "Future",
    horizon: "14 days",
    reporting: "daily",
    summary: "Emergency short run.",
  },
  {
    id: "future__2100-long-range-365d",
    label: "2100 long range",
    group: "Future",
    horizon: "365 days",
    reporting: "30-day periods",
    summary: "Long-range annual run.",
  },
  {
    id: "extremes__upstream-holdback-90d",
    label: "Upstream holdback",
    group: "Extremes",
    horizon: "90 days",
    reporting: "30-day periods",
    summary: "GERD releases are constrained to retain more upstream water.",
  },
  {
    id: "few-nodes__blue-nile-2030-30d",
    label: "Blue Nile smoke",
    group: "Smoke",
    horizon: "30 days",
    reporting: "daily",
    summary: "Small three-node Blue Nile run.",
  },
];

export const sampleDataset = datasetForPackagedScenario(defaultScenarioRunId);

export function datasetForPackagedScenario(id: string): VisualizerDataset {
  const run = packagedScenarioRuns.find((candidate) => candidate.id === id);
  if (!run) {
    throw new Error(`Unknown packaged scenario run: ${id}`);
  }

  return datasetFromCsvTextByNode(csvByNodeForScenario(id), {
    name: run.label,
    source: `Packaged NRSM run: ${run.id}`,
    horizon: run.horizon,
    reporting: run.reporting,
    units: "NRSM model units per reporting period",
  });
}

function csvByNodeForScenario(id: string) {
  const prefix = `./results/scenarios/${id}/`;
  const entries = Object.entries(scenarioCsvFiles).filter(([path]) => path.startsWith(prefix));
  if (entries.length === 0) {
    throw new Error(`No packaged CSV files found for scenario run: ${id}`);
  }

  return Object.fromEntries(
    entries.flatMap(([path, content]) => {
      const filename = path.slice(prefix.length);
      const nodeId = filename.replace(/\.csv$/i, "");
      return nodeId === "summary" ? [] : [[nodeId, content] as const];
    }),
  );
}
