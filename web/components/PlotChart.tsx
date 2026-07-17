"use client";

import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";
import type { PlotParams } from "react-plotly.js";

const Plot = createPlotlyComponent(Plotly);

const darkLayout = {
  template: "plotly_dark" as const,
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { color: "#e5eefb" },
  margin: { t: 48, r: 16, b: 48, l: 48 },
};

export function PlotChart({ layout, ...props }: PlotParams) {
  return (
    <div className="chart-wrap">
      <Plot
        {...props}
        useResizeHandler
        style={{ width: "100%", height: "100%" }}
        config={{ displayModeBar: false, responsive: true }}
        layout={{ ...darkLayout, ...layout }}
      />
    </div>
  );
}
