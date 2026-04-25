export type CopernicusMonth = {
  month: number;
  label: string;
  glofas: {
    whiteNileM3s: number;
    blueNileToGerdM3s: number;
    atbaraM3s: number;
  };
  era5Land: {
    runoffIndex: number;
    petMm: number;
  };
  sentinel2: {
    geziraCropActivity: number;
    egyptCropActivity: number;
  };
  waterBodies: {
    gerdAreaKm2: number;
    aswanAreaKm2: number;
  };
};

export const COPERNICUS_BASELINE_NOTE =
  "Demo climatology shaped from Copernicus product roles. Replace these constants with exported CEMS GloFAS, ERA5-Land, Sentinel-2/CLMS, and Water Bodies monthly extracts for a defensible run.";

export const COPERNICUS_PRODUCTS = [
  "CEMS GloFAS historical river discharge: branch inflow boundary conditions",
  "ERA5-Land: runoff index and PET stress for scenario adjustment",
  "Sentinel-2 L2A / CLMS land cover: crop activity in irrigation zones",
  "CLMS Water Bodies: reservoir surface area proxy for storage and evaporation",
];

export const COPERNICUS_MONTHLY: CopernicusMonth[] = [
  {
    month: 1,
    label: "Jan",
    glofas: { whiteNileM3s: 780, blueNileToGerdM3s: 310, atbaraM3s: 25 },
    era5Land: { runoffIndex: 0.52, petMm: 118 },
    sentinel2: { geziraCropActivity: 0.72, egyptCropActivity: 0.88 },
    waterBodies: { gerdAreaKm2: 1030, aswanAreaKm2: 4780 },
  },
  {
    month: 2,
    label: "Feb",
    glofas: { whiteNileM3s: 805, blueNileToGerdM3s: 270, atbaraM3s: 20 },
    era5Land: { runoffIndex: 0.47, petMm: 130 },
    sentinel2: { geziraCropActivity: 0.68, egyptCropActivity: 0.86 },
    waterBodies: { gerdAreaKm2: 1015, aswanAreaKm2: 4680 },
  },
  {
    month: 3,
    label: "Mar",
    glofas: { whiteNileM3s: 835, blueNileToGerdM3s: 245, atbaraM3s: 18 },
    era5Land: { runoffIndex: 0.44, petMm: 154 },
    sentinel2: { geziraCropActivity: 0.62, egyptCropActivity: 0.79 },
    waterBodies: { gerdAreaKm2: 1000, aswanAreaKm2: 4550 },
  },
  {
    month: 4,
    label: "Apr",
    glofas: { whiteNileM3s: 855, blueNileToGerdM3s: 290, atbaraM3s: 24 },
    era5Land: { runoffIndex: 0.50, petMm: 176 },
    sentinel2: { geziraCropActivity: 0.58, egyptCropActivity: 0.72 },
    waterBodies: { gerdAreaKm2: 995, aswanAreaKm2: 4420 },
  },
  {
    month: 5,
    label: "May",
    glofas: { whiteNileM3s: 875, blueNileToGerdM3s: 430, atbaraM3s: 55 },
    era5Land: { runoffIndex: 0.64, petMm: 194 },
    sentinel2: { geziraCropActivity: 0.66, egyptCropActivity: 0.84 },
    waterBodies: { gerdAreaKm2: 1005, aswanAreaKm2: 4310 },
  },
  {
    month: 6,
    label: "Jun",
    glofas: { whiteNileM3s: 890, blueNileToGerdM3s: 1050, atbaraM3s: 250 },
    era5Land: { runoffIndex: 0.86, petMm: 207 },
    sentinel2: { geziraCropActivity: 0.78, egyptCropActivity: 0.94 },
    waterBodies: { gerdAreaKm2: 1080, aswanAreaKm2: 4240 },
  },
  {
    month: 7,
    label: "Jul",
    glofas: { whiteNileM3s: 900, blueNileToGerdM3s: 3150, atbaraM3s: 1110 },
    era5Land: { runoffIndex: 1.25, petMm: 214 },
    sentinel2: { geziraCropActivity: 0.92, egyptCropActivity: 0.98 },
    waterBodies: { gerdAreaKm2: 1320, aswanAreaKm2: 4280 },
  },
  {
    month: 8,
    label: "Aug",
    glofas: { whiteNileM3s: 910, blueNileToGerdM3s: 5250, atbaraM3s: 2050 },
    era5Land: { runoffIndex: 1.58, petMm: 205 },
    sentinel2: { geziraCropActivity: 0.96, egyptCropActivity: 0.95 },
    waterBodies: { gerdAreaKm2: 1620, aswanAreaKm2: 4480 },
  },
  {
    month: 9,
    label: "Sep",
    glofas: { whiteNileM3s: 895, blueNileToGerdM3s: 4380, atbaraM3s: 1580 },
    era5Land: { runoffIndex: 1.42, petMm: 184 },
    sentinel2: { geziraCropActivity: 0.88, egyptCropActivity: 0.87 },
    waterBodies: { gerdAreaKm2: 1740, aswanAreaKm2: 4760 },
  },
  {
    month: 10,
    label: "Oct",
    glofas: { whiteNileM3s: 865, blueNileToGerdM3s: 2050, atbaraM3s: 480 },
    era5Land: { runoffIndex: 0.96, petMm: 162 },
    sentinel2: { geziraCropActivity: 0.76, egyptCropActivity: 0.78 },
    waterBodies: { gerdAreaKm2: 1680, aswanAreaKm2: 4930 },
  },
  {
    month: 11,
    label: "Nov",
    glofas: { whiteNileM3s: 825, blueNileToGerdM3s: 780, atbaraM3s: 120 },
    era5Land: { runoffIndex: 0.68, petMm: 138 },
    sentinel2: { geziraCropActivity: 0.70, egyptCropActivity: 0.82 },
    waterBodies: { gerdAreaKm2: 1480, aswanAreaKm2: 4990 },
  },
  {
    month: 12,
    label: "Dec",
    glofas: { whiteNileM3s: 795, blueNileToGerdM3s: 420, atbaraM3s: 45 },
    era5Land: { runoffIndex: 0.57, petMm: 122 },
    sentinel2: { geziraCropActivity: 0.74, egyptCropActivity: 0.90 },
    waterBodies: { gerdAreaKm2: 1190, aswanAreaKm2: 4920 },
  },
];
