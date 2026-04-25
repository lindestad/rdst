import { useMemo } from "react";
import { Locate, Minus, Plus } from "lucide-react";
import { VIEWBOX_H, VIEWBOX_W, ZOOM_BUTTON_FACTOR } from "../config";
import { osmTiles } from "../lib/geo";
import { useMapView } from "../hooks/useMapView";
import { CountryLabels, ImpactZoneOverlay, RegionAnnotations } from "./MapOverlays";
import { edgeLabel, edgeStops, edgeWidth, nodeFill, nodeRadius } from "./mapStyling";
import { layoutMapEdges, layoutMapNodes } from "../lib/mapLayout";
import type {
  Lens,
  NileEdge,
  NileNode,
  PeriodResult,
  VisualizerDataset,
} from "../types";

type BasinMapProps = {
  dataset: VisualizerDataset;
  period: PeriodResult;
  periods: PeriodResult[];
  lens: Lens;
  selectedNode: NileNode;
  selectedEdge: NileEdge;
  maxEdgeFlow: number;
  maxNodeAvailable: number;
  onSelectNode: (id: string) => void;
  onSelectEdge: (id: string) => void;
};

export function BasinMap({
  dataset,
  period,
  periods,
  lens,
  selectedNode,
  selectedEdge,
  maxEdgeFlow,
  maxNodeAvailable,
  onSelectNode,
  onSelectEdge,
}: BasinMapProps) {
  const { nodes, edges } = dataset;
  const nodeLayouts = useMemo(() => layoutMapNodes(nodes), [nodes]);
  const layoutById = useMemo(
    () => new Map(nodeLayouts.map((layout) => [layout.id, layout])),
    [nodeLayouts],
  );
  const displayNodes = useMemo(
    () => nodes.map((node) => {
      const layout = layoutById.get(node.id);
      return layout ? { ...node, x: layout.x, y: layout.y } : node;
    }),
    [layoutById, nodes],
  );
  const displayEdges = useMemo(() => layoutMapEdges(edges, nodeLayouts), [edges, nodeLayouts]);
  const {
    svgRef,
    view,
    isPanning,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    zoomCenter,
    resetView,
    guardedClick,
  } = useMapView();

  return (
    <section className="map-surface" aria-label="Nile basin decision map">
      <div className="map-toolbar">
        <div>
          <p className="control-label">Active window</p>
          <strong>
            Days {period.startDay + 1}-{period.endDayExclusive}
          </strong>
        </div>
        <div className="legend">
          <span className="legend-item flow">Runoff / release</span>
          <span className="legend-item warning-swatch">Allocation strain</span>
          <span className="legend-item critical-swatch">Severe shortage</span>
          <span className="risk-note">
            Scribbled areas mark regions where this preset creates water, food, storage, or power stress.
          </span>
        </div>
      </div>

      <div className="map-zoom-controls" aria-label="Map zoom controls">
        <button
          className="icon-button"
          onClick={() => zoomCenter(ZOOM_BUTTON_FACTOR)}
          title="Zoom in"
          aria-label="Zoom in"
          type="button"
        >
          <Plus size={16} />
        </button>
        <button
          className="icon-button"
          onClick={() => zoomCenter(1 / ZOOM_BUTTON_FACTOR)}
          title="Zoom out"
          aria-label="Zoom out"
          type="button"
        >
          <Minus size={16} />
        </button>
        <button
          className="icon-button"
          onClick={resetView}
          title="Reset view"
          aria-label="Reset view"
          type="button"
        >
          <Locate size={16} />
        </button>
      </div>

      <svg
        className={`basin-map ${isPanning ? "panning" : ""}`}
        viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
        preserveAspectRatio="xMidYMin meet"
        role="img"
        aria-label="Nile simulator graph"
        ref={svgRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <defs>
          <clipPath id="basin-clip">
            <rect x="24" y="18" width="992" height="684" rx="8" />
          </clipPath>
          <pattern id="scribble-critical" width="38" height="38" patternUnits="userSpaceOnUse">
            <path d="M-6 6 Q 4 -2 13 7 T 28 10 T 44 4" fill="none" stroke="#c8362a" strokeWidth="1.7" strokeLinecap="round" opacity="0.95" />
            <path d="M-6 14 Q 6 6 16 15 T 30 18 T 46 12" fill="none" stroke="#a52d22" strokeWidth="1.6" strokeLinecap="round" opacity="0.88" />
            <path d="M-6 22 Q 4 14 13 23 T 28 26 T 44 20" fill="none" stroke="#c8362a" strokeWidth="1.8" strokeLinecap="round" opacity="0.95" />
            <path d="M-6 30 Q 6 22 16 31 T 30 34 T 46 28" fill="none" stroke="#891f17" strokeWidth="1.5" strokeLinecap="round" opacity="0.85" />
            <path d="M5 -4 L 9 10 L 3 22 L 11 32 L 5 42" fill="none" stroke="#a52d22" strokeWidth="1.1" strokeLinecap="round" opacity="0.6" />
            <path d="M22 -4 L 17 12 L 24 24 L 19 36 L 24 44" fill="none" stroke="#c8362a" strokeWidth="1.1" strokeLinecap="round" opacity="0.55" />
            <path d="M34 -4 L 30 12 L 36 24 L 32 36 L 36 44" fill="none" stroke="#891f17" strokeWidth="1.0" strokeLinecap="round" opacity="0.55" />
          </pattern>
          <pattern id="scribble-warning" width="24" height="24" patternUnits="userSpaceOnUse" patternTransform="rotate(38)">
            <line x1="0" y1="0" x2="0" y2="24" stroke="#b07c1a" strokeWidth="2.0" opacity="0.85" />
            <line x1="12" y1="0" x2="12" y2="24" stroke="#8a6213" strokeWidth="1.4" opacity="0.7" />
            <line x1="6" y1="0" x2="6" y2="24" stroke="#d89b24" strokeWidth="0.9" opacity="0.55" />
            <line x1="18" y1="0" x2="18" y2="24" stroke="#d89b24" strokeWidth="0.9" opacity="0.55" />
          </pattern>
          {displayEdges.map((edge) => {
            const edgeResult = period.edgeResults.find((result) => result.edgeId === edge.id);
            return (
              <linearGradient
                gradientUnits="userSpaceOnUse"
                id={`edge-gradient-${edge.id}`}
                key={edge.id}
                x1={edge.gradient.x1}
                x2={edge.gradient.x2}
                y1={edge.gradient.y1}
                y2={edge.gradient.y2}
              >
                {edgeStops(lens, edge, edgeResult, periods)}
              </linearGradient>
            );
          })}
        </defs>

        <rect className="basin-frame" x="24" y="18" width="992" height="684" rx="8" />

        <g className="map-clip-layer" clipPath="url(#basin-clip)">
        <g
          className="map-pan-layer"
          transform={`translate(${view.tx} ${view.ty}) scale(${view.k})`}
        >
          <g className="basin-basemap">
            {osmTiles.map((tile) => (
              <image
                className="map-tile"
                height={tile.height}
                href={tile.href}
                key={tile.key}
                preserveAspectRatio="none"
                width={tile.width}
                x={tile.x}
                y={tile.y}
              />
            ))}
          </g>

          <ImpactZoneOverlay nodes={nodes} period={period} periods={periods} />

          <CountryLabels />

          <g className="edge-layer">
            {displayEdges.map((edge) => {
              const edgeResult = period.edgeResults.find((result) => result.edgeId === edge.id);
              const strokeWidth = edgeWidth(edgeResult, maxEdgeFlow);

              return (
                <g className="edge-group" key={edge.id}>
                  <path className="edge-shadow" d={edge.path} strokeWidth={strokeWidth + 10} />
                  <path
                    className={`edge-line ${selectedEdge.id === edge.id ? "selected" : ""}`}
                    d={edge.path}
                    onClick={guardedClick(() => onSelectEdge(edge.id))}
                    stroke={`url(#edge-gradient-${edge.id})`}
                    strokeWidth={strokeWidth}
                  />
                  <path
                    className="edge-flow-tracer"
                    d={edge.path}
                    strokeWidth={Math.max(2, strokeWidth * 0.45)}
                  />
                  <text className="edge-loss-label">
                    <textPath href={`#edge-label-${edge.id}`} startOffset="50%">
                      {edgeLabel(lens, edge, edgeResult, periods)}
                    </textPath>
                  </text>
                  <path className="edge-label-path" d={edge.path} id={`edge-label-${edge.id}`} />
                </g>
              );
            })}
          </g>

          <g className="node-layer">
            <g className="node-leader-layer" pointerEvents="none">
              {nodeLayouts.map((layout) => {
                const offset = Math.hypot(layout.x - layout.anchorX, layout.y - layout.anchorY);
                if (offset < 5) return null;
                return (
                  <line
                    className={`node-leader ${selectedNode.id === layout.id ? "selected" : ""}`}
                    key={`leader-${layout.id}`}
                    x1={layout.anchorX}
                    y1={layout.anchorY}
                    x2={layout.x}
                    y2={layout.y}
                  />
                );
              })}
            </g>
            {nodes.map((node) => {
              const nodeResult = period.nodeResults.find((result) => result.nodeId === node.id);
              const radius = nodeRadius(node, nodeResult, maxNodeAvailable);
              const fill = nodeFill(lens, node, nodeResult, periods);
              const isReservoir = node.kind === "reservoir";
              const layout = layoutById.get(node.id) ?? {
                x: node.x,
                y: node.y,
                labelX: node.x,
                labelY: node.y + radius + 18,
                labelAnchor: "middle" as const,
              };

              return (
                <g
                  className={`node ${isReservoir ? "reservoir" : "river"} ${selectedNode.id === node.id ? "selected" : ""}`}
                  key={node.id}
                  onClick={guardedClick(() => onSelectNode(node.id))}
                  transform={`translate(${layout.x} ${layout.y})`}
                >
                  <title>{node.name}</title>
                  {isReservoir ? (
                    <>
                      <rect
                        className="node-body"
                        fill={fill}
                        x={-radius - 1}
                        y={-radius - 1}
                        width={(radius + 1) * 2}
                        height={(radius + 1) * 2}
                        rx={2}
                      />
                      <path
                        className="node-glyph"
                        d={`M ${-radius + 1.5} ${-radius * 0.45} L ${radius - 1.5} ${-radius * 0.45} M ${-radius + 1.5} ${radius * 0.15} L ${radius - 1.5} ${radius * 0.15} M ${-radius + 1.5} ${radius * 0.7} L ${radius - 1.5} ${radius * 0.7}`}
                      />
                    </>
                  ) : (
                    <>
                      <circle className="node-halo" r={radius + 5} />
                      <circle className="node-body" fill={fill} r={radius} />
                    </>
                  )}
                  <text
                    className="node-label"
                    textAnchor={layout.labelAnchor}
                    x={layout.labelX - layout.x}
                    y={layout.labelY - layout.y}
                  >
                    {node.shortName}
                  </text>
                </g>
              );
            })}
          </g>

          <RegionAnnotations
            nodes={displayNodes}
            period={period}
            periods={periods}
            selectedNodeId={selectedNode.id}
          />
        </g>
        </g>

        <text className="map-attribution" x={994} y={690}>
          © OpenStreetMap contributors
        </text>
      </svg>
    </section>
  );
}
