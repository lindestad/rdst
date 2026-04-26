import { ArrowUpRight } from "lucide-react";

const businessCards = [
  {
    label: "Who pays",
    value: "Basin stakeholders",
    text:
      "River basin bodies, ministries, hydropower operators, water utilities, development banks, and aid programs that need defensible water-allocation decisions.",
  },
  {
    label: "What they buy",
    value: "Decision intelligence",
    text:
      "A basin study, shared simulator, scenario library, and optimization package that turns contested assumptions into a transparent negotiation baseline.",
  },
  {
    label: "How value appears",
    value: "Cooperation surplus",
    text:
      "Coordinated reservoir operations can raise total food, power, reliability, and drought resilience compared with each actor optimizing locally.",
  },
];

const revenueItems = [
  "Pilot basin studies: $250k-$750k for data assembly, calibration, and scenario design.",
  "Full negotiation packages: $2M-$8M for a shared platform, stakeholder workshops, and operating-policy optimization.",
  "Verified-surplus pricing: 1-3% of measured annual value created through better coordination.",
];

const differentiators = [
  "Open Copernicus and ERA5 data lowers deployment friction and keeps the fact base neutral.",
  "Fast Rust simulation makes optimization practical instead of a one-off consultant report.",
  "Transparent assumptions give negotiators a shared model rather than competing national spreadsheets.",
];

export function BusinessPage({ onOpenVisualization }: { onOpenVisualization: () => void }) {
  return (
    <section className="business-page">
      <div className="business-hero">
        <div>
          <p className="app-kicker">Business case</p>
          <h2>Turning better water coordination into measurable value.</h2>
          <p>
            FairWater helps stakeholders along shared rivers find the basin-wide
            optimum, quantify the surplus, and create a trusted basis for sharing
            the gains.
          </p>
        </div>
        <button type="button" className="fw-btn fw-btn-green" onClick={onOpenVisualization}>
          Open simulator
          <ArrowUpRight size={13} strokeWidth={2} aria-hidden="true" />
        </button>
      </div>

      <div className="business-grid">
        {businessCards.map((card) => (
          <article className="business-card" key={card.label}>
            <span>{card.label}</span>
            <h3>{card.value}</h3>
            <p>{card.text}</p>
          </article>
        ))}
      </div>

      <div className="business-columns">
        <section className="business-panel">
          <p className="app-kicker">Revenue model</p>
          <h3>Consulting first, platform second.</h3>
          <ul>
            {revenueItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section className="business-panel dark">
          <p className="app-kicker">Why FairWater</p>
          <h3>Neutral, fast, and transparent.</h3>
          <ul>
            {differentiators.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <section className="business-opportunity">
        <p className="app-kicker">Opportunity</p>
        <h3>Nile first. Any basin next.</h3>
        <p>
          The World Bank finances more than $26B in water infrastructure annually,
          while climate volatility is making existing allocation agreements harder
          to defend. Because FairWater relies on open satellite and climate data,
          the same approach can move from the Nile to the Mekong, Colorado, Indus,
          or any other basin where coordination is worth real money.
        </p>
      </section>
    </section>
  );
}
