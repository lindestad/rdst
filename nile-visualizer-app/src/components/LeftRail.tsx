import {
  CloudRain,
  Droplets,
  Gauge,
  Pause,
  Play,
  ShieldAlert,
  Sun,
  Waves,
  type LucideIcon,
  Zap,
} from "lucide-react";
import { format, sumNodes } from "../lib/format";
import { scenarioPresets } from "../lib/scenarios";
import type { Lens, PeriodResult, ScenarioPreset } from "../types";

const lensOptions: Array<{ id: Lens; label: string; Icon: LucideIcon }> = [
  { id: "stress", label: "Shortage", Icon: ShieldAlert },
  { id: "water", label: "Runoff", Icon: Waves },
  { id: "storage", label: "Storage", Icon: Droplets },
  { id: "production", label: "Output", Icon: Zap },
];

const scenarioIcons: Record<ScenarioPreset, LucideIcon> = {
  normal: Gauge,
  drought: Sun,
  extreme_rain: CloudRain,
  upstream_holdback: Droplets,
};

type LeftRailProps = {
  lens: Lens;
  onLensChange: (lens: Lens) => void;
  scenario: ScenarioPreset;
  onScenarioChange: (scenario: ScenarioPreset) => void;
  period: PeriodResult;
  periods: PeriodResult[];
  activePeriodIndex: number;
  isPlaying: boolean;
  onTogglePlay: () => void;
  onPeriodChange: (index: number) => void;
};

export function LeftRail({
  lens,
  onLensChange,
  scenario,
  onScenarioChange,
  period,
  periods,
  activePeriodIndex,
  isPlaying,
  onTogglePlay,
  onPeriodChange,
}: LeftRailProps) {
  return (
    <aside className="left-rail" aria-label="Simulation controls">
      <div className="control-group">
        <p className="control-label">Scenario preset</p>
        <div className="scenario-grid">
          {scenarioPresets.map(({ id, label, summary }) => {
            const Icon = scenarioIcons[id];
            return (
              <button
                className={`scenario-button ${scenario === id ? "active" : ""}`}
                key={id}
                onClick={() => onScenarioChange(id)}
                title={summary}
                type="button"
              >
                <Icon size={17} strokeWidth={2.1} />
                <span>{label}</span>
              </button>
            );
          })}
        </div>
        <p className="scenario-help">
          What-if presets are display transforms until simulator-native scenario runs are available.
        </p>
      </div>

      <div className="control-group">
        <p className="control-label">Lens</p>
        <div className="tool-grid">
          {lensOptions.map(({ id, label, Icon }) => (
            <button
              className={`tool-button ${lens === id ? "active" : ""}`}
              key={id}
              onClick={() => onLensChange(id)}
              title={`${label} lens`}
              aria-label={`${label} lens`}
              type="button"
            >
              <Icon size={18} strokeWidth={2.1} />
              <span>{label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="control-group">
        <p className="control-label">Period</p>
        <div className="period-row">
          <button
            className="icon-button"
            onClick={onTogglePlay}
            type="button"
            title={isPlaying ? "Pause playback" : "Play playback"}
            aria-label={isPlaying ? "Pause playback" : "Play playback"}
          >
            {isPlaying ? <Pause size={18} /> : <Play size={18} />}
          </button>
          <div className="period-slider">
            <strong>{period.label}</strong>
            <input
              aria-label="Reporting period"
              max={periods.length - 1}
              min={0}
              onChange={(event) => onPeriodChange(Number(event.currentTarget.value))}
              step={1}
              type="range"
              value={activePeriodIndex}
            />
          </div>
        </div>
      </div>

      <MetricStack period={period} />

      <div className="control-group compact">
        <p className="control-label">Monthly trend</p>
        <div className="spark-grid">
          <Sparkline label="Exit flow" values={periods.map((item) => item.totalBasinExitFlow)} activeIndex={activePeriodIndex} />
          <Sparkline label="Edge loss" values={periods.map((item) => item.totalEdgeLoss)} activeIndex={activePeriodIndex} />
          <Sparkline
            label="Energy"
            values={periods.map((item) => sumNodes(item.nodeResults, (node) => node.hydropower?.energyGenerated ?? 0))}
            activeIndex={activePeriodIndex}
          />
        </div>
      </div>
    </aside>
  );
}

function MetricStack({ period }: { period: PeriodResult }) {
  const drinking = sumNodes(period.nodeResults, (node) => node.drinkingWater?.actualDelivery ?? 0);
  const irrigation = sumNodes(period.nodeResults, (node) => node.irrigation?.water.actualDelivery ?? 0);
  const food = sumNodes(period.nodeResults, (node) => node.irrigation?.foodProduced ?? 0);
  const energy = sumNodes(period.nodeResults, (node) => node.hydropower?.energyGenerated ?? 0);

  return (
    <div className="metric-stack">
      <Metric label="Exit flow" value={format(period.totalBasinExitFlow)} accent="blue" />
      <Metric label="Edge loss" value={format(period.totalEdgeLoss)} accent="red" />
      <Metric label="Food" value={format(food)} accent="green" />
      <Metric label="Energy" value={format(energy)} accent="yellow" />
      <Metric label="Drinking" value={format(drinking)} accent="cyan" />
      <Metric label="Irrigation" value={format(irrigation)} accent="violet" />
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className={`metric ${accent}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Sparkline({ label, values, activeIndex }: { label: string; values: number[]; activeIndex: number }) {
  const max = Math.max(...values);

  return (
    <div className="sparkline">
      <span>{label}</span>
      <div className="bar-row">
        {values.map((value, index) => (
          <i
            className={index === activeIndex ? "active" : ""}
            key={`${label}-${index}`}
            style={{ height: `${Math.max(18, (value / max) * 58)}px` }}
          />
        ))}
      </div>
    </div>
  );
}
