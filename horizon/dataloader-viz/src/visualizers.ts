export type VisualizerId = "bundle-network" | "source-coverage";

export type VisualizerDefinition = {
  id: VisualizerId;
  name: string;
  eyebrow: string;
  summary: string;
  dataset: string;
  status: "ready" | "planned";
  stats: Array<{
    label: string;
    value: string;
  }>;
  preview: {
    nodes: Array<{ x: number; y: number; r: number }>;
    edges: Array<{ d: string; width: number }>;
  };
};

export const visualizers: VisualizerDefinition[] = [
  {
    id: "bundle-network",
    name: "Normalized Bundle Network",
    eyebrow: "CSV bundle",
    summary: "Topology, metric coverage, QA flags, provenance, and interval lenses for nodes, edges, and time-series rows.",
    dataset: "nodes.csv + edges.csv + time_series.csv",
    status: "ready",
    stats: [
      { label: "Files", value: "3" },
      { label: "Views", value: "Graph + Rows" },
      { label: "Checks", value: "4" },
    ],
    preview: {
      nodes: [
        { x: 54, y: 116, r: 10 },
        { x: 104, y: 88, r: 13 },
        { x: 154, y: 126, r: 10 },
        { x: 210, y: 82, r: 15 },
        { x: 264, y: 108, r: 10 },
      ],
      edges: [
        { d: "M54 116 C78 94 84 92 104 88", width: 7 },
        { d: "M104 88 C126 90 134 118 154 126", width: 10 },
        { d: "M154 126 C176 138 190 96 210 82", width: 8 },
        { d: "M210 82 C232 78 244 98 264 108", width: 11 },
      ],
    },
  },
  {
    id: "source-coverage",
    name: "Source Coverage Matrix",
    eyebrow: "Provenance QA",
    summary: "Cross-checks source products against normalized metrics, entity coverage, quality flags, and unit consistency.",
    dataset: "time_series.csv provenance columns",
    status: "ready",
    stats: [
      { label: "Mode", value: "Matrix" },
      { label: "Rows", value: "Sources" },
      { label: "Cols", value: "Metrics" },
    ],
    preview: {
      nodes: [
        { x: 74, y: 56, r: 8 },
        { x: 128, y: 56, r: 8 },
        { x: 182, y: 56, r: 8 },
        { x: 236, y: 56, r: 8 },
        { x: 74, y: 104, r: 11 },
        { x: 128, y: 104, r: 6 },
        { x: 182, y: 104, r: 10 },
        { x: 236, y: 104, r: 7 },
        { x: 74, y: 142, r: 5 },
        { x: 128, y: 142, r: 10 },
        { x: 182, y: 142, r: 6 },
        { x: 236, y: 142, r: 9 },
      ],
      edges: [
        { d: "M52 78 H268", width: 2 },
        { d: "M52 124 H268", width: 2 },
        { d: "M101 42 V154", width: 2 },
        { d: "M155 42 V154", width: 2 },
        { d: "M209 42 V154", width: 2 },
      ],
    },
  },
];
