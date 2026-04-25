import {
  BarChart3,
  Github,
  Globe2,
  Satellite,
  ShieldCheck,
  Target,
  type LucideIcon,
} from "lucide-react";

const pitchCards: Array<{ title: string; body: string; Icon: LucideIcon }> = [
  {
    title: "The problem",
    body: "Water policy in shared river basins is one of the hardest coordination problems in the world. Hold back water in Ethiopia for hydropower and Egypt's farms get less irrigation. Release early for agriculture and reservoirs run low when drought hits. Today these tradeoffs are navigated with spreadsheets, political pressure, and guesswork.",
    Icon: Globe2,
  },
  {
    title: "Our solution",
    body: "FairWater is a digital twin for river basin policy: a what-if sandbox that lets anyone see the downstream consequences of a water decision before it happens. Move a slider, run a scenario, and in seconds see the cascading impact on drinking-water reliability, food production, and hydropower output in real, comparable units.",
    Icon: Target,
  },
  {
    title: "What makes us different",
    body: "We rely exclusively on open satellite data. Our ground truth comes from the EU Copernicus programme: free, independent, and trusted by scientists worldwide. No proprietary feeds, no black-box algorithms, every number traceable back to its source. That neutrality is what lets opposing parties share the same fact base.",
    Icon: Satellite,
  },
  {
    title: "The opportunity",
    body: "The World Bank finances over $26B in water infrastructure annually and every project needs credible impact assessment. The Nile is our starting point; because we rely entirely on open data, the platform generalizes to any basin in the world, from the Mekong to the Colorado, without renegotiating data access with any government.",
    Icon: ShieldCheck,
  },
];

const dataSources: Array<{ term: string; description: string }> = [
  {
    term: "ERA5 reanalysis",
    description: "Twenty years of validated climate forcings from Copernicus, used for historical calibration and stress-test scenarios.",
  },
  {
    term: "Sentinel-2 imagery",
    description: "Optical satellite observations of real crop health and irrigation footprint across the basin.",
  },
  {
    term: "Physics-based river model",
    description: "A reproducible Rust simulation core calibrated against measured discharge data at gauging stations.",
  },
  {
    term: "Reservoir levels (live)",
    description: "Near real-time reservoir storage from satellite altimetry feeds. Source: TBD.",
  },
  {
    term: "Crop production (live)",
    description: "Current-season crop production estimates derived from satellite indices. Source: TBD.",
  },
  {
    term: "Runoff and inflow (live)",
    description: "Real-time runoff and tributary inflow signals feeding the basin model. Source: TBD.",
  },
];

export function PitchPage({ onOpenVisualization }: { onOpenVisualization: () => void }) {
  return (
    <section className="content-page pitch-page">
      <div className="content-hero">
        <div>
          <p className="app-kicker">FairWater</p>
          <h2>Fair and optimal water distribution across borders</h2>
          <p>
            The Nile feeds 500 million people across 11 countries. Every year,
            decisions about dam releases, irrigation allocations, and reservoir
            schedules are made with incomplete information, and the consequences
            ripple downstream for decades. Droughts worsen. Crops fail. Cities
            run dry. FairWater makes those consequences visible before the
            decision is made.
          </p>
          <div className="hero-actions">
            <button className="file-button" onClick={onOpenVisualization} type="button">
              <BarChart3 size={18} />
              <span>Open visualization</span>
            </button>
            <a className="text-link-button" href="https://github.com/lindestad/rdst" rel="noreferrer" target="_blank">
              <Github size={18} />
              <span>Repository</span>
            </a>
          </div>
        </div>
        <div className="pitch-visual" aria-label="Basin concept visual">
          <svg viewBox="0 0 520 320" role="img">
            <path className="land" d="M34 78 C112 28 206 44 276 76 C352 112 422 82 484 132 C538 176 498 258 410 278 C318 300 270 248 196 268 C114 290 38 236 26 162 C20 126 18 96 34 78 Z" />
            <path className="river-main" d="M64 246 C134 198 176 206 226 172 C280 134 314 142 366 106 C402 80 444 80 482 58" />
            <path className="river-branch" d="M74 80 C136 116 160 152 226 172" />
            <path className="river-branch" d="M162 282 C190 230 210 204 226 172" />
            <circle className="map-node source" cx="74" cy="80" r="13" />
            <circle className="map-node reservoir" cx="264" cy="146" r="18" />
            <circle className="map-node city" cx="366" cy="106" r="13" />
            <circle className="map-node farm" cx="196" cy="254" r="15" />
            <circle className="map-node delta" cx="482" cy="58" r="16" />
          </svg>
        </div>
      </div>

      <div className="pitch-grid">
        {pitchCards.map(({ title, body, Icon }) => (
          <article className="story-card" key={title}>
            <Icon size={22} />
            <h3>{title}</h3>
            <p>{body}</p>
          </article>
        ))}
      </div>

      <section className="wide-band">
        <div>
          <p className="app-kicker">Who it's for</p>
          <h2>Built for the people in the room when hard water decisions get made</h2>
        </div>
        <p>
          International organizations such as the UN, the World Bank, and
          regional river basin bodies working to prevent water conflicts and
          support cooperative agreements. Foreign aid and development programs
          that need rigorous, defensible impact assessments for water
          infrastructure investments. National governments and ministries
          managing shared watercourses and needing decision support they can
          stand behind in public. Hydropower companies and water utilities
          seeking to optimize operations while demonstrating respect for
          downstream obligations. If you work in any of these spaces, FairWater
          was built with you in mind.
        </p>
      </section>

      <section className="pitch-outline">
        <div>
          <p className="app-kicker">Open data foundation</p>
          <h2>Every number traceable to its source</h2>
        </div>
        <dl>
          {dataSources.map(({ term, description }) => (
            <div key={term}>
              <dt>{term}</dt>
              <dd>{description}</dd>
            </div>
          ))}
        </dl>
      </section>
    </section>
  );
}
