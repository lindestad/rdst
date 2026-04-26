import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { datasetFromCsvFiles, datasetFromFile } from "../adapters/nrsm";
import {
  defaultScenarioRunId,
  loadDatasetForPackagedScenario,
  sampleDataset,
} from "../data/scenarioCatalog";
import { PLAYBACK_INTERVAL_MS } from "../config";
import type { Lens, VisualizerDataset } from "../types";

const CUSTOM_RUN_ID = "custom";

export type VisualizerState = {
  dataset: VisualizerDataset;
  selectedRunId: string;
  lens: Lens;
  setLens: (lens: Lens) => void;
  periodIndex: number;
  activePeriodIndex: number;
  setPeriodIndex: (index: number) => void;
  isPlaying: boolean;
  togglePlay: () => void;
  pause: () => void;
  isLoading: boolean;
  loadError: string | null;
  selectedNodeId: string;
  selectedEdgeId: string;
  setSelectedNodeId: (id: string) => void;
  setSelectedEdgeId: (id: string) => void;
  loadPackagedScenario: (runId: string) => Promise<void>;
  loadJsonFile: (file: File | null) => Promise<void>;
  loadCsvFiles: (files: FileList | null) => Promise<void>;
};

export function useVisualizerState(options: { autoplay?: boolean; playbackActive?: boolean } = {}): VisualizerState {
  const playbackActive = options.playbackActive ?? true;
  const [dataset, setDataset] = useState<VisualizerDataset>(sampleDataset);
  const [selectedRunId, setSelectedRunId] = useState(defaultScenarioRunId);
  const [lens, setLens] = useState<Lens>("stress");
  const [periodIndex, setPeriodIndex] = useState(0);
  const [selectedNodeId, setSelectedNodeId] = useState(sampleDataset.nodes[0]?.id ?? "");
  const [selectedEdgeId, setSelectedEdgeId] = useState(sampleDataset.edges[0]?.id ?? "");
  const [isPlaying, setIsPlaying] = useState(options.autoplay ?? true);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Guards against late-arriving dataset loads that have been superseded.
  const loadIdRef = useRef(0);

  const periods = dataset.periods;
  const activePeriodIndex = Math.min(periodIndex, periods.length - 1);

  useEffect(() => {
    setPeriodIndex(0);
    setSelectedNodeId(dataset.nodes[0]?.id ?? "");
    setSelectedEdgeId(dataset.edges[0]?.id ?? "");
  }, [dataset]);

  useEffect(() => {
    if (!isPlaying || !playbackActive || periods.length <= 1) return;
    const timer = window.setInterval(() => {
      setPeriodIndex((current) => (current + 1) % periods.length);
    }, PLAYBACK_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [isPlaying, playbackActive, periods.length]);

  const applyLoad = useCallback(
    async (runId: string, work: () => Promise<VisualizerDataset>) => {
      const ticket = ++loadIdRef.current;
      setIsLoading(true);
      setLoadError(null);
      try {
        const next = await work();
        if (loadIdRef.current !== ticket) return;
        setDataset(next);
        setSelectedRunId(runId);
      } catch (error) {
        if (loadIdRef.current !== ticket) return;
        setLoadError(error instanceof Error ? error.message : "Could not load simulator output.");
      } finally {
        if (loadIdRef.current === ticket) setIsLoading(false);
      }
    },
    [],
  );

  const loadPackagedScenario = useCallback(
    (runId: string) => applyLoad(runId, () => loadDatasetForPackagedScenario(runId)),
    [applyLoad],
  );

  const loadJsonFile = useCallback(
    async (file: File | null) => {
      if (!file) return;
      await applyLoad(CUSTOM_RUN_ID, () => datasetFromFile(file));
    },
    [applyLoad],
  );

  const loadCsvFilesHandler = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      await applyLoad(CUSTOM_RUN_ID, () => datasetFromCsvFiles(files));
    },
    [applyLoad],
  );

  const togglePlay = useCallback(() => setIsPlaying((current) => !current), []);
  const pause = useCallback(() => setIsPlaying(false), []);

  return useMemo<VisualizerState>(
    () => ({
      dataset,
      selectedRunId,
      lens,
      setLens,
      periodIndex,
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
      loadCsvFiles: loadCsvFilesHandler,
    }),
    [
      dataset,
      selectedRunId,
      lens,
      periodIndex,
      activePeriodIndex,
      isPlaying,
      isLoading,
      loadError,
      selectedNodeId,
      selectedEdgeId,
      togglePlay,
      pause,
      loadPackagedScenario,
      loadJsonFile,
      loadCsvFilesHandler,
    ],
  );
}

export const CUSTOM_SCENARIO_RUN_ID = CUSTOM_RUN_ID;
