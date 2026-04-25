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
    body: "Water allocation decisions are often discussed through separate spreadsheets, maps, and sector models. That makes tradeoffs hard to see and harder to explain.",
    Icon: Globe2,
  },
  {
    title: "The solution",
    body: "Fairwater turns simulator runs into a shared visual workspace for river flow, reservoir releases, agriculture, municipal demand, and energy output.",
    Icon: Target,
  },
  {
    title: "The evidence layer",
    body: "A Rust simulation core produces reproducible outputs, while the web interface translates those outputs into plots, basin state, and sector indicators.",
    Icon: Satellite,
  },
  {
    title: "The outcome",
    body: "Teams can compare scenarios, identify stress points, and communicate the consequences of policy choices without hiding the underlying model assumptions.",
    Icon: ShieldCheck,
  },
];

export function PitchPage({ onOpenVisualization }: { onOpenVisualization: () => void }) {
  return (
    <section className="content-page pitch-page">
      <div className="content-hero">
        <div>
          <p className="app-kicker">Fairwater pitch</p>
          <h2>Transparent scenario planning for shared river basins</h2>
          <p>
            Fairwater helps decision-makers and technical teams explore how
            reservoir operations, drought stress, irrigation demand, and
            municipal needs affect downstream flow, food production, and energy.
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
          <p className="app-kicker">Pitch</p>
          <h2>From simulator output to shared evidence</h2>
        </div>
        <p>
          The current prototype converts NRSM outputs into a browser-based basin
          view. Line widths show routed water, panels surface sector outcomes,
          and plots summarize basin balance. The product direction is a simple
          web workspace where users can upload or select scenarios, inspect
          tradeoffs, and export evidence for discussion.
        </p>
      </section>

      <section className="pitch-outline">
        <div>
          <p className="app-kicker">Pitch skeleton</p>
          <h2>Storyline to complete</h2>
        </div>
        <dl>
          <div>
            <dt>Problem</dt>
            <dd>Fragmented water planning makes basin tradeoffs difficult to compare and communicate.</dd>
          </div>
          <div>
            <dt>Users</dt>
            <dd>Water agencies, energy planners, agriculture analysts, basin researchers, and public-interest teams.</dd>
          </div>
          <div>
            <dt>Product</dt>
            <dd>A lightweight web interface for simulation runs, maps, sector KPIs, and scenario evidence.</dd>
          </div>
          <div>
            <dt>Data and model</dt>
            <dd>NRSM simulator outputs today, with a path toward hydrology, climate, and Earth observation inputs.</dd>
          </div>
          <div>
            <dt>Demo</dt>
            <dd>Load a saved run, scrub the period, select a stress point, and explain flow, food, and energy impacts.</dd>
          </div>
          <div>
            <dt>Next step</dt>
            <dd>Finalize scenario export, add comparison mode, improve basin geometry, and publish under the Fairwater domain.</dd>
          </div>
        </dl>
      </section>
    </section>
  );
}
