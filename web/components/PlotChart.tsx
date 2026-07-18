"use client";

import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";
import type { PlotParams } from "react-plotly.js";

const Plot = createPlotlyComponent(Plotly);

const darkLayout = {
  template: "plotly_dark" as const,
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { color: "#e5eefb", family: "Fira Sans, sans-serif", size: 12 },
  margin: { t: 40, r: 12, b: 40, l: 44 },
  colorway: ["#3B82F6", "#D97706", "#DC2626", "#16A34A", "#60A5FA", "#F59E0B"],
};

type SimpleLayout = {
  title?: string;
  barmode?: "stack" | "group" | "relative" | "overlay";
  height?: number;
  xaxis?: { title?: string };
  yaxis?: { title?: string };
};

function buildLayout(layout?: SimpleLayout): PlotParams["layout"] {
  const axisTitle = (value?: string) => (value ? { title: { text: value } } : undefined);

  return {
    ...darkLayout,
    ...(layout?.barmode ? { barmode: layout.barmode } : {}),
    ...(layout?.height ? { height: layout.height } : {}),
    ...(layout?.title ? { title: { text: layout.title } } : {}),
    ...(layout?.xaxis?.title ? { xaxis: axisTitle(layout.xaxis.title) } : {}),
    ...(layout?.yaxis?.title ? { yaxis: axisTitle(layout.yaxis.title) } : {}),
  };
}

export function PlotChart({
  layout,
  ...props
}: Omit<PlotParams, "layout"> & { layout?: SimpleLayout }) {
  return (
    <div className="chart-wrap">
      <Plot
        {...props}
        useResizeHandler
        style={{ width: "100%", height: "100%" }}
        config={{ displayModeBar: false, responsive: true }}
        layout={buildLayout(layout)}
      />
    </div>
  );
}
