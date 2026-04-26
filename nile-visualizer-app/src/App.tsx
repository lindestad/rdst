import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  FileJson,
  GitCompareArrows,
  Network,
  RotateCcw,
  Users,
  type LucideIcon,
} from "lucide-react";
import { BasinMap } from "./components/BasinMap";
import { LeftRail } from "./components/LeftRail";
import { ProvenanceBadge } from "./components/ProvenanceBadge";
import { RightRail } from "./components/RightRail";
import { ScenarioPage } from "./pages/ScenarioPage";
import { ShowcasePage } from "./pages/ShowcasePage";
import { TeamPage } from "./pages/TeamPage";
import { defaultScenarioRunId, packagedScenarioRuns } from "./data/scenarioCatalog";
import { CUSTOM_SCENARIO_RUN_ID, useVisualizerState } from "./hooks/useVisualizerState";

type SitePage = "visualization" | "scenarios" | "showcase" | "team";

const sitePages: Array<{ id: SitePage; label: string; Icon: LucideIcon }> = [
  { id: "showcase", label: "Showcase", Icon: BookOpen },
  { id: "scenarios", label: "Scenarios", Icon: GitCompareArrows },
  { id: "visualization", label: "Simulator", Icon: Network },
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
  if (raw === "pitch") return "showcase";
  return sitePages.some((item) => item.id === raw) ? (raw as SitePage) : "showcase";
}

function FairWaterLogo({ small = false }: { small?: boolean }) {
  return (
    <svg
      viewBox="0 0 110.07 40.42"
      xmlns="http://www.w3.org/2000/svg"
      style={{ height: small ? 22 : 28, width: "auto" }}
      aria-hidden="true"
    >
      <g transform="translate(-19.29,-50.75)">
        <g>
          <circle fill="#2fa46f" cx="28.74" cy="76.52" r="5" />
          <circle fill="#2fa46f" cx="21.34" cy="67.93" r="2.06" />
          <circle fill="#2fa46f" cx="44.80" cy="72.03" r="2.06" />
          <circle fill="#2fa46f" cx="36.28" cy="64.47" r="2.06" />
          <circle fill="#2fa46f" cx="27.85" cy="60.86" r="2.06" />
          <circle fill="#2fa46f" cx="27.54" cy="53.06" r="2.06" />
          <path stroke="#2fa46f" strokeWidth="1" fill="none" d="M28.74,76.52 21.34,67.93 27.85,60.86 27.54,53.06" />
          <path stroke="#2fa46f" strokeWidth="1" fill="none" d="m44.80,72.03 -8.52-7.57 -8.43-3.61" />
          <circle fill="#0b4f6c" cx="48.72" cy="71.78" r="2.06" />
          <circle fill="#0b4f6c" cx="40.21" cy="64.22" r="2.06" />
          <circle fill="#0b4f6c" cx="31.78" cy="60.61" r="2.06" />
          <circle fill="#0b4f6c" cx="31.47" cy="52.81" r="2.06" />
          <circle fill="#0b4f6c" cx="32.67" cy="76.27" r="5" />
          <circle fill="#0b4f6c" cx="25.27" cy="67.68" r="2.06" />
          <path stroke="#0b4f6c" strokeWidth="1" fill="none" d="M32.67,76.27 25.27,67.68 31.78,60.61 31.47,52.81" />
          <path stroke="#0b4f6c" strokeWidth="1" fill="none" d="m48.72,71.78 -8.52-7.57 -8.43-3.61" />
        </g>
        <text fontFamily="DM Sans, sans-serif" fontWeight="700" fontSize="17.64" x="42.55" y="90.99">
          <tspan fill="#2fa46f">Fair</tspan>
          <tspan fill="#ffffff">Water</tspan>
        </text>
      </g>
    </svg>
  );
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
  const hasData = periods.length > 0 && nodes.length > 0;
  const period = hasData ? periods[activePeriodIndex] : undefined;
  const selectedNode = hasData ? (nodes.find((node) => node.id === selectedNodeId) ?? nodes[0]) : undefined;
  const selectedNodeResult = period && selectedNode
    ? period.nodeResults.find((node) => node.nodeId === selectedNode.id)
    : undefined;
  const selectedEdge = edges.length > 0
    ? (edges.find((edge) => edge.id === selectedEdgeId) ?? edges[0])
    : undefined;
  const selectedEdgeResult = period && selectedEdge
    ? period.edgeResults.find((edge) => edge.edgeId === selectedEdge.id)
    : undefined;

  const maxEdgeFlow = useMemo(
    () => Math.max(1, ...periods.flatMap((item) => item.edgeResults.map((edge) => edge.totalFlow))),
    [periods],
  );
  const maxNodeAvailable = useMemo(
    () => Math.max(1, ...periods.flatMap((item) => item.nodeResults.map((node) => node.totalAvailableWater))),
    [periods],
  );

  useEffect(() => {
    const sync = () => setPage(readPageFromHash());
    window.addEventListener("hashchange", sync);
    if (!window.location.hash) {
      window.history.replaceState(null, "", "#/showcase");
    }
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  function navigate(nextPage: SitePage) {
    window.location.hash = `/${nextPage}`;
    setPage(nextPage);
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  const isShowcase = page === "showcase";
  const shellClass = `app-shell${isShowcase ? " showcase-active" : ""}`;

  return (
    <main className={shellClass}>
      <header className="topbar">
        <div className="brand-block">
          <a className="brand-mark" href="#/showcase" onClick={(event) => { event.preventDefault(); navigate("showcase"); }}>
            <FairWaterLogo />
          </a>
          {!isShowcase && (
            <span className="brand-meta">
              {page === "visualization"
                ? "Live Simulator"
                : page === "scenarios"
                  ? "Scenario Benchmarks"
                  : "Project Team"}
            </span>
          )}
          <nav className="site-nav" aria-label="Site pages">
            {sitePages.map(({ id, label, Icon }) => (
              <button
                className={page === id ? "active" : ""}
                key={id}
                onClick={() => navigate(id)}
                type="button"
              >
                <Icon size={14} />
                <span>{label}</span>
              </button>
            ))}
          </nav>
        </div>

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
            <label className="file-button" title="Load NRSM --results-dir CSV files">
              <FileJson size={16} />
              <span>CSV</span>
              <input
                accept=".csv,text/csv"
                multiple
                onChange={(event) => void loadCsvFiles(event.currentTarget.files)}
                type="file"
                {...({ webkitdirectory: "" } as Record<string, string>)}
              />
            </label>
            <label className="file-button" title="Load NRSM JSON output">
              <FileJson size={16} />
              <span>JSON</span>
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
              <RotateCcw size={16} />
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

      {page === "showcase" ? (
        <ShowcasePage onOpenVisualization={() => navigate("visualization")} />
      ) : page === "scenarios" ? (
        <ScenarioPage onOpenVisualization={() => navigate("visualization")} />
      ) : page === "team" ? (
        <TeamPage onOpenVisualization={() => navigate("visualization")} />
      ) : !hasData || !period || !selectedNode || !selectedEdge ? (
        <section className="empty-state" role="status">
          <h2>No simulator data loaded.</h2>
          <p>Pick a packaged run, upload an NRSM JSON, or load a results-dir of CSVs to begin.</p>
        </section>
      ) : (
        <section className="workspace">
          <LeftRail
            lens={lens}
            metadata={metadata}
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
          />
        </section>
      )}
    </main>
  );
}

export default App;
