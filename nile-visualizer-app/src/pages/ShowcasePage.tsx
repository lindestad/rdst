import { useEffect, useRef } from "react";
import L from "leaflet";

type Props = {
  onOpenVisualization: () => void;
};

type NodeKind = "source" | "reservoir" | "wetland" | "confluence" | "irrigation" | "municipal" | "sink";
type NileNode = {
  lat: number;
  lng: number;
  id: string;
  label: string;
  kind: NodeKind;
};

const NODES: NileNode[] = [
  { lat: 0.4, lng: 33.2, id: "victoria", label: "L. Victoria", kind: "source" },
  { lat: 11.6, lng: 37.55, id: "tana", label: "L. Tana", kind: "source" },
  { lat: 11.22, lng: 35.09, id: "gerd", label: "GERD", kind: "reservoir" },
  { lat: 11.79, lng: 34.39, id: "roseires", label: "Roseires", kind: "reservoir" },
  { lat: 7.0, lng: 30.6, id: "sudd", label: "Sudd", kind: "wetland" },
  { lat: 15.6, lng: 32.53, id: "khartoum", label: "Khartoum", kind: "confluence" },
  { lat: 17.69, lng: 33.99, id: "atbara", label: "Atbara", kind: "source" },
  { lat: 18.46, lng: 31.84, id: "merowe", label: "Merowe", kind: "reservoir" },
  { lat: 14.4, lng: 33.1, id: "gezira", label: "Gezira irr.", kind: "irrigation" },
  { lat: 23.97, lng: 32.88, id: "aswan", label: "Aswan / Nasser", kind: "reservoir" },
  { lat: 28.5, lng: 30.9, id: "egypt_ag", label: "Egypt agr.", kind: "irrigation" },
  { lat: 30.06, lng: 31.24, id: "cairo", label: "Cairo", kind: "municipal" },
  { lat: 31.5, lng: 30.9, id: "mediterranean", label: "Mediterranean", kind: "sink" },
];

const EDGES: Array<[number, number]> = [
  [0, 4], [4, 5], [1, 2], [2, 3], [3, 5], [6, 5], [5, 7], [7, 9], [9, 10], [10, 11], [11, 12],
];

const MAIN_STEM = [0, 4, 5, 7, 9, 11, 12];
const BLUE_NILE = [1, 2, 3, 5];

const SVG_NS = "http://www.w3.org/2000/svg";

function makeEl<K extends keyof SVGElementTagNameMap>(
  tag: K,
  attrs: Record<string, string | number>,
): SVGElementTagNameMap[K] {
  const el = document.createElementNS(SVG_NS, tag) as SVGElementTagNameMap[K];
  Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, String(v)));
  return el;
}

export function ShowcasePage({ onOpenVisualization }: Props) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const annotationsRef = useRef<HTMLDivElement | null>(null);
  const sectionRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!mapRef.current) return;

    const map = L.map(mapRef.current, {
      center: [17.5, 33.2],
      zoom: 5,
      zoomControl: false,
      attributionControl: false,
      dragging: false,
      touchZoom: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      keyboard: false,
    });

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      crossOrigin: true,
    }).addTo(map);

    const px = (lat: number, lng: number) => map.latLngToContainerPoint([lat, lng]);
    const nodePos = (i: number) => px(NODES[i].lat, NODES[i].lng);

    function pathD(indices: number[]) {
      return indices
        .map((idx, i) => {
          const p = nodePos(idx);
          return `${i === 0 ? "M" : "L"}${p.x},${p.y}`;
        })
        .join(" ");
    }

    function drawNetwork() {
      const svg = svgRef.current;
      if (!svg) return;
      while (svg.firstChild) svg.removeChild(svg.firstChild);

      EDGES.forEach(([a, b]) => {
        const pa = nodePos(a);
        const pb = nodePos(b);
        svg.appendChild(
          makeEl("line", {
            x1: pa.x,
            y1: pa.y,
            x2: pb.x,
            y2: pb.y,
            stroke: "rgba(26,107,138,0.45)",
            "stroke-width": 1.5,
            "stroke-linecap": "round",
          }),
        );
      });

      svg.appendChild(
        makeEl("path", {
          d: pathD(MAIN_STEM),
          fill: "none",
          stroke: "rgba(47,164,111,0.22)",
          "stroke-width": 3,
          "stroke-linecap": "round",
        }),
      );

      svg.appendChild(
        makeEl("path", {
          d: pathD(BLUE_NILE),
          fill: "none",
          stroke: "rgba(47,164,111,0.16)",
          "stroke-width": 2,
          "stroke-linecap": "round",
        }),
      );

      const animMain = makeEl("path", {
        d: pathD(MAIN_STEM),
        fill: "none",
        stroke: "rgba(47,164,111,0.65)",
        "stroke-width": 2,
        "stroke-linecap": "round",
        "stroke-dasharray": "10 14",
      });
      animMain.style.animation = "fw-flow-dash 5s linear infinite";
      svg.appendChild(animMain);

      const animBlue = makeEl("path", {
        d: pathD(BLUE_NILE),
        fill: "none",
        stroke: "rgba(47,164,111,0.45)",
        "stroke-width": 1.5,
        "stroke-linecap": "round",
        "stroke-dasharray": "8 12",
      });
      animBlue.style.animation = "fw-flow-dash 4s linear infinite";
      animBlue.style.animationDelay = "-2s";
      svg.appendChild(animBlue);

      NODES.forEach(({ lat, lng, id, label, kind }) => {
        const p = px(lat, lng);
        const g = makeEl("g", {});

        if (kind === "reservoir") {
          const sz = id === "aswan" ? 9 : id === "gerd" ? 8 : 6;
          const accent = id === "aswan" || id === "gerd";
          g.appendChild(
            makeEl("rect", {
              x: p.x - sz,
              y: p.y - sz,
              width: sz * 2,
              height: sz * 2,
              rx: 1,
              fill: accent ? "rgba(47,164,111,0.3)" : "rgba(14,107,138,0.5)",
              stroke: accent ? "#2fa46f" : "rgba(47,164,111,0.5)",
              "stroke-width": accent ? 1.5 : 1,
            }),
          );
          [-sz * 0.35, sz * 0.1, sz * 0.55].forEach((dy) => {
            g.appendChild(
              makeEl("line", {
                x1: p.x - sz + 2,
                y1: p.y + dy,
                x2: p.x + sz - 2,
                y2: p.y + dy,
                stroke: accent ? "rgba(47,164,111,0.7)" : "rgba(47,164,111,0.4)",
                "stroke-width": 0.8,
              }),
            );
          });
        } else if (kind === "irrigation") {
          g.appendChild(
            makeEl("ellipse", {
              cx: p.x,
              cy: p.y,
              rx: 14,
              ry: 7,
              fill: "rgba(47,164,111,0.08)",
              stroke: "rgba(47,164,111,0.3)",
              "stroke-width": 1,
              "stroke-dasharray": "3 3",
            }),
          );
        } else if (kind === "sink") {
          g.appendChild(
            makeEl("rect", {
              x: p.x - 18,
              y: p.y - 6,
              width: 36,
              height: 12,
              rx: 1,
              fill: "rgba(11,79,108,0.2)",
              stroke: "rgba(11,79,108,0.4)",
              "stroke-width": 1,
            }),
          );
        } else {
          const r = kind === "confluence" ? 7 : kind === "municipal" ? 5 : 4;
          g.appendChild(
            makeEl("circle", {
              cx: p.x,
              cy: p.y,
              r: r + 4,
              fill: "rgba(11,79,108,0.12)",
            }),
          );
          g.appendChild(
            makeEl("circle", {
              cx: p.x,
              cy: p.y,
              r: r,
              fill:
                kind === "confluence"
                  ? "rgba(11,79,108,0.78)"
                  : kind === "municipal"
                    ? "rgba(11,79,108,0.6)"
                    : "rgba(11,79,108,0.5)",
              stroke: kind === "confluence" ? "#1a6b8a" : "rgba(26,107,138,0.6)",
              "stroke-width": 1,
            }),
          );
        }

        const labeled = ["gerd", "khartoum", "aswan", "cairo", "mediterranean", "tana", "victoria"];
        if (labeled.includes(id)) {
          const isLeft = id === "tana" || id === "victoria";
          const offset = isLeft ? [-10, 4] : [10, 4];
          const anchor = isLeft ? "end" : "start";
          const bold = id === "gerd" || id === "aswan";
          const txt = makeEl("text", {
            x: p.x + offset[0],
            y: p.y + offset[1],
            "text-anchor": anchor,
            "font-family": "DM Mono, monospace",
            "font-size": bold ? 10 : 9,
            "font-weight": bold ? 500 : 400,
            "letter-spacing": "0.04em",
            fill: bold ? "rgba(47,164,111,0.92)" : "rgba(255,255,255,0.55)",
          });
          txt.textContent = label;
          g.appendChild(txt);
        }

        svg.appendChild(g);
      });
    }

    function positionAnnotations() {
      const wrap = annotationsRef.current;
      if (!wrap) return;
      const items: Array<{ id: string; lat: number; lng: number; side: "left" | "right" }> = [
        { id: "fw-ann-gerd", lat: 11.22, lng: 35.09, side: "right" },
        { id: "fw-ann-aswan", lat: 23.97, lng: 32.88, side: "right" },
        { id: "fw-ann-khartoum", lat: 15.6, lng: 32.53, side: "left" },
      ];
      items.forEach(({ id, lat, lng, side }) => {
        const el = wrap.querySelector(`#${id}`) as HTMLElement | null;
        if (!el) return;
        const p = map.latLngToContainerPoint([lat, lng]);
        el.style.display = "block";
        el.style.left = `${p.x + (side === "right" ? 12 : -12)}px`;
        el.style.top = `${p.y - 26}px`;
        const card = el.querySelector(".fw-map-ann-card") as HTMLElement | null;
        if (card) {
          card.style.transform = side === "right" ? "translateX(0)" : "translateX(-100%)";
        }
      });
    }

    map.whenReady(() => {
      window.setTimeout(() => {
        drawNetwork();
        positionAnnotations();
      }, 220);
    });

    const onResize = () => {
      map.invalidateSize();
      window.setTimeout(() => {
        drawNetwork();
        positionAnnotations();
      }, 100);
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      map.remove();
    };
  }, []);

  useEffect(() => {
    if (!sectionRef.current) return;
    const reveals = sectionRef.current.querySelectorAll(".fw-reveal");
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -48px 0px" },
    );
    reveals.forEach((el) => observer.observe(el));

    const counters = sectionRef.current.querySelectorAll<HTMLElement>(".fw-counter");
    const counterObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const el = entry.target as HTMLElement;
            const target = parseFloat(el.dataset.target ?? "0");
            const duration = 1400;
            const start = performance.now();
            const step = (now: number) => {
              const elapsed = now - start;
              const progress = Math.min(elapsed / duration, 1);
              const eased = 1 - Math.pow(1 - progress, 3);
              el.textContent = String(Math.round(eased * target));
              if (progress < 1) requestAnimationFrame(step);
            };
            requestAnimationFrame(step);
            counterObserver.unobserve(el);
          }
        });
      },
      { threshold: 0.4 },
    );
    counters.forEach((el) => counterObserver.observe(el));

    return () => {
      observer.disconnect();
      counterObserver.disconnect();
    };
  }, []);

  return (
    <div className="fw" ref={sectionRef}>
      <section className="fw-hero">
        <div className="fw-hero-map-wrap">
          <div className="fw-hero-map" ref={mapRef} />
          <div className="fw-hero-overlay" />
          <svg className="fw-river-svg" ref={svgRef} aria-label="Nile basin schematic" />
        </div>

        <div ref={annotationsRef}>
          <div id="fw-ann-gerd" className="fw-map-ann" style={{ display: "none" }}>
            <div className="fw-map-ann-card">
              <div className="fw-ann-title">GERD · Blue Nile</div>
              <div className="fw-ann-value">6.45 GW</div>
              <div className="fw-ann-sub">Largest dam in Africa</div>
            </div>
          </div>
          <div id="fw-ann-aswan" className="fw-map-ann" style={{ display: "none" }}>
            <div className="fw-map-ann-card">
              <div className="fw-ann-title">Aswan / Nasser</div>
              <div className="fw-ann-value">74k MCM</div>
              <div className="fw-ann-sub">Storage capacity</div>
            </div>
          </div>
          <div id="fw-ann-khartoum" className="fw-map-ann" style={{ display: "none" }}>
            <div className="fw-map-ann-card">
              <div className="fw-ann-title">Khartoum confluence</div>
              <div className="fw-ann-value">Blue + White</div>
              <div className="fw-ann-sub">Nile rivers meet</div>
            </div>
          </div>
        </div>

        <div className="fw-hero-editorial">
          <div className="fw-kicker">CASSINI · Space for Water · 2026</div>
          <h1 className="fw-h1">
            FairWater
            <em>
              Every drop
              <br />
              accounted for.
            </em>
          </h1>
          <button type="button" className="fw-cta-link" onClick={onOpenVisualization}>
            Open simulator
          </button>
        </div>

        <div className="fw-hero-strip">
          <div className="fw-strip-item">
            <span className="fw-strip-val">11</span>
            <span className="fw-strip-label">riparian nations</span>
          </div>
          <div className="fw-strip-item">
            <span className="fw-strip-val">500M+</span>
            <span className="fw-strip-label">people dependent</span>
          </div>
          <div className="fw-strip-item">
            <span className="fw-strip-val">240</span>
            <span className="fw-strip-label">monthly steps</span>
          </div>
          <div className="fw-strip-item">
            <span className="fw-strip-val">~10 ms</span>
            <span className="fw-strip-label">per simulation run</span>
          </div>
          <div className="fw-strip-item">
            <span className="fw-strip-val">ERA5 · Sentinel-2</span>
            <span className="fw-strip-label">space data</span>
          </div>
        </div>
      </section>

      <section className="fw-problem">
        <div className="section-header fw-reveal">
          <span className="label">The Challenge</span>
          <h2>A basin under simultaneous pressure.</h2>
          <p>
            The Nile’s water-food-energy nexus is geopolitically complex. No single
            nation can optimise its outcomes in isolation — yet today, decisions
            are made with limited cross-border visibility into downstream
            consequences.
          </p>
        </div>

        <div className="fw-problem-grid">
          <div className="fw-problem-cell fw-reveal fw-reveal-1">
            <div className="fw-problem-num">
              74<sup>k</sup>
            </div>
            <div className="fw-problem-desc">
              MCM storage capacity at GERD — the largest dam in Africa, reshaping
              Blue Nile hydrology.
            </div>
          </div>
          <div className="fw-problem-cell fw-reveal fw-reveal-2">
            <div className="fw-problem-num">0.5</div>
            <div className="fw-problem-desc">
              Sudd wetland evaporative loss fraction — a natural variable amplified
              by upstream withdrawal policy.
            </div>
          </div>
          <div className="fw-problem-cell fw-problem-text fw-reveal fw-reveal-3">
            <h3>Policy decisions cascade across borders.</h3>
            <p>
              When Ethiopia adjusts GERD’s release schedule, the effects propagate
              through Sudan’s Roseires and Merowe dams, reduce Egyptian agricultural
              yields, and cut hydropower output at Aswan — all within the same
              seasonal window.
            </p>
            <p>
              Existing modelling tools either operate at sub-national scale, require
              months of configuration, or lack the satellite-validated ground truth
              needed for credible policy dialogue.
            </p>
            <div className="fw-nexus-pills">
              <span className="fw-nexus-pill">Water reliability</span>
              <span className="fw-nexus-pill">Food production</span>
              <span className="fw-nexus-pill">Hydropower output</span>
              <span className="fw-nexus-pill">Environmental flow</span>
            </div>
          </div>
        </div>
      </section>

      <section className="fw-how">
        <div className="section-header fw-reveal">
          <span className="label">Architecture</span>
          <h2>Four layers. One coherent view.</h2>
          <p>
            FairWater is built as a clean separation of concerns: each layer has a
            hard interface, enabling parallel development and independent
            validation. The optimizer sits on top of the simulator and searches
            for basin-wide policies that beat local, rule-based operation.
          </p>
        </div>

        <div className="fw-pipeline">
          <div className="fw-pipe-step fw-reveal fw-reveal-1">
            <div className="fw-pipe-num">L1</div>
            <div className="fw-pipe-icon">
              <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" /></svg>
            </div>
            <h3>Dataloader</h3>
            <p>
              ERA5 climate reanalysis (precipitation, temperature, PET, runoff) and
              Copernicus Sentinel-2 NDVI are assembled into a canonical node-graph
              schema with per-node monthly forcings from 2005–2024.
            </p>
            <div className="fw-tech-tags">
              <span className="fw-tech-tag">ERA5</span>
              <span className="fw-tech-tag">Sentinel-2</span>
              <span className="fw-tech-tag">CGLS NDVI</span>
              <span className="fw-tech-tag">Python CLI</span>
            </div>
            <div className="fw-pipe-arrow">
              <svg viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
            </div>
          </div>
          <div className="fw-pipe-step fw-reveal fw-reveal-2">
            <div className="fw-pipe-num">L2</div>
            <div className="fw-pipe-icon">
              <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
            </div>
            <h3>Simulation Engine</h3>
            <p>
              A directed acyclic river graph runs in monthly steps with Muskingum
              reach routing, Penman reservoir evaporation, and demand nodes for
              municipal and irrigation offtake. One full 240-step run completes in
              ~10 ms.
            </p>
            <div className="fw-tech-tags">
              <span className="fw-tech-tag">Rust</span>
              <span className="fw-tech-tag">NRSM Core</span>
              <span className="fw-tech-tag">YAML Contracts</span>
            </div>
            <div className="fw-pipe-arrow">
              <svg viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
            </div>
          </div>
          <div className="fw-pipe-step fw-reveal fw-reveal-3">
            <div className="fw-pipe-num">L3</div>
            <div className="fw-pipe-icon">
              <svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" /><line x1="8" y1="21" x2="16" y2="21" /><line x1="12" y1="17" x2="12" y2="21" /></svg>
            </div>
            <h3>Scenario Runner + Optimizer</h3>
            <p>
              YAML-defined scenarios encode policy choices — reservoir release
              schedules, irrigation area multipliers, environmental-flow
              constraints, and scoring weights. The optimizer then runs fast
              policy searches against the Rust core to find higher-value water
              allocations across energy, food, storage, and reliability.
            </p>
            <div className="fw-tech-tags">
              <span className="fw-tech-tag">FastAPI</span>
              <span className="fw-tech-tag">CMA-ES</span>
              <span className="fw-tech-tag">JSON Store</span>
              <span className="fw-tech-tag">NRSM CLI</span>
            </div>
            <div className="fw-pipe-arrow">
              <svg viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>
            </div>
          </div>
          <div className="fw-pipe-step fw-reveal fw-reveal-4">
            <div className="fw-pipe-num">L4</div>
            <div className="fw-pipe-icon">
              <svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></svg>
            </div>
            <h3>Decision Dashboard</h3>
            <p>
              A map-first React interface places each node at its geographic
              position along the Nile. Edge thickness encodes simulated flow
              magnitude. A month scrubber animates the full 20-year run. Scenarios
              are saved and compared side by side.
            </p>
            <div className="fw-tech-tags">
              <span className="fw-tech-tag">React + Vite</span>
              <span className="fw-tech-tag">TypeScript</span>
              <span className="fw-tech-tag">Pure SVG</span>
            </div>
          </div>
        </div>
      </section>

      <section className="fw-kpis">
        <div className="section-header fw-reveal">
          <span className="label">Measured Outcomes</span>
          <h2>Three KPIs. Real units.</h2>
          <p>
            FairWater reports outcomes in quantities that matter to policy-makers
            — not dimensionless indices or percentage changes on arbitrary
            baselines.
          </p>
        </div>

        <div className="fw-kpi-grid">
          <article className="fw-kpi-card fw-reveal fw-reveal-1">
            <div className="fw-kpi-bar" />
            <div className="fw-kpi-icon">
              <svg viewBox="0 0 24 24"><path d="M12 2c0 0-8 6-8 12a8 8 0 1 0 16 0c0-6-8-12-8-12z" /></svg>
            </div>
            <div className="fw-kpi-value">
              <span className="fw-counter" data-target="94">0</span>
              <span className="fw-kpi-unit">%</span>
            </div>
            <div className="fw-kpi-label">Drinking water reliability</div>
            <p className="fw-kpi-desc">
              Population-weighted fraction of municipal demand met across Cairo and
              Khartoum. Reported in m³/person/day and aggregate served fraction per
              period.
            </p>
          </article>
          <article className="fw-kpi-card fw-reveal fw-reveal-2">
            <div className="fw-kpi-bar" />
            <div className="fw-kpi-icon">
              <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 0 1 10 10H2A10 10 0 0 1 12 2z" /><rect x="7" y="12" width="10" height="8" rx="1" /><line x1="9" y1="16" x2="15" y2="16" /></svg>
            </div>
            <div className="fw-kpi-value">
              <span className="fw-counter" data-target="12">0</span>
              <span className="fw-kpi-unit">.4 Mt</span>
            </div>
            <div className="fw-kpi-label">Food production</div>
            <p className="fw-kpi-desc">
              Sum of irrigation-zone deliveries multiplied by FAO AquaStat
              crop-water-productivity coefficients for Gezira (cotton/wheat) and
              Egypt Delta (rice/maize/wheat). Reported as tonnes wheat-equivalent
              per year.
            </p>
          </article>
          <article className="fw-kpi-card fw-reveal fw-reveal-3">
            <div className="fw-kpi-bar" />
            <div className="fw-kpi-icon">
              <svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></svg>
            </div>
            <div className="fw-kpi-value">
              <span className="fw-counter" data-target="38">0</span>
              <span className="fw-kpi-unit"> TWh</span>
            </div>
            <div className="fw-kpi-label">Hydropower output</div>
            <p className="fw-kpi-desc">
              Aggregated across GERD (6.45 GW nameplate), Roseires, Merowe, and
              Aswan dams. Computed from release volumes, constant head estimates,
              and published turbine efficiencies. Reported as GWh/month and
              TWh/year.
            </p>
          </article>
        </div>

        <div className="fw-scenario-banner fw-reveal">
          <div>
            <h3>Scenario: GERD 90-day upstream holdback</h3>
            <p>Modelled consequence of a 3-month reduced release strategy on downstream basin metrics.</p>
          </div>
          <div className="fw-scenario-items">
            <div className="fw-scenario-item">
              <div className="fw-scenario-val">−18%</div>
              <div className="fw-scenario-label">Aswan inflow</div>
            </div>
            <div className="fw-scenario-item">
              <div className="fw-scenario-val">−2.3 Mt</div>
              <div className="fw-scenario-label">Food (Egypt)</div>
            </div>
            <div className="fw-scenario-item">
              <div className="fw-scenario-val">+6 TWh</div>
              <div className="fw-scenario-label">GERD output</div>
            </div>
            <div className="fw-scenario-item">
              <div className="fw-scenario-val">−4 TWh</div>
              <div className="fw-scenario-label">Aswan output</div>
            </div>
          </div>
        </div>
      </section>

      <section className="fw-business">
        <div className="section-header fw-reveal">
          <span className="label">Business Model</span>
          <h2>Finding the cooperation surplus.</h2>
          <p>
            Shared rivers are coordination markets. Every stakeholder can optimize
            locally and still leave the basin poorer; FairWater quantifies the
            basin-wide optimum and the surplus available to split.
          </p>
        </div>

        <div className="fw-business-grid">
          <article className="fw-business-card fw-reveal fw-reveal-1">
            <span className="fw-business-num">$250k–$750k</span>
            <h3>Pilot basin study</h3>
            <p>
              A first engagement with a ministry, hydropower operator, or river
              basin body: assemble data, calibrate scenarios, and quantify the
              gains from coordinated operation.
            </p>
          </article>
          <article className="fw-business-card fw-reveal fw-reveal-2">
            <span className="fw-business-num">$2M–$8M</span>
            <h3>Full negotiation package</h3>
            <p>
              Consulting plus platform deployment for a basin-scale planning
              process: transparent assumptions, shared scenarios, and auditable
              trade-off numbers all parties can negotiate from.
            </p>
          </article>
          <article className="fw-business-card fw-reveal fw-reveal-3">
            <span className="fw-business-num">1–3%</span>
            <h3>Share of verified surplus</h3>
            <p>
              If better coordination creates hundreds of millions in extra food,
              power, avoided shortage, or aid efficiency, FairWater can price as a
              small fraction of the measured annual gain.
            </p>
          </article>
        </div>

        <div className="fw-value-strip fw-reveal">
          <div>
            <strong>Nile-scale payoff</strong>
            <span>
              A 1% improvement in agricultural and hydropower outcomes can be
              worth hundreds of millions per year.
            </span>
          </div>
          <div>
            <strong>Customers</strong>
            <span>Dam operators, ministries, basin commissions, EU/UN aid programs, and development banks.</span>
          </div>
          <div>
            <strong>Core claim</strong>
            <span>Cooperation is not altruism; it can be more profitable than conflict.</span>
          </div>
        </div>
      </section>

      <section className="fw-caps">
        <div className="section-header fw-reveal">
          <span className="label">Platform Capabilities</span>
          <h2>Built for credible dialogue.</h2>
          <p>
            FairWater’s architecture supports the full workflow from data assembly
            through scenario exploration to decision comparison — within a single,
            auditable pipeline.
          </p>
        </div>

        <div className="fw-cap-grid">
          <article className="fw-cap-item fw-reveal fw-reveal-1">
            <div className="fw-cap-num">01</div>
            <h3>Policy scenario modelling</h3>
            <p>
              YAML-defined scenarios encode reservoir release schedules, irrigation
              area scaling, and minimum environmental-flow constraints. Any
              combination can be executed in milliseconds and saved for comparison.
              Packaged baseline, historical, future, and extreme-stress runs ship
              with the tool.
            </p>
          </article>
          <article className="fw-cap-item fw-reveal fw-reveal-2">
            <div className="fw-cap-num">02</div>
            <h3>Satellite-validated ground truth</h3>
            <p>
              Sentinel-2 NDVI observations over the Gezira and Egyptian Delta
              irrigation zones are pre-rendered as monthly raster overlays. The
              scrubber animates observed crop condition alongside simulated
              delivery — closing the space-data loop for CASSINI’s validation
              track.
            </p>
          </article>
          <article className="fw-cap-item fw-reveal fw-reveal-3">
            <div className="fw-cap-num">03</div>
            <h3>Side-by-side scenario comparison</h3>
            <p>
              Compare mode splits the basin map into two synchronized views driven
              by separate scenarios. The right rail shows KPI deltas as signed
              quantities — food −2.3 Mt, energy +6 TWh — making trade-offs
              immediately legible without interpretation.
            </p>
          </article>
          <article className="fw-cap-item fw-reveal fw-reveal-4">
            <div className="fw-cap-num">04</div>
            <h3>Auditable, open architecture</h3>
            <p>
              The Rust simulation core is open-source, schema-validated via YAML
              contracts, and produces deterministic JSON output. Simulation
              parameters, forcings, and KPI definitions are fully transparent. No
              black boxes between the data and the number on screen.
            </p>
          </article>
        </div>
      </section>

      <section className="fw-tech">
        <div className="section-header fw-reveal">
          <span className="label">Technology</span>
          <h2>Purpose-built at every layer.</h2>
          <p>
            Each component was chosen for correctness and auditability — not
            convenience. The simulation core is intentionally separate from the
            data layer, the optimizer, and the dashboard.
          </p>
        </div>
        <table className="fw-tech-table fw-reveal">
          <thead>
            <tr>
              <th>Layer</th>
              <th>Component</th>
              <th>Stack</th>
              <th>Role</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="fw-td-layer">L1 · Data</td>
              <td className="fw-td-name">NRSM Dataloader</td>
              <td className="fw-td-stack">Python · cdsapi · stackstac · Parquet</td>
              <td className="fw-td-role">
                Fetches ERA5 monthly forcings and Sentinel-2 NDVI. Assembles
                canonical node configs and timeseries files for simulator
                consumption.
              </td>
            </tr>
            <tr>
              <td className="fw-td-layer">L2 · Engine</td>
              <td className="fw-td-name">NRSM Sim Core</td>
              <td className="fw-td-stack">Rust · Cargo workspace</td>
              <td className="fw-td-role">
                Topological DAG sweep, Muskingum reach routing, Penman evaporation,
                demand-node mass balance. Schema-validated YAML scenarios. ~10 ms
                per 240-step run.
              </td>
            </tr>
            <tr>
              <td className="fw-td-layer">L2 · CLI</td>
              <td className="fw-td-name">NRSM CLI</td>
              <td className="fw-td-stack">Rust · serde_json</td>
              <td className="fw-td-role">
                Runs any scenario YAML and emits structured JSON or per-node CSVs
                to a results directory. Entry point for CI and batch scenario
                generation.
              </td>
            </tr>
            <tr>
              <td className="fw-td-layer">L3 · Optimizer</td>
              <td className="fw-td-name">Policy Optimizer</td>
              <td className="fw-td-stack">Python · CMA-ES · NRSM bindings</td>
              <td className="fw-td-role">
                Searches time-varying reservoir actions against the fast Rust
                simulator. Scores each policy with a configurable objective over
                hydropower value, food-water delivery, drinking-water reliability,
                and terminal storage.
              </td>
            </tr>
            <tr>
              <td className="fw-td-layer">L3 · API</td>
              <td className="fw-td-name">Scenario API</td>
              <td className="fw-td-stack">FastAPI · Python · JSON store</td>
              <td className="fw-td-role">
                Stateless HTTP surface for node metadata, timeseries queries,
                synchronous scenario execution, save/load, and comparison diffs.
                Docker Compose deployable.
              </td>
            </tr>
            <tr>
              <td className="fw-td-layer">L4 · UI</td>
              <td className="fw-td-name">Visualizer</td>
              <td className="fw-td-stack">React · Vite · TypeScript</td>
              <td className="fw-td-role">
                Geography-based basin map, left-rail lenses, right-rail KPI charts,
                month scrubber, NDVI overlay, scenario selector. Hash-routed:
                showcase, simulator, team.
              </td>
            </tr>
            <tr>
              <td className="fw-td-layer">Obs · Space</td>
              <td className="fw-td-name">Space data layer</td>
              <td className="fw-td-stack">Copernicus · Sentinel-2 L2A · CGLS · ERA5</td>
              <td className="fw-td-role">
                Satellite-observed NDVI for irrigation zone validation. ERA5
                land-surface reanalysis for 2005–2024 monthly forcings at 15–20
                basin nodes.
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="fw-cassini">
        <div className="fw-cassini-inner fw-reveal">
          <div className="fw-cassini-left">
            <span className="label">Context</span>
            <h2>Built for CASSINI’s Space for Water track.</h2>
            <p>
              FairWater was developed as a one-weekend MVP for the CASSINI
              Hackathon 2026, specifically targeting the Space for Water
              challenge: using Copernicus and Sentinel Earth observation data to
              address water scarcity and security.
            </p>
            <p>
              The prototype demonstrates a full pipeline from satellite
              observation through physical simulation to policy-ready decision
              support — in a form that scales from hackathon demo to operational
              tool.
            </p>
            <button
              type="button"
              className="fw-btn fw-btn-green"
              onClick={onOpenVisualization}
              style={{ marginTop: 12 }}
            >
              Open the live simulator
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 13, height: 13 }}>
                <line x1="7" y1="17" x2="17" y2="7" />
                <polyline points="7 7 17 7 17 17" />
              </svg>
            </button>
          </div>
          <div className="fw-cassini-right">
            <div className="fw-cassini-fact">
              <div className="fw-cassini-fact-icon">
                <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" /></svg>
              </div>
              <div className="fw-cassini-fact-text">
                <strong>Space data at the core</strong>
                <span>
                  Copernicus ERA5 and Sentinel-2 observations are not supplementary
                  — they are the primary forcing and validation data throughout
                  the pipeline.
                </span>
              </div>
            </div>
            <div className="fw-cassini-fact">
              <div className="fw-cassini-fact-icon">
                <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg>
              </div>
              <div className="fw-cassini-fact-text">
                <strong>Policy-ready output</strong>
                <span>
                  Outcomes are expressed in tonnes, GWh, and percentage of
                  population served — quantities that translate directly into
                  national planning contexts.
                </span>
              </div>
            </div>
            <div className="fw-cassini-fact">
              <div className="fw-cassini-fact-icon">
                <svg viewBox="0 0 24 24"><polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" /></svg>
              </div>
              <div className="fw-cassini-fact-text">
                <strong>Open and auditable</strong>
                <span>
                  The Rust simulation core, YAML scenario contracts, and data
                  pipeline are all open-source. Every number can be traced back to
                  its ERA5 or satellite source.
                </span>
              </div>
            </div>
            <div className="fw-cassini-fact">
              <div className="fw-cassini-fact-icon">
                <svg viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>
              </div>
              <div className="fw-cassini-fact-text">
                <strong>~10 ms per simulation run</strong>
                <span>
                  The Rust engine completes 240 monthly steps across 15–20 basin
                  nodes in approximately 10 ms, enabling interactive policy
                  exploration without server round-trips.
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="fw-cta">
        <h2>
          Explore the Nile
          <br />
          basin simulator.
        </h2>
        <p>
          Move a policy lever and watch the cascade from GERD to the Egyptian
          Delta — in real units, validated against satellite-observed crop NDVI.
        </p>
        <div className="fw-cta-actions">
          <button type="button" className="fw-btn fw-btn-white" onClick={onOpenVisualization}>
            Open FairWater simulator
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 13, height: 13 }}>
              <line x1="7" y1="17" x2="17" y2="7" />
              <polyline points="7 7 17 7 17 17" />
            </svg>
          </button>
          <a
            className="fw-btn fw-btn-outline"
            href="https://github.com/lindestad/rdst"
            target="_blank"
            rel="noreferrer"
          >
            View on GitHub
          </a>
        </div>
      </section>

      <footer className="fw-footer">
        <div className="fw-footer-left">
          <svg viewBox="0 0 110.07 40.42" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <g transform="translate(-19.29,-50.75)">
              <circle fill="#2fa46f" cx="28.74" cy="76.52" r="5" />
              <circle fill="#2fa46f" cx="21.34" cy="67.93" r="2.06" />
              <circle fill="#2fa46f" cx="44.80" cy="72.03" r="2.06" />
              <circle fill="#2fa46f" cx="36.28" cy="64.47" r="2.06" />
              <circle fill="#2fa46f" cx="27.85" cy="60.86" r="2.06" />
              <circle fill="#2fa46f" cx="27.54" cy="53.06" r="2.06" />
              <path stroke="#2fa46f" strokeWidth="1" fill="none" d="M28.74,76.52 21.34,67.93 27.85,60.86 27.54,53.06" />
              <path stroke="#2fa46f" strokeWidth="1" fill="none" d="m44.80,72.03 -8.52-7.57 -8.43-3.61" />
              <circle fill="#0b4f6c" cx="48.72" cy="71.78" r="2.06" />
              <circle fill="#0b4f6c" cx="40.21" cy="64.22" r="2.06" />
              <circle fill="#0b4f6c" cx="31.78" cy="60.61" r="2.06" />
              <circle fill="#0b4f6c" cx="31.47" cy="52.81" r="2.06" />
              <circle fill="#0b4f6c" cx="32.67" cy="76.27" r="5" />
              <circle fill="#0b4f6c" cx="25.27" cy="67.68" r="2.06" />
              <path stroke="#0b4f6c" strokeWidth="1" fill="none" d="M32.67,76.27 25.27,67.68 31.78,60.61 31.47,52.81" />
              <path stroke="#0b4f6c" strokeWidth="1" fill="none" d="m48.72,71.78 -8.52-7.57 -8.43-3.61" />
              <text fontFamily="DM Sans, sans-serif" fontWeight="700" fontSize="17.64" x="42.55" y="90.99">
                <tspan fill="#2fa46f">Fair</tspan>
                <tspan fill="#ffffff">Water</tspan>
              </text>
            </g>
          </svg>
          <span className="fw-footer-copy">CASSINI Hackathon 2026 · Space for Water</span>
        </div>
        <div className="fw-footer-links">
          <button type="button" onClick={onOpenVisualization}>
            Simulator
          </button>
          <a href="https://github.com/lindestad/rdst" target="_blank" rel="noreferrer">
            GitHub
          </a>
          <a href="#/team">Team</a>
        </div>
      </footer>
    </div>
  );
}
