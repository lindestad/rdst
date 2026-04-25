import { useEffect, useMemo, useState } from "react";

import {
  COPERNICUS_BASELINE_NOTE,
  COPERNICUS_MONTHLY,
  COPERNICUS_PRODUCTS,
  type CopernicusMonth,
} from "./copernicusData/copernicusBaseline";

type Params = {
  month: number;
  rainfallScale: number;
  droughtStress: number;
  gerdRelease: number;
  aswanRelease: number;
  irrigationScale: number;
  suddLoss: number;
};

type NodeId =
  | "victoria"
  | "sudd"
  | "tana"
  | "gerd"
  | "khartoum"
  | "atbara"
  | "merowe"
  | "aswan"
  | "egyptAg"
  | "cairo"
  | "delta";

type FlowSegment = {
  id: string;
  label: string;
  from: NodeId;
  to: NodeId;
  flow: number;
  branch: "white" | "blue" | "atbara" | "main";
};

type SimResult = {
  month: number;
  dataMonthLabel: string;
  segments: FlowSegment[];
  nodes: Record<NodeId, { label: string; x: number; y: number; flow: number }>;
  transfers: {
    suddLoss: number;
    geziraTake: number;
    egyptAgTake: number;
    cairoTake: number;
  };
  metrics: {
    deltaFlow: number;
    cairoServedPct: number;
    irrigationServedPct: number;
    energyGwh: number;
    gerdStorageDelta: number;
    aswanStorageDelta: number;
    runoffIndex: number;
    petMm: number;
    gerdAreaKm2: number;
    aswanAreaKm2: number;
  };
};

type BaselinePayload = {
  generatedAt?: string;
  period?: [number, number];
  source?: { note?: string };
  months: CopernicusMonth[];
};

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const NODE_POS: Record<NodeId, { label: string; x: number; y: number }> = {
  victoria: { label: "Lake Victoria", x: 180, y: 560 },
  sudd: { label: "Sudd", x: 260, y: 420 },
  tana: { label: "Lake Tana", x: 610, y: 405 },
  gerd: { label: "GERD", x: 530, y: 345 },
  khartoum: { label: "Khartoum", x: 380, y: 305 },
  atbara: { label: "Atbara", x: 570, y: 255 },
  merowe: { label: "Merowe", x: 365, y: 220 },
  aswan: { label: "Aswan", x: 350, y: 135 },
  egyptAg: { label: "Egypt farms", x: 315, y: 85 },
  cairo: { label: "Cairo", x: 375, y: 58 },
  delta: { label: "Delta", x: 415, y: 28 },
};

const LABEL_POS: Record<NodeId, { x: number; y: number; anchor?: "start" | "middle" | "end" }> = {
  victoria: { x: 18, y: -8 },
  sudd: { x: 16, y: 4 },
  tana: { x: -18, y: -18, anchor: "end" },
  gerd: { x: 18, y: -8 },
  khartoum: { x: -18, y: -12, anchor: "end" },
  atbara: { x: 16, y: -10 },
  merowe: { x: -18, y: -10, anchor: "end" },
  aswan: { x: -18, y: -10, anchor: "end" },
  egyptAg: { x: -20, y: 18, anchor: "end" },
  cairo: { x: 18, y: 12 },
  delta: { x: 14, y: -7 },
};

const CURVES: Record<string, { cx: number; cy: number }> = {
  "victoria-sudd": { cx: 215, cy: 490 },
  "sudd-khartoum": { cx: 295, cy: 355 },
  "tana-gerd": { cx: 565, cy: 385 },
  "gerd-khartoum": { cx: 505, cy: 305 },
  "atbara-merowe": { cx: 500, cy: 230 },
  "khartoum-merowe": { cx: 350, cy: 260 },
  "merowe-aswan": { cx: 315, cy: 178 },
  "aswan-egypt": { cx: 330, cy: 110 },
  "egypt-cairo": { cx: 335, cy: 64 },
  "cairo-delta": { cx: 400, cy: 42 },
};

const DEFAULT_PARAMS: Params = {
  month: 8,
  rainfallScale: 1,
  droughtStress: 0,
  gerdRelease: 1_400,
  aswanRelease: 2_000,
  irrigationScale: 1,
  suddLoss: 0.42,
};

const PRESETS: Array<{ name: string; params: Params }> = [
  { name: "Normal year", params: DEFAULT_PARAMS },
  {
    name: "Drought year",
    params: { ...DEFAULT_PARAMS, droughtStress: 0.35, rainfallScale: 0.75, aswanRelease: 1_550 },
  },
  {
    name: "High GERD release",
    params: { ...DEFAULT_PARAMS, gerdRelease: 2_600, rainfallScale: 1.05 },
  },
  {
    name: "GERD filling",
    params: { ...DEFAULT_PARAMS, gerdRelease: 650, rainfallScale: 0.95 },
  },
  {
    name: "High irrigation",
    params: { ...DEFAULT_PARAMS, irrigationScale: 1.55, aswanRelease: 2_500 },
  },
  {
    name: "Low Aswan release",
    params: { ...DEFAULT_PARAMS, aswanRelease: 1_100, irrigationScale: 1.15 },
  },
];

export default function App() {
  const [params, setParams] = useState<Params>(DEFAULT_PARAMS);
  const [playing, setPlaying] = useState(false);
  const [baseline, setBaseline] = useState<CopernicusMonth[]>(COPERNICUS_MONTHLY);
  const [baselineLabel, setBaselineLabel] = useState("Packaged Copernicus demo baseline");
  const result = useMemo(() => simulate(params, baseline), [params, baseline]);
  const yearResults = useMemo(
    () => MONTHS.map((_, i) => simulate({ ...params, month: i + 1 }, baseline)),
    [params, baseline],
  );

  useEffect(() => {
    let cancelled = false;
    fetch("/copernicus-baseline.json", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error("no generated baseline");
        return response.json() as Promise<BaselinePayload>;
      })
      .then((payload) => {
        if (cancelled || !Array.isArray(payload.months) || payload.months.length !== 12) return;
        setBaseline(payload.months);
        const period = payload.period ? `${payload.period[0]}-${payload.period[1]}` : "real export";
        setBaselineLabel(`Generated Copernicus baseline (${period})`);
      })
      .catch(() => {
        if (!cancelled) setBaselineLabel("Packaged Copernicus demo baseline");
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      setParams((p) => ({ ...p, month: p.month === 12 ? 1 : p.month + 1 }));
    }, 850);
    return () => window.clearInterval(id);
  }, [playing]);

  return (
    <main className="h-screen overflow-hidden bg-zinc-950 text-zinc-100">
      <div className="grid h-full grid-cols-[minmax(280px,320px)_minmax(520px,1fr)_minmax(280px,300px)]">
        <aside className="min-h-0 overflow-y-auto border-r border-zinc-800 bg-zinc-900 p-4">
          <div className="mb-5">
            <h1 className="text-lg font-semibold">Nile Flow Simulator</h1>
            <p className="mt-1 text-sm text-zinc-400">
              Draft monthly routing model backed by packaged Copernicus-style
              baseline data for branch inflows, runoff stress, crop activity,
              and reservoir water extent.
            </p>
            <div className="mt-3 rounded border border-cyan-900/60 bg-cyan-950/30 px-3 py-2 text-xs text-cyan-100">
              {baselineLabel}
            </div>
          </div>

          <div className="mb-5 grid grid-cols-2 gap-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.name}
                type="button"
                onClick={() => setParams(preset.params)}
                className="rounded border border-zinc-700 bg-zinc-950 px-2 py-2 text-left text-xs text-zinc-200 hover:border-cyan-500"
              >
                {preset.name}
              </button>
            ))}
          </div>

          <div className="space-y-5">
            <Range
              label="Month"
              value={params.month}
              min={1}
              max={12}
              step={1}
              display={MONTHS[params.month - 1]}
              onChange={(month) => setParams((p) => ({ ...p, month }))}
            />
            <button
              type="button"
              onClick={() => setPlaying((p) => !p)}
              className="w-full rounded bg-cyan-500 px-3 py-2 text-sm font-semibold text-zinc-950 hover:bg-cyan-400"
            >
              {playing ? "Pause year playback" : "Play year playback"}
            </button>
            <Range
              label="Basin rainfall"
              value={params.rainfallScale}
              min={0.5}
              max={1.5}
              step={0.05}
              display={`${params.rainfallScale.toFixed(2)}x`}
              onChange={(rainfallScale) => setParams((p) => ({ ...p, rainfallScale }))}
            />
            <Range
              label="Drought stress"
              value={params.droughtStress}
              min={0}
              max={0.7}
              step={0.05}
              display={`${Math.round(params.droughtStress * 100)}%`}
              onChange={(droughtStress) => setParams((p) => ({ ...p, droughtStress }))}
            />
            <Range
              label="GERD release"
              value={params.gerdRelease}
              min={200}
              max={3_200}
              step={50}
              display={`${Math.round(params.gerdRelease)} m3/s`}
              onChange={(gerdRelease) => setParams((p) => ({ ...p, gerdRelease }))}
            />
            <Range
              label="Aswan release"
              value={params.aswanRelease}
              min={700}
              max={4_000}
              step={50}
              display={`${Math.round(params.aswanRelease)} m3/s`}
              onChange={(aswanRelease) => setParams((p) => ({ ...p, aswanRelease }))}
            />
            <Range
              label="Irrigation demand"
              value={params.irrigationScale}
              min={0.5}
              max={1.8}
              step={0.05}
              display={`${params.irrigationScale.toFixed(2)}x`}
              onChange={(irrigationScale) => setParams((p) => ({ ...p, irrigationScale }))}
            />
            <Range
              label="Sudd wetland loss"
              value={params.suddLoss}
              min={0.2}
              max={0.65}
              step={0.01}
              display={`${Math.round(params.suddLoss * 100)}%`}
              onChange={(suddLoss) => setParams((p) => ({ ...p, suddLoss }))}
            />
          </div>

          <Assumptions baselineLabel={baselineLabel} />
        </aside>

        <section className="relative min-h-0 min-w-0 overflow-hidden bg-[#071017]">
          <FlowMap result={result} />
        </section>

        <aside className="min-h-0 overflow-y-auto border-l border-zinc-800 bg-zinc-900 p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Monthly outputs
          </h2>
          <Metric label="Delta outflow" value={`${result.metrics.deltaFlow.toFixed(0)} m3/s`} />
          <Metric
            label="Cairo water served"
            value={`${Math.round(result.metrics.cairoServedPct * 100)}%`}
          />
          <Metric
            label="Irrigation served"
            value={`${Math.round(result.metrics.irrigationServedPct * 100)}%`}
          />
          <Metric label="Hydropower" value={`${result.metrics.energyGwh.toFixed(0)} GWh`} />
          <Metric
            label="GERD storage"
            value={`${signed(result.metrics.gerdStorageDelta)} mcm`}
          />
          <Metric
            label="Aswan storage"
            value={`${signed(result.metrics.aswanStorageDelta)} mcm`}
          />
          <Metric
            label="ERA5-Land runoff index"
            value={result.metrics.runoffIndex.toFixed(2)}
          />
          <Metric label="ERA5-Land PET" value={`${result.metrics.petMm.toFixed(0)} mm`} />

          <h2 className="mb-2 mt-5 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Year shape
          </h2>
          <YearChart results={yearResults} activeMonth={params.month} />

          <h2 className="mb-2 mt-5 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Reservoir area proxy
          </h2>
          <div className="rounded border border-zinc-800 bg-zinc-950 p-3 text-sm">
            <div className="flex justify-between">
              <span className="text-zinc-400">GERD water body</span>
              <span className="tabular-nums">{result.metrics.gerdAreaKm2.toFixed(0)} km2</span>
            </div>
            <div className="mt-1 flex justify-between">
              <span className="text-zinc-400">Aswan water body</span>
              <span className="tabular-nums">{result.metrics.aswanAreaKm2.toFixed(0)} km2</span>
            </div>
          </div>

          <h2 className="mb-2 mt-5 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Reach flows
          </h2>
          <div className="space-y-2">
            {result.segments.map((s) => (
              <div key={s.id} className="flex items-center justify-between text-sm">
                <span className="truncate pr-2 text-zinc-300">{s.label}</span>
                <span className="tabular-nums text-zinc-100">{s.flow.toFixed(0)}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </main>
  );
}

function FlowMap({ result }: { result: SimResult }) {
  return (
    <svg viewBox="0 0 720 620" className="h-full w-full" role="img" aria-label="Nile water flow">
      <defs>
        <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <rect width="720" height="620" fill="#071017" />
      <path d="M0 0H720V620H0Z" fill="#08151f" />
      <text x="34" y="44" fill="#e4e4e7" fontSize="24" fontWeight="700">
        {MONTHS[result.month - 1]} water routing
      </text>
      <text x="34" y="70" fill="#a1a1aa" fontSize="13">
        Line width follows CEMS GloFAS-style baseline discharge adjusted by scenario sliders.
      </text>

      {result.segments.map((segment) => (
        <FlowLine key={segment.id} segment={segment} result={result} />
      ))}

      <TransferMarker
        x={214}
        y={410}
        label="Sudd loss"
        value={result.transfers.suddLoss}
        tone="loss"
      />
      <TransferMarker
        x={470}
        y={286}
        label="Gezira"
        value={result.transfers.geziraTake}
        tone="take"
        align="right"
      />
      <TransferMarker
        x={268}
        y={122}
        label="Farms"
        value={result.transfers.egyptAgTake}
        tone="take"
      />
      <TransferMarker
        x={460}
        y={82}
        label="Cairo"
        value={result.transfers.cairoTake}
        tone="take"
        align="right"
      />

      {Object.entries(result.nodes).map(([id, node]) => (
        <g key={id} transform={`translate(${node.x} ${node.y})`} pointerEvents="none">
          {renderNodeLabel(id as NodeId, node)}
          <circle r={nodeRadius(node.flow)} fill="#e5e7eb" opacity="0.95" />
          <circle r={nodeRadius(node.flow) + 5} fill="none" stroke="#e5e7eb" opacity="0.16" />
        </g>
      ))}
    </svg>
  );
}

function FlowLine({ segment, result }: { segment: FlowSegment; result: SimResult }) {
  const from = result.nodes[segment.from];
  const to = result.nodes[segment.to];
  const curve = CURVES[segment.id];
  const width = lineWidth(segment.flow);
  const path = `M ${from.x} ${from.y} Q ${curve.cx} ${curve.cy} ${to.x} ${to.y}`;
  return (
    <>
      <path
        d={path}
        fill="none"
        stroke="#020617"
        strokeWidth={width + 8}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.72"
      />
      <path
        d={path}
        fill="none"
        stroke={branchColor(segment.branch)}
        strokeWidth={width}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.9"
        filter="url(#glow)"
      />
    </>
  );
}

function TransferMarker({
  x,
  y,
  label,
  value,
  tone,
  align = "left",
}: {
  x: number;
  y: number;
  label: string;
  value: number;
  tone: "loss" | "take";
  align?: "left" | "right";
}) {
  const color = tone === "loss" ? "#fb7185" : "#fbbf24";
  const dir = align === "right" ? 1 : -1;
  const labelX = align === "right" ? 14 : -72;
  const anchor = align === "right" ? "start" : "start";
  return (
    <g transform={`translate(${x} ${y})`}>
      <line x1="0" y1="0" x2={dir * 26} y2="-18" stroke={color} strokeWidth="2" opacity="0.75" />
      <circle cx={dir * 31} cy="-22" r="5" fill={color} />
      <text x={labelX} y="-28" fill="#f4f4f5" fontSize="10" fontWeight="700" textAnchor={anchor}>
        {label}
      </text>
      <text x={labelX} y="-15" fill="#a1a1aa" fontSize="10" textAnchor={anchor}>
        -{value.toFixed(0)} m3/s
      </text>
    </g>
  );
}

function renderNodeLabel(
  id: NodeId,
  node: { label: string; x: number; y: number; flow: number },
) {
  const pos = LABEL_POS[id];
  const anchor = pos.anchor ?? "start";
  const width = Math.max(64, node.label.length * 6.2);
  return (
    <g transform={`translate(${pos.x} ${pos.y})`}>
      <rect
        x={anchor === "end" ? -width - 8 : -8}
        y="-14"
        width={width + 16}
        height="31"
        rx="5"
        fill="#071017"
        opacity="0.78"
      />
      <text
        x={anchor === "end" ? -6 : 0}
        y="-2"
        fill="#f4f4f5"
        fontSize="11"
        fontWeight={id === "delta" ? 700 : 600}
        textAnchor={anchor}
      >
        {node.label}
      </text>
      <text
        x={anchor === "end" ? -6 : 0}
        y="12"
        fill="#a1a1aa"
        fontSize="9"
        textAnchor={anchor}
      >
        {node.flow.toFixed(0)} m3/s
      </text>
    </g>
  );
}

function Range({
  label,
  value,
  min,
  max,
  step,
  display,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  display: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <div className="mb-1 flex items-center justify-between gap-3 text-sm">
        <span className="text-zinc-200">{label}</span>
        <span className="tabular-nums text-zinc-400">{display}</span>
      </div>
      <input
        type="range"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full accent-cyan-400"
      />
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-2 rounded border border-zinc-800 bg-zinc-950 px-3 py-2">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function YearChart({ results, activeMonth }: { results: SimResult[]; activeMonth: number }) {
  const maxDelta = Math.max(1, ...results.map((r) => r.metrics.deltaFlow));
  const maxEnergy = Math.max(1, ...results.map((r) => r.metrics.energyGwh));
  const w = 260;
  const h = 150;
  const pad = 24;
  const points = results
    .map((r, i) => {
      const x = pad + (i / 11) * (w - pad * 2);
      const y = h - pad - (r.metrics.deltaFlow / maxDelta) * (h - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="rounded border border-zinc-800 bg-zinc-950 p-2">
      <svg viewBox={`0 0 ${w} ${h}`} className="h-40 w-full">
        <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#3f3f46" />
        <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="#3f3f46" />
        {results.map((r, i) => {
          const x = pad + (i / 11) * (w - pad * 2);
          const energyHeight = (r.metrics.energyGwh / maxEnergy) * 42;
          const active = i + 1 === activeMonth;
          return (
            <g key={r.month}>
              <rect
                x={x - 5}
                y={h - pad - energyHeight}
                width="10"
                height={energyHeight}
                fill={active ? "#fbbf24" : "#52525b"}
                opacity={active ? 1 : 0.75}
              />
              <text x={x - 4} y={h - 5} fill="#a1a1aa" fontSize="8">
                {MONTHS[i][0]}
              </text>
            </g>
          );
        })}
        <polyline points={points} fill="none" stroke="#22d3ee" strokeWidth="3" />
        {results.map((r, i) => {
          const x = pad + (i / 11) * (w - pad * 2);
          const y = h - pad - (r.metrics.deltaFlow / maxDelta) * (h - pad * 2);
          return (
            <circle
              key={r.month}
              cx={x}
              cy={y}
              r={i + 1 === activeMonth ? 4 : 2.5}
              fill={i + 1 === activeMonth ? "#f4f4f5" : "#22d3ee"}
            />
          );
        })}
        <text x={pad} y={16} fill="#a1a1aa" fontSize="10">
          cyan: delta flow, bars: energy
        </text>
      </svg>
    </div>
  );
}

function Assumptions({ baselineLabel }: { baselineLabel: string }) {
  return (
    <section className="mt-6 rounded border border-zinc-800 bg-zinc-950 p-3 text-xs text-zinc-400">
      <h2 className="mb-2 font-semibold uppercase tracking-wide text-zinc-300">
        Copernicus demo data
      </h2>
      <p className="mb-2 text-cyan-100">{baselineLabel}</p>
      <p className="mb-2 leading-relaxed">{COPERNICUS_BASELINE_NOTE}</p>
      <ul className="mb-3 space-y-1">
        {COPERNICUS_PRODUCTS.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      <h2 className="mb-2 font-semibold uppercase tracking-wide text-zinc-300">
        Model assumptions
      </h2>
      <ul className="space-y-1">
        <li>River sources start from monthly GloFAS-style discharge baselines.</li>
        <li>Rainfall and drought sliders perturb those baselines as scenarios.</li>
        <li>Crop activity scales irrigation demand from Sentinel-2/CLMS-style signals.</li>
        <li>Reservoir water area affects drawdown and evaporation stress.</li>
        <li>Hydropower uses release x head x efficiency.</li>
      </ul>
    </section>
  );
}

function simulate(params: Params, baseline: CopernicusMonth[]): SimResult {
  const data = baseline[params.month - 1] ?? COPERNICUS_MONTHLY[params.month - 1];
  const dryFactor = 1 - params.droughtStress;
  const runoffStress = clamp(params.rainfallScale * dryFactor, 0.15, 1.7);
  const runoffAdjustment = 0.82 + 0.18 * data.era5Land.runoffIndex;
  const whiteSource = data.glofas.whiteNileM3s * runoffStress * runoffAdjustment;
  const blueSource = data.glofas.blueNileToGerdM3s * runoffStress * runoffAdjustment;
  const atbaraSource = data.glofas.atbaraM3s * runoffStress * runoffAdjustment;
  const petStress = 1 + params.droughtStress * 0.55 + Math.max(0, 1 - params.rainfallScale) * 0.25;
  const petMm = data.era5Land.petMm * petStress;

  const whiteAfterSudd = whiteSource * (1 - params.suddLoss);
  const blueToGerd = route(blueSource, 0.92);
  const gerd = reservoir(
    blueToGerd,
    params.gerdRelease,
    74_000,
    36_000,
    133,
    0.9,
    data.waterBodies.gerdAreaKm2,
    petMm,
  );
  const blueToKhartoum = route(gerd.outflow, 0.9);

  const geziraDemand =
    cropDemand(470, data.sentinel2.geziraCropActivity, petStress) * params.irrigationScale;
  const geziraTake = Math.min(blueToKhartoum, geziraDemand);
  const blueAfterGezira = blueToKhartoum - geziraTake;
  const khartoumFlow = whiteAfterSudd + blueAfterGezira;

  const khartoumMunicipal = 10;
  const afterKhartoum = Math.max(0, khartoumFlow - khartoumMunicipal);
  const mainAfterAtbara = afterKhartoum + atbaraSource;
  const merowe = reservoir(mainAfterAtbara, mainAfterAtbara, 12_500, 8_000, 67, 0.88, 720, petMm);
  const aswanInflow = route(merowe.outflow, 0.88);
  const aswan = reservoir(
    aswanInflow,
    params.aswanRelease,
    162_000,
    104_000,
    70,
    0.88,
    data.waterBodies.aswanAreaKm2,
    petMm,
  );

  const egyptAgDemand =
    cropDemand(1_420, data.sentinel2.egyptCropActivity, petStress) * params.irrigationScale;
  const egyptAgTake = Math.min(aswan.outflow, egyptAgDemand);
  const afterEgyptAg = aswan.outflow - egyptAgTake;
  const cairoDemand = 145;
  const cairoTake = Math.min(afterEgyptAg, cairoDemand);
  const deltaFlow = Math.max(0, afterEgyptAg - cairoTake);

  const irrigationDemand = geziraDemand + egyptAgDemand;
  const irrigationServed = irrigationDemand > 0 ? (geziraTake + egyptAgTake) / irrigationDemand : 1;
  const cairoServed = cairoDemand > 0 ? cairoTake / cairoDemand : 1;

  const nodeFlows: Record<NodeId, number> = {
    victoria: whiteSource,
    sudd: whiteAfterSudd,
    tana: blueSource,
    gerd: gerd.outflow,
    khartoum: khartoumFlow,
    atbara: atbaraSource,
    merowe: merowe.outflow,
    aswan: aswan.outflow,
    egyptAg: afterEgyptAg,
    cairo: deltaFlow,
    delta: deltaFlow,
  };

  const nodes = Object.fromEntries(
    Object.entries(NODE_POS).map(([id, pos]) => [
      id,
      { ...pos, flow: nodeFlows[id as NodeId] },
    ]),
  ) as SimResult["nodes"];

  const segments: FlowSegment[] = [
    { id: "victoria-sudd", label: "White Nile to Sudd", from: "victoria", to: "sudd", flow: whiteSource, branch: "white" },
    { id: "sudd-khartoum", label: "White Nile after Sudd", from: "sudd", to: "khartoum", flow: whiteAfterSudd, branch: "white" },
    { id: "tana-gerd", label: "Blue Nile to GERD", from: "tana", to: "gerd", flow: blueToGerd, branch: "blue" },
    { id: "gerd-khartoum", label: "Blue Nile to Khartoum", from: "gerd", to: "khartoum", flow: blueAfterGezira, branch: "blue" },
    { id: "atbara-merowe", label: "Atbara tributary", from: "atbara", to: "merowe", flow: atbaraSource, branch: "atbara" },
    { id: "khartoum-merowe", label: "Main Nile in Sudan", from: "khartoum", to: "merowe", flow: afterKhartoum, branch: "main" },
    { id: "merowe-aswan", label: "Main Nile to Aswan", from: "merowe", to: "aswan", flow: aswanInflow, branch: "main" },
    { id: "aswan-egypt", label: "Aswan release", from: "aswan", to: "egyptAg", flow: aswan.outflow, branch: "main" },
    { id: "egypt-cairo", label: "Egypt reach", from: "egyptAg", to: "cairo", flow: afterEgyptAg, branch: "main" },
    { id: "cairo-delta", label: "Cairo to Delta", from: "cairo", to: "delta", flow: deltaFlow, branch: "main" },
  ];

  return {
    month: params.month,
    dataMonthLabel: data.label,
    segments,
    nodes,
    transfers: {
      suddLoss: whiteSource * params.suddLoss,
      geziraTake,
      egyptAgTake,
      cairoTake,
    },
    metrics: {
      deltaFlow,
      cairoServedPct: cairoServed,
      irrigationServedPct: irrigationServed,
      energyGwh: gerd.energy + merowe.energy + aswan.energy,
      gerdStorageDelta: gerd.storageDelta,
      aswanStorageDelta: aswan.storageDelta,
      runoffIndex: data.era5Land.runoffIndex,
      petMm,
      gerdAreaKm2: data.waterBodies.gerdAreaKm2,
      aswanAreaKm2: data.waterBodies.aswanAreaKm2,
    },
  };
}

function route(flow: number, attenuation: number) {
  return Math.max(0, flow * attenuation);
}

function cropDemand(baselineM3s: number, cropActivity: number, petStress: number) {
  return baselineM3s * (0.35 + 0.95 * cropActivity) * petStress;
}

function reservoir(
  inflow: number,
  targetRelease: number,
  capacityMcm: number,
  storageMcm: number,
  headM: number,
  efficiency: number,
  waterAreaKm2: number,
  petMm: number,
) {
  const monthSeconds = 30 * 24 * 60 * 60;
  const availableDrawdown = Math.max(0, storageMcm - capacityMcm * 0.2) * 1_000_000 / monthSeconds;
  const outflow = Math.max(0, Math.min(targetRelease, inflow + availableDrawdown));
  const evapM3s = (petMm * waterAreaKm2 * 1_000) / monthSeconds;
  const storageDelta = (inflow - outflow - evapM3s) * monthSeconds / 1_000_000;
  const energy = outflow * monthSeconds * 1_000 * 9.81 * headM * efficiency / 3.6e12;
  return { outflow, storageDelta, energy };
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function lineWidth(flow: number) {
  return Math.max(2, Math.min(22, 2 + Math.sqrt(flow) * 0.36));
}

function nodeRadius(flow: number) {
  return Math.max(5, Math.min(16, 5 + Math.sqrt(flow) * 0.16));
}

function branchColor(branch: FlowSegment["branch"]) {
  if (branch === "blue") return "#38bdf8";
  if (branch === "white") return "#7dd3fc";
  if (branch === "atbara") return "#fbbf24";
  return "#22d3ee";
}

function signed(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(0)}`;
}
