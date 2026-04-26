// Map viewport — used by SVG viewBox and the OSM tile background. Changing
// these requires updating riverPaths/mapLayout offsets in lockstep.
export const VIEWBOX_W = 1040;
export const VIEWBOX_H = 720;

// Pan/zoom limits for useMapView.
export const ZOOM_MIN = 0.4;
export const ZOOM_MAX = 6;
export const ZOOM_WHEEL_FACTOR = 1.18;
export const ZOOM_BUTTON_FACTOR = 1.25;

// Period auto-play cadence. Tuned so a 30-period horizon takes ~60s to play
// through; faster feels jumpy on the map, slower is boring during demos.
export const PLAYBACK_INTERVAL_MS = 2200;

// Stress lens — flow ratios vs. baseline period.
export const STRESS_CRITICAL_RATIO = 0.65;
export const STRESS_WARNING_RATIO = 0.9;

// Storage lens — endingStorage / capacity.
export const STORAGE_CRITICAL_RATIO = 0.18;
export const STORAGE_WARNING_RATIO = 0.4;

// Sector delivery thresholds (delivered / target) for non-storage sectors —
// drinking water, irrigation, hydropower, flow.
export const DELIVERY_CRITICAL_RATIO = 0.75;
export const DELIVERY_WARNING_RATIO = 0.97;

// Lens palette — keep in sync with CSS custom properties --red/--yellow/--green.
export const COLOR_CRITICAL = "#d4483c";
export const COLOR_WARNING = "#d89b24";
export const COLOR_OK = "#20a66a";
