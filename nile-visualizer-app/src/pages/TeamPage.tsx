import { MapPinned } from "lucide-react";

const teamMembers = [
  {
    tag: "01",
    name: "Member 1",
    role: "Project lead / pitch",
    focus: "Fill in name, role, affiliation, and contribution.",
  },
  {
    tag: "02",
    name: "Member 2",
    role: "Simulation lead",
    focus: "Fill in name, role, affiliation, and contribution.",
  },
  {
    tag: "03",
    name: "Member 3",
    role: "Data and Earth observation",
    focus: "Fill in name, role, affiliation, and contribution.",
  },
  {
    tag: "04",
    name: "Member 4",
    role: "Visualization and UX",
    focus: "Fill in name, role, affiliation, and contribution.",
  },
  {
    tag: "05",
    name: "Member 5",
    role: "Validation / domain insight",
    focus: "Fill in name, role, affiliation, and contribution.",
  },
];

export function TeamPage({ onOpenVisualization }: { onOpenVisualization: () => void }) {
  return (
    <section className="content-page team-page">
      <div className="content-hero compact-hero">
        <div>
          <p className="app-kicker">Team</p>
          <h2>Fairwater team</h2>
          <p>
            Five contributors are building the simulator, data pathway,
            visualization, validation, and pitch. Replace these cards with names,
            roles, affiliations, and contact links when ready.
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
