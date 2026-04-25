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

// Impact zones are downstream consequence regions: places on the map whose
// state depends on stress at one or more upstream nodes. The scribble pattern
// represents the impact, not the cause — the cause is shown by node color
// (lens) and reservoir rings. This decoupling is intentional, so each visual
// layer has exactly one job.
//
// `dimension` lets the overlay gate zones by the active lens:
//   - "delivery": lights up under the Shortage (stress) lens
//   - "flow":     lights up under the Runoff (water) lens
//   - "power":    lights up under the Output (production) lens
// Storage stress is handled by reservoir rings, not polygons.
//
// `causedBy` lists upstream node ids whose deficits propagate here. Use only
// canonical hydmod node ids — legacy digital-twin names never match real runs.
// `deliveryNodes` lists nodes inside the zone whose own demand-met ratios
// also drive the zone (only meaningful for the "delivery" dimension).
export type ImpactDimension = "delivery" | "flow" | "power";

export type DeliveryKind = "drinking" | "food";

export type ImpactZone = {
  id: string;
  region: string;
  label: string;
  dimension: ImpactDimension;
  causedBy: string[];
  // Required for `dimension === "delivery"`. Limits which demand-met signal
  // at `deliveryNodes` drives the zone (so a Gezira food zone and a Khartoum
  // drinking zone can both look at karthoum without firing on each other).
  deliveryKind?: DeliveryKind;
  deliveryNodes?: string[];
  geo: Coord[];
};

// Polygon vertices are real geographic landmarks (longitude, latitude). The
// `smoothPolygonFromGeo` helper converts these to projected viewport coords
// and applies Catmull-Rom smoothing (tension 0.18), so vertices outline the
// shape's "skeleton"; rounded corners and bulges come from the smoother. Use
// more vertices for organic shapes (lakes, wetlands), fewer for compact ones.
export const impactZones: ImpactZone[] = [
  {
    id: "egypt-agriculture",
    region: "Egypt",
    label: "Egyptian Nile valley & delta",
    dimension: "delivery",
    deliveryKind: "food",
    // The cultivable strip along the Nile from Aswan to Cairo plus the delta
    // fan to the Mediterranean. Less Aswan release → less irrigation reaching
    // the valley; Cairo represents the demand sink at the basin tail.
    causedBy: ["aswand"],
    deliveryNodes: ["cairo"],
    // Trace counterclockwise: up the east bank from Aswan, fan out across the
    // delta to the Mediterranean coast, back down the west bank to Aswan.
    geo: [
      [33.05, 24.05], // Aswan, east bank
      [32.85, 25.10], // east of Edfu/Esna
      [32.60, 26.20], // east of Qena bend
      [32.20, 27.40], // east of Asyut
      [31.65, 28.55], // east of Minya
      [31.30, 29.55], // east approach to Cairo
      [31.50, 30.05], // Cairo, east of river
      [31.95, 30.45], // east delta apex
      [32.30, 30.95],
      [32.40, 31.30], // Port Said
      [31.85, 31.55], // Damietta coast
      [31.10, 31.55], // Rosetta coast
      [30.45, 31.45],
      [29.85, 31.20], // Alexandria
      [30.05, 30.70],
      [30.55, 30.35], // west delta apex
      [30.95, 30.05], // Cairo, west of river
      [31.15, 29.55], // west of Beni Suef
      [31.50, 28.55],
      [32.10, 27.40],
      [32.50, 26.20],
      [32.75, 25.10],
      [32.85, 24.05], // Aswan, west bank
    ],
  },
  {
    id: "gezira",
    region: "Sudan",
    label: "Gezira irrigation scheme",
    dimension: "delivery",
    deliveryKind: "food",
    // Triangular plain between the Blue and White Niles south of Khartoum.
    // Roseires/Sennar releases feed the canal system; Khartoum holds the
    // consolidated irrigation demand for the scheme.
    causedBy: ["roseires", "singa"],
    deliveryNodes: ["karthoum"],
    geo: [
      [32.50, 15.55], // Khartoum confluence (apex)
      [33.05, 14.85], // east bulge along Blue Nile
      [33.55, 13.55], // Sennar / Singa
      [33.30, 13.40],
      [32.80, 13.30],
      [32.40, 13.40], // Kosti, on White Nile
      [32.30, 14.10],
      [32.35, 14.95],
      [32.40, 15.40],
    ],
  },
  {
    id: "khartoum-muni",
    region: "Sudan",
    label: "Khartoum drinking water",
    dimension: "delivery",
    deliveryKind: "drinking",
    causedBy: [],
    deliveryNodes: ["karthoum"],
    // Greater Khartoum (Khartoum / Omdurman / Khartoum North) at the
    // Blue/White Nile confluence — about 25 km radius.
    geo: [
      [32.30, 15.50],
      [32.45, 15.42],
      [32.70, 15.42],
      [32.88, 15.50],
      [32.92, 15.68],
      [32.78, 15.88],
      [32.55, 15.92],
      [32.32, 15.82],
      [32.25, 15.65],
    ],
  },
  {
    id: "sudd",
    region: "South Sudan",
    label: "Sudd wetlands",
    dimension: "flow",
    // World's largest tropical wetland — the Bahr el Jebel splays out across
    // ~30,000 km² before reforming as the White Nile at Malakal. Extent
    // depends on through-flow from Lake Victoria via southwest.
    causedBy: ["victoria", "southwest"],
    geo: [
      [28.80, 7.40],
      [29.30, 6.40],
      [30.20, 5.95], // near Bor, southern reach
      [31.10, 6.30],
      [31.75, 7.20],
      [32.10, 8.20],
      [32.20, 9.10],
      [31.75, 9.75], // Malakal exit
      [31.10, 10.05],
      [30.30, 9.90],
      [29.55, 9.45],
      [28.95, 8.55],
      [28.65, 7.95],
    ],
  },
  {
    id: "tana-headwaters",
    region: "Ethiopia",
    label: "Lake Tana basin",
    dimension: "flow",
    // Lake Tana ≈ 84 km × 66 km, source of the Blue Nile in the Ethiopian
    // highlands. Roughly oval, slightly elongated south-to-north.
    causedBy: ["tana"],
    geo: [
      [37.00, 11.55],
      [37.30, 11.45],
      [37.60, 11.55],
      [37.78, 11.85],
      [37.65, 12.20],
      [37.30, 12.32],
      [36.98, 12.20],
      [36.88, 11.90],
    ],
  },
  {
    id: "victoria-headwaters",
    region: "Uganda",
    label: "Lake Victoria outflow",
    dimension: "flow",
    // Lake Victoria's northern half (the south is below the visible map).
    // The basin frame clips at lat -1.2°, so vertices stay above that line.
    // Outflow at Jinja's Owen Falls drives the entire White Nile.
    causedBy: ["victoria"],
    geo: [
      [31.65, -1.10],
      [32.30, -1.18],
      [33.10, -1.18],
      [33.85, -1.05],
      [34.00, -0.40],
      [33.85, 0.15],
      [33.40, 0.50],
      [32.80, 0.55],
      [32.10, 0.30],
      [31.65, -0.20],
      [31.55, -0.65],
    ],
  },
  {
    id: "gerd-power",
    region: "Ethiopia",
    label: "GERD reservoir",
    dimension: "power",
    // Grand Ethiopian Renaissance Dam reservoir on the Blue Nile near the
    // Sudanese border. Long thin shape filling the river canyon.
    causedBy: ["gerd"],
    geo: [
      [34.65, 11.10],
      [35.00, 10.95],
      [35.30, 10.95],
      [35.50, 11.10],
      [35.55, 11.30],
      [35.40, 11.50],
      [35.05, 11.55],
      [34.80, 11.50],
      [34.60, 11.30],
    ],
  },
  {
    id: "merowe-power",
    region: "Sudan",
    label: "Merowe reservoir",
    dimension: "power",
    // Merowe Dam at ~31.83°E, 18.69°N. Reservoir extends upstream along the
    // Nile fourth-cataract bend.
    causedBy: ["merowe"],
    geo: [
      [31.45, 18.55],
      [31.85, 18.45],
      [32.20, 18.50],
      [32.40, 18.75],
      [32.30, 19.00],
      [31.95, 19.10],
      [31.55, 19.00],
      [31.40, 18.80],
    ],
  },
  {
    id: "high-aswan-power",
    region: "Egypt",
    label: "Lake Nasser",
    dimension: "power",
    // Reservoir behind the High Aswan Dam — ~5,250 km² spanning ~500 km
    // south from the dam (32.88°E, 23.97°N) into Sudan as Lake Nubia. Shown
    // as a long narrow N-S lake.
    causedBy: ["aswand"],
    geo: [
      [32.65, 23.95],
      [32.95, 23.80],
      [33.00, 22.80],
      [32.95, 21.80],
      [32.60, 21.20],
      [32.10, 21.05],
      [31.80, 21.55],
      [31.70, 22.60],
      [31.85, 23.40],
      [32.20, 23.85],
    ],
  },
];
