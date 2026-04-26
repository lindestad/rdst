import type { RunMetadata, RunOrigin } from "../types";

const ORIGIN_LABELS: Record<RunOrigin, string> = {
  packaged: "Packaged run",
  "uploaded-csv": "Uploaded CSVs",
  "uploaded-json": "Uploaded JSON",
  sample: "Sample run",
};

const ORIGIN_TONES: Record<RunOrigin, string> = {
  packaged: "ok",
  "uploaded-csv": "user",
  "uploaded-json": "user",
  sample: "muted",
};

export function ProvenanceBadge({ metadata }: { metadata: RunMetadata }) {
  const origin = metadata.origin;
  const tone = ORIGIN_TONES[origin] ?? "muted";
  const detail = [
    metadata.runId,
    metadata.schemaVersion ? `schema ${metadata.schemaVersion}` : null,
    metadata.assembledAt ? `built ${metadata.assembledAt}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <span className={`provenance-badge ${tone}`} title={detail || metadata.source}>
      <span className="provenance-dot" aria-hidden="true" />
      <span className="provenance-label">{ORIGIN_LABELS[origin] ?? origin}</span>
      {detail && <span className="provenance-detail">{detail}</span>}
    </span>
  );
}
