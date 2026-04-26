type Member = {
  tag: string;
  name: string;
  role: string;
  focus: string;
};

const members: Member[] = [
  {
    tag: "01",
    name: "Emilio Lombardo",
    role: "Mathematical modeling",
    focus:
      "Industrial mathematics student contributing to the mathematical modeling and numerical methods underpinning the simulation engine.",
  },
  {
    tag: "02",
    name: "Storm Selvig",
    role: "Backend and data infrastructure",
    focus:
      "Data engineering student responsible for backend infrastructure, data architecture, and the systems that make large-scale satellite data processable in real time.",
  },
  {
    tag: "03",
    name: "Daniel Lindestad",
    role: "Product and stakeholder lead",
    focus:
      "Business administration graduate specialized in analytical finance, now completing computer engineering with a focus on applied machine learning. Leads product development and stakeholder communication.",
  },
  {
    tag: "04",
    name: "Bernt Viggo Matheussen",
    role: "Hydrology lead",
    focus:
      "PhD in hydrological modeling. Brings deep expertise in river systems and water resource simulation, providing the scientific foundation that keeps the platform grounded in physical reality.",
  },
  {
    tag: "05",
    name: "Jonas Tjemsland",
    role: "Data and Earth observation",
    focus:
      "PhD in Theoretical Astroparticle Physics. Leads data pipeline development and the integration of satellite and climate datasets, applying rigorous quantitative methods to real-world water systems.",
  },
];

export function TeamPage({ onOpenVisualization }: { onOpenVisualization: () => void }) {
  return (
    <section className="fw-team">
      <div className="fw-team-hero">
        <div>
          <span className="label" style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            fontFamily: "DM Mono, monospace",
            fontSize: 10.5,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "var(--green)",
          }}>
            <span style={{ display: "inline-block", width: 18, height: 1, background: "var(--green)", opacity: 0.6 }} />
            Team
          </span>
          <h2>The people behind FairWater.</h2>
          <p>
            FairWater was built by a five-person team with backgrounds in
            hydrology, data engineering, mathematical modeling, economics, and
            applied machine learning. Together they cover the full path from
            satellite pixels to a working river-basin decision tool.
          </p>
        </div>
        <button type="button" className="fw-btn fw-btn-green" onClick={onOpenVisualization}>
          View basin run
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 13, height: 13 }}>
            <line x1="7" y1="17" x2="17" y2="7" />
            <polyline points="7 7 17 7 17 17" />
          </svg>
        </button>
      </div>

      <div className="fw-team-grid">
        {members.map((m) => (
          <article className="fw-team-card" key={m.name}>
            <div className="fw-team-tag">{m.tag}</div>
            <h3>{m.name}</h3>
            <span className="fw-team-role">{m.role}</span>
            <p>{m.focus}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
