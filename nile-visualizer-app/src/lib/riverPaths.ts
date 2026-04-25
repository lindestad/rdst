// Real-world Nile waypoint polylines (lon, lat). The visualizer slices these
// against the projected screen positions of each edge's from/to node, so a
// single set of rivers serves every dataset granularity.

type Coord = [number, number];

export type River = {
  id: string;
  name: string;
  coords: Coord[];
};

export const rivers: River[] = [
  {
    id: "white-nile",
    name: "White Nile",
    coords: [
      [33.20, 0.42],   // Lake Victoria outlet / Jinja
      [32.95, 1.15],
      [32.40, 1.65],
      [31.69, 2.28],   // Murchison Falls
      [30.95, 1.93],   // Lake Albert
      [31.55, 3.05],
      [32.07, 3.60],   // Nimule
      [31.61, 4.85],   // Juba
      [31.55, 6.21],   // Bor
      [30.90, 7.30],
      [30.40, 7.95],   // Sudd center
      [30.85, 8.55],
      [31.30, 9.10],
      [31.65, 9.53],   // Malakal
      [32.05, 11.20],
      [32.55, 13.00],  // Kosti
      [32.55, 14.40],
      [32.53, 15.60],  // Khartoum
    ],
  },
  {
    id: "blue-nile",
    name: "Blue Nile",
    coords: [
      [37.38, 11.60],  // Lake Tana
      [37.55, 11.49],  // Tisisat falls
      [37.10, 11.30],
      [36.40, 11.10],
      [35.65, 11.30],
      [35.09, 11.22],  // GERD
      [34.85, 11.45],
      [34.39, 11.84],  // Roseires
      [33.62, 13.55],  // Sennar
      [33.50, 14.40],  // Wad Madani
      [33.05, 14.95],
      [32.85, 15.30],
      [32.53, 15.60],  // Khartoum
    ],
  },
  {
    id: "atbara",
    name: "Atbara",
    coords: [
      [37.00, 13.50],
      [36.20, 14.30],
      [35.20, 15.30],
      [34.50, 16.50],
      [33.97, 17.67],  // Atbara confluence
    ],
  },
  {
    id: "main-nile",
    name: "Main Nile",
    coords: [
      [32.53, 15.60],  // Khartoum
      [32.70, 16.27],  // 6th cataract Sabaloka
      [33.40, 16.95],
      [33.97, 17.67],  // Atbara confluence
      [33.97, 18.10],  // Berber / 5th cataract
      [33.32, 19.53],  // Abu Hamed (great bend)
      [32.10, 19.10],
      [31.93, 18.68],  // Merowe
      [30.78, 19.30],
      [30.48, 19.18],  // Dongola
      [30.85, 20.30],
      [31.34, 21.79],  // Wadi Halfa
      [32.10, 22.70],
      [32.55, 23.40],
      [32.88, 23.97],  // Aswan
    ],
  },
  {
    id: "lower-nile",
    name: "Lower Nile",
    coords: [
      [32.88, 23.97],  // Aswan
      [32.78, 24.65],
      [32.65, 25.70],  // Luxor
      [32.05, 26.55],
      [31.18, 27.18],  // Asyut
      [31.05, 28.30],
      [31.10, 29.07],  // Beni Suef
      [31.25, 30.06],  // Cairo
      [31.20, 30.60],
      [31.45, 31.10],
      [31.50, 31.50],  // Delta tip
    ],
  },
];

// Real Nile basin sub-region polygons (lon, lat) used as scribble-fill
// "affected zones". These outline actual at-risk geography rather than
// abstract circles around country centroids.
export type ImpactZone = {
  id: string;
  region: string;
  label: string;
  trigger: { kind: "food" | "drinking" | "power" | "storage" | "flow"; nodeIds: string[] };
  geo: Coord[];
};

export const impactZones: ImpactZone[] = [
  {
    id: "nile-delta",
    region: "Egypt",
    label: "Nile Delta agriculture",
    trigger: { kind: "food", nodeIds: ["nile_delta", "delta", "egypt_ag", "cairo"] },
    geo: [
      [29.85, 30.70],
      [30.10, 31.30],
      [30.55, 31.55],
      [31.10, 31.65],
      [31.65, 31.60],
      [32.20, 31.40],
      [32.45, 31.05],
      [32.05, 30.55],
      [31.40, 30.10],
      [30.65, 30.20],
      [30.10, 30.45],
    ],
  },
  {
    id: "egypt-valley",
    region: "Egypt",
    label: "Aswan–Cairo valley",
    trigger: { kind: "food", nodeIds: ["aswan", "aswand", "egypt_ag", "cairo"] },
    geo: [
      [32.55, 24.05],
      [32.95, 24.20],
      [33.10, 25.20],
      [32.55, 25.95],
      [32.10, 27.05],
      [31.55, 28.30],
      [31.10, 29.20],
      [30.85, 30.05],
      [30.65, 30.05],
      [30.95, 28.95],
      [31.40, 27.45],
      [31.85, 26.30],
      [32.30, 25.40],
      [32.45, 24.40],
    ],
  },
  {
    id: "lake-nasser",
    region: "Egypt",
    label: "Lake Nasser reservoir",
    trigger: { kind: "storage", nodeIds: ["aswan", "aswand"] },
    geo: [
      [31.95, 22.05],
      [32.45, 22.05],
      [33.00, 22.45],
      [33.30, 23.20],
      [33.15, 23.85],
      [32.90, 24.05],
      [32.50, 23.85],
      [32.05, 23.30],
      [31.75, 22.65],
    ],
  },
  {
    id: "high-aswan-power",
    region: "Egypt",
    label: "Aswan hydropower",
    trigger: { kind: "power", nodeIds: ["aswan", "aswand"] },
    geo: [
      [32.55, 23.65],
      [33.15, 23.70],
      [33.15, 24.20],
      [32.55, 24.20],
    ],
  },
  {
    id: "gezira",
    region: "Sudan",
    label: "Gezira irrigation",
    trigger: { kind: "food", nodeIds: ["gezira_irr", "khartoum", "karthoum", "singa"] },
    geo: [
      [32.35, 13.40],
      [33.65, 13.40],
      [33.95, 14.30],
      [33.65, 15.10],
      [32.95, 15.50],
      [32.35, 15.10],
      [32.20, 14.20],
    ],
  },
  {
    id: "khartoum-muni",
    region: "Sudan",
    label: "Khartoum drinking water",
    trigger: { kind: "drinking", nodeIds: ["khartoum", "khartoum_muni", "karthoum"] },
    geo: [
      [32.25, 15.40],
      [32.85, 15.40],
      [32.95, 15.80],
      [32.55, 16.00],
      [32.20, 15.85],
    ],
  },
  {
    id: "merowe-power",
    region: "Sudan",
    label: "Merowe hydropower",
    trigger: { kind: "power", nodeIds: ["merowe"] },
    geo: [
      [31.55, 18.45],
      [32.20, 18.50],
      [32.40, 18.95],
      [31.95, 19.15],
      [31.45, 18.95],
    ],
  },
  {
    id: "sudd",
    region: "South Sudan",
    label: "Sudd wetlands",
    trigger: { kind: "flow", nodeIds: ["sudd", "malakal", "white_nile_to_sudd", "southwest"] },
    geo: [
      [29.50, 6.65],
      [30.40, 6.30],
      [31.40, 6.85],
      [32.00, 7.95],
      [32.05, 9.10],
      [31.55, 9.85],
      [30.65, 9.55],
      [29.85, 8.55],
      [29.40, 7.55],
    ],
  },
  {
    id: "tana-basin",
    region: "Ethiopia",
    label: "Lake Tana basin",
    trigger: { kind: "flow", nodeIds: ["lake_tana_outlet", "blue_nile_headwaters", "tana"] },
    geo: [
      [36.85, 11.40],
      [37.35, 11.10],
      [37.85, 11.40],
      [37.85, 12.10],
      [37.40, 12.45],
      [36.95, 12.30],
      [36.75, 11.85],
    ],
  },
  {
    id: "gerd-power",
    region: "Ethiopia",
    label: "GERD hydropower",
    trigger: { kind: "power", nodeIds: ["gerd"] },
    geo: [
      [34.55, 10.95],
      [35.55, 10.85],
      [35.65, 11.45],
      [34.85, 11.60],
      [34.45, 11.35],
    ],
  },
  {
    id: "victoria-basin",
    region: "Uganda",
    label: "Victoria headwaters",
    trigger: { kind: "flow", nodeIds: ["white_nile_headwaters", "lake_victoria_outlet", "victoria"] },
    geo: [
      [31.85, -1.05],
      [33.05, -1.05],
      [33.95, -0.30],
      [33.95, 0.95],
      [33.05, 1.50],
      [31.95, 1.05],
      [31.55, 0.05],
    ],
  },
];
