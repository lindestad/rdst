import { BatteryCharging, Droplets, Sprout, TrendingUp, Zap } from "lucide-react";
import type { BenchmarkPolicy, OptimizerScenario } from "../types";

function formatCompact(value: number, unit = "") {
  const absolute = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const suffix = unit ? ` ${unit}` : "";

  if (absolute >= 1_000_000_000) return `${sign}${(absolute / 1_000_000_000).toFixed(2)}B${suffix}`;
  if (absolute >= 1_000_000) return `${sign}${(absolute / 1_000_000).toFixed(1)}M${suffix}`;
  if (absolute >= 1_000) return `${sign}${(absolute / 1_000).toFixed(1)}K${suffix}`;
  return `${sign}${absolute.toFixed(0)}${suffix}`;
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function signedCompact(value: number) {
  return value >= 0 ? `+${formatCompact(value)}` : `-${formatCompact(Math.abs(value))}`;
}

function valueWidth(policy: BenchmarkPolicy, maxValue: number) {
  return `${Math.max(8, (policy.policyValue / maxValue) * 100)}%`;
}

export function BenchmarkComparisonPanel({ scenario }: { scenario: OptimizerScenario }) {
  const sortedPolicies = [...scenario.policies].sort((a, b) => b.policyValue - a.policyValue);
  const optimized = scenario.policies.find((policy) => policy.id === "optimized") ?? sortedPolicies[0];
  const naivePolicies = scenario.policies.filter((policy) => policy.id !== optimized.id);
  const bestNaive = naivePolicies.reduce(
    (best, policy) => (policy.policyValue > best.policyValue ? policy : best),
    naivePolicies[0],
  );
  const maxValue = Math.max(...scenario.policies.map((policy) => policy.policyValue), 1);
  const optimizerGain = optimized.policyValue - bestNaive.policyValue;

  const metricCards = [
    {
      label: "Optimizer gain",
      value: formatCompact(optimizerGain),
      detail: `vs ${bestNaive.label}`,
      Icon: TrendingUp,
      tone: "green",
    },
    {
      label: "Retained storage",
      value: formatCompact(optimized.terminalStorageDelta, "m3"),
      detail: "vs full production",
      Icon: Droplets,
      tone: "blue",
    },
    {
      label: "Energy value",
      value: formatCompact(optimized.energyValue),
      detail: `${formatCompact(optimized.generatedElectricityKwh, "kWh")} generated`,
      Icon: Zap,
      tone: "yellow",
    },
    {
      label: "Demand reliability",
      value: `${percent(optimized.foodReliability)} / ${percent(optimized.drinkReliability)}`,
      detail: "food / drinking water",
      Icon: Sprout,
      tone: "cyan",
    },
  ];

  return (
    <section className="benchmark-panel">
      <div className="benchmark-heading">
        <div>
          <p className="app-kicker">Benchmark comparison</p>
          <h2>Optimized actions outperform naive reservoir rules</h2>
        </div>
        <div className="benchmark-badge">
          <BatteryCharging size={18} />
          <span>{formatCompact(optimized.policyValue)} payoff</span>
        </div>
      </div>

      <div className="benchmark-metrics">
        {metricCards.map(({ label, value, detail, Icon, tone }) => (
          <article className={`metric scenario-metric ${tone}`} key={label}>
            <Icon size={19} />
            <span>{label}</span>
            <strong>{value}</strong>
            <em>{detail}</em>
          </article>
        ))}
      </div>

      <div className="benchmark-chart" aria-label="Policy payoff comparison">
        {sortedPolicies.map((policy, index) => {
          const isOptimized = policy.id === optimized.id;
          const delta = policy.policyValue - bestNaive.policyValue;
          return (
            <article className={isOptimized ? "benchmark-row optimized" : "benchmark-row"} key={policy.id}>
              <div className="benchmark-rank">{index + 1}</div>
              <div className="benchmark-policy-copy">
                <strong>{policy.label}</strong>
                <span>{policy.description}</span>
              </div>
              <div className="benchmark-bar-track">
                <div className="benchmark-bar" style={{ width: valueWidth(policy, maxValue) }} />
              </div>
              <div className="benchmark-values">
                <strong>{formatCompact(policy.policyValue)}</strong>
                <span>{isOptimized ? signedCompact(delta) : formatCompact(policy.energyValue)}</span>
              </div>
            </article>
          );
        })}
      </div>

      <div className="benchmark-footnote">
        <strong>Payoff model</strong>
        <span>{scenario.valueFormula}</span>
      </div>
    </section>
  );
}
