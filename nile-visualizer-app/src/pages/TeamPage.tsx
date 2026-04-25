import { MapPinned } from "lucide-react";

const teamMembers = [
  {
    tag: "01",
    name: "Bernt Viggo Matheussen",
    role: "Hydrology lead",
    focus:
      "PhD in hydrological modeling. Provides the scientific foundation that keeps the platform grounded in physical reality, with deep expertise in river systems and water resource simulation.",
  },
  {
    tag: "02",
    name: "Jonas Tjemsland",
    role: "Data and Earth observation",
    focus:
      "PhD in Theoretical Astroparticle Physics. Leads data pipeline development and the integration of satellite and climate datasets, applying rigorous quantitative methods to real-world water systems.",
  },
  {
    tag: "03",
    name: "Daniel Lindestad",
    role: "Product and stakeholder lead",
    focus:
      "Master's in economics, currently completing a degree in data science. Bridges the technical and policy dimensions of the platform and leads product development and stakeholder communication.",
  },
  {
    tag: "04",
    name: "Storm Selvig",
    role: "Backend and data infrastructure",
    focus:
      "Data engineering student responsible for backend infrastructure, data architecture, and the systems that make large-scale satellite data processable in real time.",
  },
  {
    tag: "05",
    name: "Emilio Lombardo",
    role: "Mathematical modeling",
    focus:
      "Industrial mathematics student contributing to the mathematical modeling and numerical methods underpinning the simulation engine.",
  },
];

export function TeamPage({ onOpenVisualization }: { onOpenVisualization: () => void }) {
  return (
    <section className="content-page team-page">
      <div className="content-hero compact-hero">
        <div>
          <p className="app-kicker">Team</p>
          <h2>FairWater team</h2>
          <p>
            FairWater was built by a five-person team with backgrounds in
            hydrology, data engineering, mathematical modeling, and economics.
            Together they cover the full path from satellite pixels to policy
            evidence.
          </p>
        </div>
        <button className="file-button" onClick={onOpenVisualization} type="button">
          <MapPinned size={18} />
          <span>View basin run</span>
        </button>
      </div>

      <div className="team-grid">
        {teamMembers.map((member) => (
          <article className="team-card" key={member.name}>
            <div className="avatar-mark">{member.tag}</div>
            <div>
              <h3>{member.name}</h3>
              <strong>{member.role}</strong>
              <p>{member.focus}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
