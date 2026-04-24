import type { CsvBundleFiles, DataloaderBundle, EdgeRow, NodeRow, TimeSeriesRow } from "./types";

const fileAliases = {
  nodes: "nodes.csv",
  edges: "edges.csv",
  timeSeries: "time_series.csv",
} as const;

export async function readCsvBundleFromFiles(files: FileList): Promise<CsvBundleFiles> {
  const selected = Array.from(files);
  const lookup = new Map(selected.map((file) => [file.name.toLowerCase(), file]));

  const nodes = lookup.get(fileAliases.nodes);
  const edges = lookup.get(fileAliases.edges);
  const timeSeries = lookup.get(fileAliases.timeSeries);

  if (!nodes || !edges || !timeSeries) {
    throw new Error("Select nodes.csv, edges.csv, and time_series.csv together.");
  }

  return {
    nodes: await nodes.text(),
    edges: await edges.text(),
    timeSeries: await timeSeries.text(),
  };
}

export function parseBundle(sourceLabel: string, files: CsvBundleFiles): DataloaderBundle {
  return {
    sourceLabel,
    nodes: parseCsv<NodeRow>(files.nodes),
    edges: parseCsv<EdgeRow>(files.edges),
    timeSeries: parseCsv<TimeSeriesRow>(files.timeSeries),
  };
}

export function parseCsv<T extends Record<string, string>>(text: string): T[] {
  const rows = parseCsvRows(text.trim());
  const [headers, ...body] = rows;

  if (!headers?.length) {
    return [];
  }

  const normalizedHeaders = headers.map((header) => header.trim());

  return body
    .filter((row) => row.some((cell) => cell.trim().length > 0))
    .map((row) => {
      const record: Record<string, string> = {};
      normalizedHeaders.forEach((header, index) => {
        record[header] = row[index]?.trim() ?? "";
      });
      return record as T;
    });
}

function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"' && inQuotes && next === '"') {
      cell += '"';
      index += 1;
      continue;
    }

    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(cell);
      cell = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") {
        index += 1;
      }
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      continue;
    }

    cell += char;
  }

  row.push(cell);
  rows.push(row);

  return rows;
}
