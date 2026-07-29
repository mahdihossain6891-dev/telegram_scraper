import type { EChartsOption } from "echarts";

import { CHART_COLORS, chartBase } from "@/lib/charts";

export function distributionBarOption(dist: Record<string, number>): EChartsOption {
  const order = ["Normal", "Unusual", "Suspicious", "High Risk"];
  const colors = [
    CHART_COLORS.low,
    CHART_COLORS.medium,
    CHART_COLORS.high,
    CHART_COLORS.critical,
  ];
  return {
    ...chartBase(220),
    grid: { left: 48, right: 16, top: 24, bottom: 36 },
    xAxis: {
      type: "category",
      data: order,
      axisLabel: { color: CHART_COLORS.muted },
      axisLine: { lineStyle: { color: CHART_COLORS.axis } },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      splitLine: { lineStyle: { color: CHART_COLORS.grid } },
      axisLabel: { color: CHART_COLORS.muted },
    },
    series: [
      {
        type: "bar",
        data: order.map((k, i) => ({
          value: dist[k] || 0,
          itemStyle: { color: colors[i], borderRadius: [6, 6, 0, 0] },
        })),
        barWidth: 36,
      },
    ],
  };
}

export function postingLineOption(
  series: Array<{ date: string; messages: number }>,
): EChartsOption {
  return {
    ...chartBase(),
    xAxis: {
      type: "category",
      data: series.map((p) => p.date),
      axisLabel: { color: CHART_COLORS.muted, rotate: series.length > 14 ? 35 : 0 },
      axisLine: { lineStyle: { color: CHART_COLORS.axis } },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: CHART_COLORS.grid } },
      axisLabel: { color: CHART_COLORS.muted },
    },
    series: [
      {
        type: "line",
        smooth: true,
        data: series.map((p) => p.messages),
        lineStyle: { width: 3, color: CHART_COLORS.primary },
        itemStyle: { color: CHART_COLORS.primary },
        areaStyle: { color: CHART_COLORS.fill },
        symbolSize: 5,
      },
    ],
  };
}

export function hourlyBarOption(
  series: Array<{ hour: number; messages: number }>,
): EChartsOption {
  return {
    ...chartBase(),
    xAxis: {
      type: "category",
      data: series.map((p) => `${String(p.hour).padStart(2, "0")}:00`),
      axisLabel: { color: CHART_COLORS.muted, interval: 3 },
      axisLine: { lineStyle: { color: CHART_COLORS.axis } },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: CHART_COLORS.grid } },
      axisLabel: { color: CHART_COLORS.muted },
    },
    series: [
      {
        type: "bar",
        data: series.map((p) => p.messages),
        itemStyle: { color: CHART_COLORS.secondary, borderRadius: [4, 4, 0, 0] },
        barWidth: 10,
      },
    ],
  };
}

export function mediaPieOption(media: Record<string, number>): EChartsOption {
  const data = Object.entries(media).map(([name, value]) => ({ name, value }));
  return {
    ...chartBase(280),
    tooltip: { trigger: "item" },
    legend: {
      bottom: 0,
      textStyle: { color: CHART_COLORS.muted, fontSize: 11 },
    },
    series: [
      {
        type: "pie",
        radius: ["42%", "68%"],
        center: ["50%", "45%"],
        data,
        label: { color: "#374151", fontSize: 11 },
      },
    ],
  };
}

export function languageBarOption(dist: Record<string, number>): EChartsOption {
  const entries = Object.entries(dist).sort((a, b) => b[1] - a[1]).slice(0, 8);
  return {
    ...chartBase(240),
    grid: { left: 80, right: 24, top: 16, bottom: 28 },
    xAxis: {
      type: "value",
      axisLabel: { color: CHART_COLORS.muted, formatter: "{value}%" },
      splitLine: { lineStyle: { color: CHART_COLORS.grid } },
    },
    yAxis: {
      type: "category",
      data: entries.map(([k]) => k).reverse(),
      axisLabel: { color: CHART_COLORS.muted },
    },
    series: [
      {
        type: "bar",
        data: entries.map(([, v]) => v).reverse(),
        itemStyle: { color: CHART_COLORS.primary, borderRadius: [0, 4, 4, 0] },
        barWidth: 14,
      },
    ],
  };
}

export function heatmapOption(
  cells: Array<{ weekday: string; hour: number; messages: number }>,
): EChartsOption {
  const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const data = cells.map((c) => [
    c.hour,
    weekdays.indexOf(c.weekday),
    c.messages,
  ]);
  const max = Math.max(1, ...cells.map((c) => c.messages));
  return {
    ...chartBase(280),
    tooltip: {
      position: "top",
      formatter: (params: unknown) => {
        const p = params as { value?: number[] };
        const v = p.value || [];
        return `${weekdays[v[1] as number] || "?"} ${String(v[0]).padStart(2, "0")}:00 — ${v[2]} msgs`;
      },
    },
    grid: { left: 48, right: 24, top: 16, bottom: 48 },
    xAxis: {
      type: "category",
      data: hours.map((h) => String(h).padStart(2, "0")),
      splitArea: { show: true },
      axisLabel: { color: CHART_COLORS.muted, interval: 2 },
    },
    yAxis: {
      type: "category",
      data: weekdays,
      axisLabel: { color: CHART_COLORS.muted },
    },
    visualMap: {
      min: 0,
      max,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: ["#EEF2FF", CHART_COLORS.soft, CHART_COLORS.primary] },
      textStyle: { color: CHART_COLORS.muted, fontSize: 11 },
    },
    series: [
      {
        type: "heatmap",
        data,
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.15)" } },
      },
    ],
  };
}

export function scoreTrendOption(history: Array<{ time?: string | null; title: string }>): EChartsOption {
  // Approximate trend from timeline length (score snapshots aren't stored per event)
  const labels = history.slice(-12).map((h) => (h.time || "").slice(0, 10) || h.title);
  const values = history.slice(-12).map((_, i) => i + 1);
  return {
    ...chartBase(200),
    xAxis: {
      type: "category",
      data: labels,
      axisLabel: { color: CHART_COLORS.muted, rotate: 30 },
    },
    yAxis: {
      type: "value",
      name: "Events",
      splitLine: { lineStyle: { color: CHART_COLORS.grid } },
      axisLabel: { color: CHART_COLORS.muted },
    },
    series: [
      {
        type: "line",
        data: values,
        smooth: true,
        lineStyle: { color: CHART_COLORS.high },
        itemStyle: { color: CHART_COLORS.high },
        areaStyle: { color: "rgba(249, 115, 22, 0.12)" },
      },
    ],
  };
}

export function statusClass(status?: string): string {
  switch (status) {
    case "High Risk":
      return "ba-status ba-status-critical";
    case "Suspicious":
      return "ba-status ba-status-high";
    case "Unusual":
      return "ba-status ba-status-medium";
    default:
      return "ba-status ba-status-low";
  }
}
