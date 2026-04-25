import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  FileJson,
  Network,
  RotateCcw,
  Users,
  type LucideIcon,
} from "lucide-react";
import { BasinMap } from "./components/BasinMap";
import { LeftRail } from "./components/LeftRail";
import { ProvenanceBadge } from "./components/ProvenanceBadge";
import { RightRail } from "./components/RightRail";
import { SummaryItem } from "./components/SummaryItem";
import { PitchPage } from "./pages/PitchPage";
import { TeamPage } from "./pages/TeamPage";
import { defaultScenarioRunId, packagedScenarioRuns } from "./data/scenarioCatalog";
import { CUSTOM_SCENARIO_RUN_ID, useVisualizerState } from "./hooks/useVisualizerState";

type SitePage = "visualization" | "pitch" | "team";

const sitePages: Array<{ id: SitePage; label: string; Icon: LucideIcon }> = [
  { id: "visualization", label: "Visualization", Icon: Network },
  { id: "pitch", label: "Pitch", Icon: BookOpen },
  { id: "team", label: "Team", Icon: Users },
];

const SCENARIO_GROUP_ORDER: ReadonlyArray<"Default" | "Extremes" | "Future" | "Past" | "Smoke"> = [
  "Default",
  "Extremes",
  "Future",
  "Past",
  "Smoke",
];

function readPageFromHash(): SitePage {
  const raw = window.location.hash.replace(/^#\/?/, "");
  return sitePages.some((item) => item.id === raw) ? (raw as SitePage) : "visualization";
}

function App() {
  const [page, setPage] = useState<SitePage>(readPageFromHash);
  const state = useVisualizerState({ autoplay: true, playbackActive: page === "visualization" });
  const {
    dataset,
    selectedRunId,
    lens,
    setLens,
    activePeriodIndex,
    setPeriodIndex,
    isPlaying,
    togglePlay,
    pause,
    isLoading,
    loadError,
    selectedNodeId,
    selectedEdgeId,
    setSelectedNodeId,
    setSelectedEdgeId,
    loadPackagedScenario,
    loadJsonFile,
    loadCsvFiles,
  } = state;

  const { metadata, nodes, edges, periods } = dataset;
  const period = periods[activePeriodIndex];
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? nodes[0];
  const selectedNodeResult = period.nodeResults.find((node) => node.nodeId === selectedNode.id);
  const selectedEdge = edges.find((edge) => edge.id === selectedEdgeId) ?? edges[0];
  const selectedEdgeResult = period.edgeResults.find((edge) => edge.edgeId === selectedEdge.id);

  const maxEdgeFlow = useMemo(
    () => Math.max(1, ...periods.flatMap((item) => item.edgeResults.map((edge) => edge.totalRoutedFlow))),
    [periods],
  );
  const maxNodeAvailable = useMemo(
    () => Math.max(1, ...periods.flatMap((item) => item.nodeResults.map((node) => node.totalAvailableWater))),
    [periods],
  );
  const maxLoss = useMemo(
    () => Math.max(1, ...periods.flatMap((item) => item.edgeResults.map((edge) => edge.totalLostFlow))),
    [periods],
  );

  useEffect(() => {
    const sync = () => setPage(readPageFromHash());
    window.addEventListener("hashchange", sync);
    if (!window.location.hash) {
      window.history.replaceState(null, "", "#/visualization");
    }
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  function navigate(nextPage: SitePage) {
    window.location.hash = `/${nextPage}`;
    setPage(nextPage);
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <p className="app-kicker">Fairwater</p>
          <h1>River basin decisions made visible</h1>
          <nav className="site-nav" aria-label="Site pages">
            {sitePages.map(({ id, label, Icon }) => (
              <button
                className={page === id ? "active" : ""}
                key={id}
                onClick={() => navigate(id)}
                type="button"
              >
                <Icon size={16} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
        </div>

        {page === "visualization" ? (
          <div className="scenario-strip" aria-label="Scenario summary">
            <SummaryItem label="Scenario" value={metadata.name} />
            <SummaryItem label="Horizon" value={metadata.horizon} />
            <SummaryItem label="Source" value={metadata.source} />
            <SummaryItem label="Reporting" value={metadata.reporting} />
          </div>
        ) : (
          <div className="site-summary">
            <SummaryItem label="Project" value="Fairwater" />
            <SummaryItem label="Focus" value="Water, food, energy" />
            <SummaryItem label="Engine" value="NRSM Rust" />
          </div>
        )}

        {page === "visualization" && (
          <div className="file-tools">
            <ProvenanceBadge metadata={metadata} />
            <label className="scenario-select-wrap" title="Choose a packaged NRSM scenario run">
              <span>Run</span>
              <select
                disabled={isLoading}
                onChange={(event) => void loadPackagedScenario(event.currentTarget.value)}
                value={selectedRunId}
              >
                {selectedRunId === CUSTOM_SCENARIO_RUN_ID && (
                  <option value={CUSTOM_SCENARIO_RUN_ID}>Uploaded run</option>
                )}
                {SCENARIO_GROUP_ORDER.map((group) => (
                  <optgroup key={group} label={group}>
                    {packagedScenarioRuns
                      .filter((run) => run.group === group)
                      .map((run) => (
                        <option key={run.id} value={run.id}>
                          {run.label}
                        </option>
                      ))}
                  </optgroup>
                ))}
              </select>
            </label>
            <label className="file-button secondary" title="Load NRSM --results-dir CSV files">
              <FileJson size={18} />
              <span>Load CSVs</span>
              <input
                accept=".csv,text/csv"
                multiple
                onChange={(event) => void loadCsvFiles(event.currentTarget.files)}
                type="file"
                {...({ webkitdirectory: "" } as Record<string, string>)}
              />
            </label>
            <label className="file-button" title="Load NRSM JSON output">
              <FileJson size={18} />
              <span>Load JSON</span>
              <input
                accept="application/json,.json"
                onChange={(event) => void loadJsonFile(event.currentTarget.files?.[0] ?? null)}
                type="file"
              />
            </label>
            <button
              className="icon-button"
              disabled={isLoading}
              onClick={() => void loadPackagedScenario(defaultScenarioRunId)}
              title="Reset to sample run"
              type="button"
            >
              <RotateCcw size={17} />
            </button>
          </div>
        )}
      </header>
      {loadError && <div className="load-error">{loadError}</div>}
      {isLoading && (
        <div className="load-status" role="status" aria-live="polite">
          Loading scenario…
        </div>
      )}

      {page === "pitch" ? (
        <PitchPage onOpenVisualization={() => navigate("visualization")} />
      ) : page === "team" ? (
        <TeamPage onOpenVisualization={() => navigate("visualization")} />
      ) : (
        <section className="workspace">
          <LeftRail
            lens={lens}
            onLensChange={setLens}
            period={period}
            periods={periods}
            activePeriodIndex={activePeriodIndex}
            isPlaying={isPlaying}
            onTogglePlay={togglePlay}
            onPeriodChange={(index) => {
              setPeriodIndex(index);
              pause();
            }}
          />

          <BasinMap
            dataset={dataset}
            period={period}
            periods={periods}
            lens={lens}
            selectedNode={selectedNode}
            selectedEdge={selectedEdge}
            maxEdgeFlow={maxEdgeFlow}
            maxNodeAvailable={maxNodeAvailable}
            onSelectNode={setSelectedNodeId}
            onSelectEdge={setSelectedEdgeId}
          />

          <RightRail
            selectedNode={selectedNode}
            selectedNodeResult={selectedNodeResult}
            selectedEdge={selectedEdge}
            selectedEdgeResult={selectedEdgeResult}
            periods={periods}
            activePeriodIndex={activePeriodIndex}
            period={period}
            maxLoss={maxLoss}
          />
        </section>
      )}
    </main>
  );
}

export default App;
