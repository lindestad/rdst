import type { CsvBundleFiles } from "./types";

const nodes = [
  ["nile-mvp", "lake_victoria_outlet", "Lake Victoria Outlet", "river", "-0.32", "33.18", "UGA", "hybas_112042", "", "", "", "", "", "White Nile headwater proxy"],
  ["nile-mvp", "sudd_wetland", "Sudd Wetland", "river", "7.61", "30.39", "SSD", "hybas_112088", "", "", "", "0.9", "", "High loss wetland reach"],
  ["nile-mvp", "malakal", "Malakal White Nile", "river", "9.53", "31.66", "SSD", "hybas_112095", "", "", "", "", "", "White Nile control point"],
  ["nile-mvp", "lake_tana_outlet", "Lake Tana Outlet", "river", "12.02", "37.25", "ETH", "hybas_112117", "", "", "", "", "", "Blue Nile headwater proxy"],
  ["nile-mvp", "gerd", "GERD", "reservoir", "11.21", "35.09", "ETH", "hybas_112121", "950", "250", "500", "", "0.68", "Reservoir and hydropower node"],
  ["nile-mvp", "roseires", "Roseires Dam", "reservoir", "11.80", "34.39", "SDN", "hybas_112133", "420", "120", "260", "", "0.31", "Reservoir and hydropower node"],
  ["nile-mvp", "gezira_irrigation", "Gezira Irrigation Scheme", "river", "14.43", "33.50", "SDN", "hybas_112144", "", "", "", "1.2", "", "Irrigation demand proxy"],
  ["nile-mvp", "khartoum", "Khartoum Confluence", "river", "15.50", "32.56", "SDN", "hybas_112151", "", "", "", "1.1", "", "Blue and White Nile confluence"],
  ["nile-mvp", "atbara_headwaters", "Atbara Headwaters", "river", "13.61", "36.05", "ETH", "hybas_112170", "", "", "", "", "", "Atbara tributary source"],
  ["nile-mvp", "atbara_confluence", "Atbara Confluence", "river", "17.68", "33.98", "SDN", "hybas_112181", "", "", "", "", "", "Atbara joins Nile"],
  ["nile-mvp", "merowe", "Merowe Dam", "reservoir", "18.67", "32.05", "SDN", "hybas_112191", "720", "180", "420", "", "0.38", "Reservoir and hydropower node"],
  ["nile-mvp", "aswan", "High Aswan", "reservoir", "23.97", "32.88", "EGY", "hybas_112205", "1600", "500", "900", "", "0.59", "Lake Nasser operations proxy"],
  ["nile-mvp", "cairo_municipal", "Cairo Municipal Demand", "river", "30.04", "31.24", "EGY", "hybas_112220", "", "", "", "", "", "Drinking water demand proxy"],
  ["nile-mvp", "egypt_agriculture", "Egypt Agriculture", "river", "30.61", "30.99", "EGY", "hybas_112225", "", "", "", "1.5", "", "Irrigation demand proxy"],
  ["nile-mvp", "nile_delta", "Nile Delta", "river", "31.20", "31.90", "EGY", "hybas_112230", "", "", "", "1.8", "", "Basin exit proxy"],
];

const edges = [
  ["nile-mvp", "lake_victoria_to_sudd", "lake_victoria_outlet", "sudd_wetland", "1.0", "0.04", "8", "White Nile entry reach"],
  ["nile-mvp", "sudd_to_malakal", "sudd_wetland", "malakal", "1.0", "0.45", "16", "Wetland loss reach"],
  ["nile-mvp", "malakal_to_khartoum", "malakal", "khartoum", "1.0", "0.02", "12", "White Nile main stem"],
  ["nile-mvp", "lake_tana_to_gerd", "lake_tana_outlet", "gerd", "1.0", "0.01", "4", "Blue Nile headwater reach"],
  ["nile-mvp", "gerd_to_roseires", "gerd", "roseires", "1.0", "0.015", "3", "Blue Nile regulated reach"],
  ["nile-mvp", "roseires_to_gezira", "roseires", "gezira_irrigation", "1.0", "0.01", "2", "Irrigation supply reach"],
  ["nile-mvp", "gezira_to_khartoum", "gezira_irrigation", "khartoum", "1.0", "0.01", "2", "Return to confluence"],
  ["nile-mvp", "atbara_to_confluence", "atbara_headwaters", "atbara_confluence", "1.0", "0.03", "5", "Atbara tributary"],
  ["nile-mvp", "khartoum_to_atbara_confluence", "khartoum", "atbara_confluence", "1.0", "0.02", "5", "Nile below Khartoum"],
  ["nile-mvp", "atbara_confluence_to_merowe", "atbara_confluence", "merowe", "1.0", "0.02", "4", "Main stem to Merowe"],
  ["nile-mvp", "merowe_to_aswan", "merowe", "aswan", "1.0", "0.025", "9", "Main stem to Lake Nasser"],
  ["nile-mvp", "aswan_to_cairo", "aswan", "cairo_municipal", "1.0", "0.015", "5", "Egypt municipal supply"],
  ["nile-mvp", "cairo_to_egypt_agriculture", "cairo_municipal", "egypt_agriculture", "1.0", "0.01", "2", "Delta irrigation supply"],
  ["nile-mvp", "egypt_agriculture_to_delta", "egypt_agriculture", "nile_delta", "1.0", "0.015", "2", "Delta outlet"],
];

const intervals = [
  ["2026-01-01", "2026-02-01", 1.0],
  ["2026-02-01", "2026-03-01", 1.08],
  ["2026-03-01", "2026-04-01", 0.88],
] as const;

const nodeMetricSeeds = [
  ["lake_victoria_outlet", "local_inflow_million_m3_per_day", 125, "million_m3_per_day", "GloFAS v4.0", "monthly mean converted from discharge"],
  ["sudd_wetland", "local_inflow_million_m3_per_day", 30, "million_m3_per_day", "ERA5-Land", "runoff aggregation"],
  ["malakal", "local_inflow_million_m3_per_day", 18, "million_m3_per_day", "GloFAS v4.0", "control-point discharge"],
  ["lake_tana_outlet", "local_inflow_million_m3_per_day", 170, "million_m3_per_day", "GloFAS v4.0", "monthly mean converted from discharge"],
  ["khartoum", "drinking_target_delivery_million_m3_per_day", 25, "million_m3_per_day", "WorldPop + JMP", "population exposure heuristic"],
  ["khartoum", "irrigation_target_delivery_million_m3_per_day", 20, "million_m3_per_day", "CLMS ET", "crop ET proxy"],
  ["gezira_irrigation", "irrigation_target_delivery_million_m3_per_day", 62, "million_m3_per_day", "CLMS ET", "crop ET proxy"],
  ["gerd", "hydropower_target_mwh_per_day", 130, "MWh_per_day", "Operator factsheet", "capacity proxy"],
  ["roseires", "hydropower_target_mwh_per_day", 55, "MWh_per_day", "WRI power plants", "capacity proxy"],
  ["merowe", "hydropower_target_mwh_per_day", 92, "MWh_per_day", "WRI power plants", "capacity proxy"],
  ["aswan", "hydropower_target_mwh_per_day", 170, "MWh_per_day", "Operator factsheet", "capacity proxy"],
  ["cairo_municipal", "drinking_target_delivery_million_m3_per_day", 62, "million_m3_per_day", "WorldPop + JMP", "population exposure heuristic"],
  ["egypt_agriculture", "irrigation_target_delivery_million_m3_per_day", 135, "million_m3_per_day", "CLMS ET", "crop ET proxy"],
  ["nile_delta", "drinking_target_delivery_million_m3_per_day", 28, "million_m3_per_day", "WorldPop + JMP", "population exposure heuristic"],
] as const;

const edgeFlowSeeds = [
  ["lake_victoria_to_sudd", 125],
  ["sudd_to_malakal", 72],
  ["malakal_to_khartoum", 88],
  ["lake_tana_to_gerd", 170],
  ["gerd_to_roseires", 185],
  ["roseires_to_gezira", 175],
  ["gezira_to_khartoum", 112],
  ["atbara_to_confluence", 70],
  ["khartoum_to_atbara_confluence", 272],
  ["atbara_confluence_to_merowe", 332],
  ["merowe_to_aswan", 260],
  ["aswan_to_cairo", 330],
  ["cairo_to_egypt_agriculture", 260],
  ["egypt_agriculture_to_delta", 118],
] as const;

const timeSeries = [
  ...nodeMetricSeeds.flatMap(([entityId, metric, baseValue, unit, sourceName, transform]) =>
    intervals.map(([start, end, multiplier], index) => [
      "nile-mvp",
      "node",
      entityId,
      metric,
      start,
      end,
      (baseValue * multiplier).toFixed(2),
      unit,
      sourceName,
      "",
      transform,
      index === 2 && metric.includes("irrigation") ? "review" : "ok",
    ]),
  ),
  ...edgeFlowSeeds.flatMap(([entityId, baseValue]) =>
    intervals.map(([start, end, multiplier]) => [
      "nile-mvp",
      "edge",
      entityId,
      "reach_received_flow_million_m3_per_day",
      start,
      end,
      (baseValue * multiplier).toFixed(2),
      "million_m3_per_day",
      "Assembler estimate",
      "",
      "routed flow after configured reach loss",
      "ok",
    ]),
  ),
];

export const sampleBundleFiles: CsvBundleFiles = {
  nodes: toCsv(
    [
      "scenario_id",
      "node_id",
      "name",
      "node_kind",
      "latitude",
      "longitude",
      "country_code",
      "subbasin_id",
      "reservoir_capacity_million_m3",
      "reservoir_min_storage_million_m3",
      "initial_storage_million_m3",
      "food_per_unit_water",
      "energy_per_unit_water",
      "notes",
    ],
    nodes,
  ),
  edges: toCsv(
    [
      "scenario_id",
      "edge_id",
      "from_node_id",
      "to_node_id",
      "flow_share",
      "default_loss_fraction",
      "travel_time_days",
      "notes",
    ],
    edges,
  ),
  timeSeries: toCsv(
    [
      "scenario_id",
      "entity_type",
      "entity_id",
      "metric",
      "interval_start",
      "interval_end",
      "value",
      "unit",
      "source_name",
      "source_url",
      "transform",
      "quality_flag",
    ],
    timeSeries,
  ),
};

function toCsv(headers: string[], rows: ReadonlyArray<ReadonlyArray<string | number>>) {
  return [headers, ...rows]
    .map((row) =>
      row
        .map((cell) => String(cell))
        .map((cell) => (/[",\n\r]/.test(cell) ? `"${cell.replaceAll('"', '""')}"` : cell))
        .join(","),
    )
    .join("\n");
}
