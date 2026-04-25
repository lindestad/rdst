import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  FileJson,
  Network,
  RotateCcw,
  Users,
  type LucideIcon,
} from "lucide-react";
import { datasetFromCsvFiles, datasetFromFile } from "./adapters/nrsm";
import { sampleDataset } from "./data/nile";
import { BasinMap } from "./components/BasinMap";
import { LeftRail } from "./components/LeftRail";
import { RightRail } from "./components/RightRail";
import { SummaryItem } from "./components/SummaryItem";
import { PitchPage } from "./pages/PitchPage";
import { TeamPage } from "./pages/TeamPage";
import { applyScenarioPreset, scenarioLabel } from "./lib/scenarios";
import type { Lens, ScenarioPreset, VisualizerDataset } from "./types";

type SitePage = "visualization" | "pitch" | "team";

const sitePages: Array<{ id: SitePage; label: string; Icon: LucideIcon }> = [
  { id: "visualization", label: "Visualization", Icon: Network },
  { id: "pitch", label: "Pitch", Icon: BookOpen },
  { id: "team", label: "Team", Icon: Users },
];

function readPageFromHash(): SitePage {
  const raw = window.location.hash.replace(/^#\/?/, "");
  return sitePages.some((item) => item.id === raw) ? (raw as SitePage) : "visualization";
}

function App() {
  const [page, setPage] = useState<SitePage>(readPageFromHash);
  const [baseDataset, setBaseDataset] = useState<VisualizerDataset>(sampleDataset);
  const [scenario, setScenario] = useState<ScenarioPreset>("normal");
  const [lens, setLens] = useState<Lens>("stress");
  const [periodIndex, setPeriodIndex] = useState(0);
  const [selectedNodeId, setSelectedNodeId] = useState(sampleDataset.nodes[0].id);
  const [selectedEdgeId, setSelectedEdgeId] = useState(sampleDataset.edges[0].id);
  const [isPlaying, setIsPlaying] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const dataset = useMemo(() => applyScenarioPreset(baseDataset, scenario), [baseDataset, scenario]);
  const { metadata, nodes, edges, periods } = dataset;
  const activePeriodIndex = Math.min(periodIndex, periods.length - 1);

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

  useEffect(() => {
    if (!isPlaying || page !== "visualization") return;
    const timer = window.setInterval(() => {
      setPeriodIndex((current) => (current + 1) % periods.length);
    }, 2200);
    return () => window.clearInterval(timer);
  }, [isPlaying, page, periods.length]);

  useEffect(() => {
    setPeriodIndex(0);
    setSelectedNodeId(dataset.nodes[0]?.id ?? "");
    setSelectedEdgeId(dataset.edges[0]?.id ?? "");
  }, [dataset]);

  async function loadFile(file: File | null) {
    if (!file) return;
    try {
      const next = await datasetFromFile(file);
      setBaseDataset(next);
      setScenario("normal");
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load simulator output.");
    }
  }

  async function loadCsvFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    try {
      const next = await datasetFromCsvFiles(files);
      setBaseDataset(next);
      setScenario("normal");
      setLoadError(null);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "Could not load NRSM CSV results.");
    }
  }

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
            <SummaryItem label="What-if" value={scenarioLabel(scenario)} />
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
                onChange={(event) => void loadFile(event.currentTarget.files?.[0] ?? null)}
                type="file"
              />
            </label>
            <button
              className="icon-button"
              onClick={() => {
                setBaseDataset(sampleDataset);
                setScenario("normal");
                setLoadError(null);
              }}
              title="Reset to sample run"
              type="button"
            >
              <RotateCcw size={17} />
            </button>
          </div>
        )}
      </header>
      {loadError && <div className="load-error">{loadError}</div>}

      {page === "pitch" ? (
        <PitchPage onOpenVisualization={() => navigate("visualization")} />
      ) : page === "team" ? (
        <TeamPage onOpenVisualization={() => navigate("visualization")} />
      ) : (
        <section className="workspace">
          <LeftRail
            lens={lens}
            onLensChange={setLens}
            scenario={scenario}
            onScenarioChange={setScenario}
            period={period}
            periods={periods}
            activePeriodIndex={activePeriodIndex}
            isPlaying={isPlaying}
            onTogglePlay={() => setIsPlaying((current) => !current)}
            onPeriodChange={(index) => {
              setPeriodIndex(index);
              setIsPlaying(false);
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
