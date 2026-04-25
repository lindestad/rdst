// plotly.js-dist-min ships no types; we use it only as the engine passed to
// react-plotly.js/factory, which accepts `any`. Keep the shim until we need
// a full Plotly typing surface.
declare module "plotly.js-dist-min";
