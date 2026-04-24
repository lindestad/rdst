import createPlotComponent from "react-plotly.js/factory";
// plotly.js-dist-min is the bundle we install directly. react-plotly.js's
// default entry point imports `plotly.js` (the meta-package) which we don't
// ship — so build the component via the factory instead.
import Plotly from "plotly.js-dist-min";

const Plot = createPlotComponent(Plotly as any);

export function KpiChart({
  x, y, color, unit,
}: {
  x: string[];
  y: number[];
  color: string;
  unit: string;
}) {
  return (
    <Plot
      data={[
        { x, y, type: "scatter", mode: "lines", line: { color, width: 2 } } as any,
      ]}
      layout={{
        autosize: true,
        height: 100,
        margin: { l: 30, r: 8, t: 8, b: 24 },
        xaxis: {
          showgrid: false,
          tickfont: { size: 9, color: "#94a3b8" },
        },
        yaxis: {
          title: { text: unit, font: { size: 9, color: "#94a3b8" } },
          tickfont: { size: 9, color: "#94a3b8" },
        },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
      }}
      config={{ displayModeBar: false }}
      style={{ width: "100%" }}
    />
  );
}
