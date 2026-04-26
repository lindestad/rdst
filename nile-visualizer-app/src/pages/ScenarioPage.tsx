import { Activity, BarChart3, GitCompareArrows } from "lucide-react";
import { useMemo, useState } from "react";
import { BenchmarkComparisonPanel } from "../components/BenchmarkComparisonPanel";
import { optimizerScenarios } from "../data/optimizerScenarios";

export function ScenarioPage({ onOpenVisualization }: { onOpenVisualization: () => void }) {
  const [activeScenarioId, setActiveScenarioId] = useState(optimizerScenarios[0].id);
  const scenario = useMemo(
    () => optimizerScenarios.find((item) => item.id === activeScenarioId) ?? optimizerScenarios[0],
    [activeScenarioId],
  );

  return (
    <section className="content-page scenario-page">
      <div className="content-hero compact-hero scenario-hero">
        <div>
          <p className="app-kicker">Scenario lab</p>
          <h2>Optimized water decisions against simple benchmark policies</h2>
          <p>
            Run the same Nile stress case through the Rust simulator, compare
            optimized actions against naive reservoir rules, and show the payoff
            in energy, storage, and unmet demand.
          </p>
        </div>
        <button className="file-button" onClick={onOpenVisualization} type="button">
          <BarChart3 size={18} />
          <span>Open basin view</span>
        </button>
      </div>

      <section className="scenario-layout">
        <aside className="scenario-list" aria-label="Available scenarios">
          <div>
            <p className="app-kicker">Available scenario</p>
            <h3>Benchmark runs</h3>
          </div>
          {optimizerScenarios.map((item) => (
            <button
              className={item.id === scenario.id ? "scenario-option active" : "scenario-option"}
              key={item.id}
              onClick={() => setActiveScenarioId(item.id)}
              type="button"
            >
              <GitCompareArrows size={17} />
              <span>
                <strong>{item.name}</strong>
                <small>{item.period}</small>
              </span>
            </button>
          ))}
          <div className="scenario-note">
            <Activity size={17} />
            <span>Scenario data is exported from NRSM benchmark summaries so the frontend stays independent of generated run folders.</span>
          </div>
        </aside>

        <div className="scenario-main">
          <section className="scenario-summary-band">
            <div>
              <p className="app-kicker">{scenario.simulator}</p>
              <h2>{scenario.name}</h2>
            </div>
            <p>{scenario.summary}</p>
          </section>
          <BenchmarkComparisonPanel scenario={scenario} />
        </div>
      </section>
    </section>
  );
}
