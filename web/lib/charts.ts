import type { EChartsOption } from "echarts";

import type { MessageDisplayRow } from "./types";

export type ChartTheme = "dark" | "light";

export const CHART_COLORS = {
  primary: "#8B5CF6",
  secondary: "#6366F1",
  soft: "#C4B5FD",
  fill: "rgba(139, 92, 246, 0.18)",
  muted: "#94A3B8",
  grid: "rgba(148, 163, 184, 0.12)",
  axis: "rgba(148, 163, 184, 0.25)",
  low: "#10B981",
  medium: "#F59E0B",
  high: "#F97316",
  critical: "#EF4444",
  narcotics: "#8B5CF6",
  trafficking: "#6366F1",
  firearms: "#C4B5FD",
  tooltipBg: "#1A1A28",
  tooltipFg: "#F1F5F9",
};

function readCssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** Resolve chart palette from CSS tokens (theme-aware). */
export function resolveChartColors(theme?: ChartTheme) {
  const isDark =
    theme === "dark" ||
    (theme !== "light" &&
      typeof document !== "undefined" &&
      document.documentElement.getAttribute("data-theme") === "dark");

  if (typeof window === "undefined") {
    return { ...CHART_COLORS };
  }

  return {
    primary: readCssVar("--color-primary", CHART_COLORS.primary),
    secondary: readCssVar("--color-secondary", CHART_COLORS.secondary),
    soft: CHART_COLORS.soft,
    fill: isDark ? "rgba(139, 92, 246, 0.22)" : "rgba(124, 58, 237, 0.14)",
    muted: readCssVar("--color-muted", CHART_COLORS.muted),
    grid: readCssVar("--color-chart-grid", CHART_COLORS.grid),
    axis: readCssVar("--color-chart-axis", CHART_COLORS.axis),
    low: readCssVar("--color-success", CHART_COLORS.low),
    medium: readCssVar("--color-warning", CHART_COLORS.medium),
    high: readCssVar("--color-high", CHART_COLORS.high),
    critical: readCssVar("--color-destructive", CHART_COLORS.critical),
    narcotics: readCssVar("--color-primary", CHART_COLORS.narcotics),
    trafficking: readCssVar("--color-secondary", CHART_COLORS.trafficking),
    firearms: CHART_COLORS.firearms,
    tooltipBg: readCssVar("--color-chart-tooltip-bg", isDark ? "#1A1A28" : "#ffffff"),
    tooltipFg: readCssVar("--color-chart-tooltip-fg", isDark ? "#F1F5F9" : "#0F172A"),
  };
}

const baseText = {
  color: CHART_COLORS.muted,
  fontFamily: "Inter, Plus Jakarta Sans, sans-serif",
  fontSize: 12,
};

export function chartBase(heightHint = 300): Partial<EChartsOption> {
  const c = resolveChartColors();
  return {
    color: [c.primary, c.secondary, c.soft, c.medium],
    textStyle: { ...baseText, color: c.muted },
    grid: { left: 48, right: 16, top: 36, bottom: 36, containLabel: false },
    tooltip: {
      trigger: "axis",
      backgroundColor: c.tooltipBg,
      borderColor: c.axis,
      textStyle: { color: c.tooltipFg, fontSize: 12 },
    },
    animationDuration: heightHint > 0 ? 400 : 0,
  };
}

/** Re-apply theme colors onto an existing option (for ThreatChart). */
export function withThemeColors(option: EChartsOption, theme?: ChartTheme): EChartsOption {
  const c = resolveChartColors(theme);
  return {
    ...option,
    color: [c.primary, c.secondary, c.soft, c.medium],
    textStyle: { ...(option.textStyle || {}), color: c.muted, fontFamily: baseText.fontFamily },
    tooltip: {
      ...(typeof option.tooltip === "object" && !Array.isArray(option.tooltip)
        ? option.tooltip
        : {}),
      backgroundColor: c.tooltipBg,
      borderColor: c.axis,
      textStyle: { color: c.tooltipFg, fontSize: 12 },
    },
  };
}

export function areaTimelineOption(
  points: Array<{ date: string; messages: number }>,
): EChartsOption {
  const c = resolveChartColors();
  return {
    ...chartBase(),
    xAxis: {
      type: "category",
      data: points.map((p) => p.date),
      axisLine: { lineStyle: { color: c.axis } },
      axisLabel: { color: c.muted },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: c.grid } },
      axisLabel: { color: c.muted },
    },
    series: [
      {
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        data: points.map((p) => p.messages),
        lineStyle: { width: 3, color: c.primary },
        itemStyle: { color: c.primary },
        areaStyle: { color: c.fill },
      },
    ],
  };
}

export function barHourlyOption(
  points: Array<{ hour: string; messages: number }>,
): EChartsOption {
  const c = resolveChartColors();
  return {
    ...chartBase(),
    xAxis: {
      type: "category",
      data: points.map((p) => p.hour),
      axisLabel: { color: c.muted },
      axisLine: { lineStyle: { color: c.axis } },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: c.grid } },
      axisLabel: { color: c.muted },
    },
    series: [
      {
        type: "bar",
        data: points.map((p) => p.messages),
        itemStyle: { color: c.primary, borderRadius: [6, 6, 0, 0] },
        barMaxWidth: 28,
      },
    ],
  };
}

export function heatmapOption(input: {
  days: string[];
  hours: string[];
  matrix: number[][];
}): EChartsOption {
  const c = resolveChartColors();
  const data: Array<[number, number, number]> = [];
  input.matrix.forEach((row, y) => {
    row.forEach((value, x) => {
      data.push([x, y, value]);
    });
  });
  const max = Math.max(1, ...data.map((d) => d[2]));
  return {
    ...chartBase(),
    tooltip: {
      position: "top",
      backgroundColor: c.tooltipBg,
      borderColor: c.axis,
      textStyle: { color: c.tooltipFg, fontSize: 12 },
      formatter: (params: unknown) => {
        const p = params as { value?: number[] };
        const v = p.value || [0, 0, 0];
        return `${input.days[v[1]]} ${input.hours[v[0]]}:00<br/><b>${v[2]}</b> msgs`;
      },
    },
    grid: { left: 48, right: 16, top: 16, bottom: 40 },
    xAxis: {
      type: "category",
      data: input.hours,
      splitArea: { show: true },
      axisLabel: { color: c.muted },
    },
    yAxis: {
      type: "category",
      data: input.days,
      axisLabel: { color: c.muted },
    },
    visualMap: {
      min: 0,
      max,
      calculable: false,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: ["#2e1065", "#7c3aed", "#a78bfa", "#c4b5fd"] },
      textStyle: { color: c.muted },
    },
    series: [
      {
        type: "heatmap",
        data,
        label: { show: false },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.25)" } },
      },
    ],
  };
}

export function donutSeverityOption(
  levels: Record<string, number>,
): EChartsOption {
  const c = resolveChartColors();
  const order = ["Critical", "High", "Medium", "Low"] as const;
  const colors = [c.critical, c.high, c.medium, c.low];
  return {
    ...chartBase(),
    tooltip: {
      trigger: "item",
      backgroundColor: c.tooltipBg,
      borderColor: c.axis,
      textStyle: { color: c.tooltipFg, fontSize: 12 },
    },
    legend: {
      bottom: 0,
      textStyle: { color: c.muted },
    },
    series: [
      {
        type: "pie",
        radius: ["48%", "72%"],
        center: ["50%", "46%"],
        avoidLabelOverlap: true,
        label: { show: false },
        data: order.map((name, i) => ({
          name,
          value: levels[name] || 0,
          itemStyle: { color: colors[i] },
        })),
      },
    ],
  };
}

export function horizontalKeywordsOption(
  rows: Array<{ term: string; category: string; count: number }>,
): EChartsOption {
  const c = resolveChartColors();
  const ordered = rows.slice().reverse();
  return {
    ...chartBase(),
    grid: { left: 120, right: 24, top: 16, bottom: 24 },
    xAxis: {
      type: "value",
      splitLine: { lineStyle: { color: c.grid } },
      axisLabel: { color: c.muted },
    },
    yAxis: {
      type: "category",
      data: ordered.map((r) => r.term),
      axisLabel: { color: c.muted, width: 100, overflow: "truncate" },
    },
    series: [
      {
        type: "bar",
        data: ordered.map((r) => r.count),
        itemStyle: { color: c.primary, borderRadius: [0, 6, 6, 0] },
        barMaxWidth: 18,
      },
    ],
  };
}

export function stackedCategoryBySourceOption(
  rows: Array<{
    source_type: string;
    narcotics: number;
    human_trafficking: number;
    firearms: number;
  }>,
): EChartsOption {
  const c = resolveChartColors();
  return {
    ...chartBase(),
    legend: {
      top: 0,
      textStyle: { color: c.muted },
    },
    grid: { left: 48, right: 16, top: 40, bottom: 36 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: c.tooltipBg,
      borderColor: c.axis,
      textStyle: { color: c.tooltipFg, fontSize: 12 },
    },
    xAxis: {
      type: "category",
      data: rows.map((r) => r.source_type),
      axisLabel: { color: c.muted },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: c.grid } },
      axisLabel: { color: c.muted },
    },
    series: [
      {
        name: "Narcotics",
        type: "bar",
        stack: "cat",
        data: rows.map((r) => r.narcotics),
        itemStyle: { color: c.narcotics },
      },
      {
        name: "Trafficking",
        type: "bar",
        stack: "cat",
        data: rows.map((r) => r.human_trafficking),
        itemStyle: { color: c.trafficking },
      },
      {
        name: "Firearms",
        type: "bar",
        stack: "cat",
        data: rows.map((r) => r.firearms),
        itemStyle: { color: c.firearms },
      },
    ],
  };
}

export function categoryBarOption(
  rows: Array<{ category: string; count: number }>,
): EChartsOption {
  const c = resolveChartColors();
  return {
    ...chartBase(),
    xAxis: {
      type: "category",
      data: rows.map((r) => r.category.replace(/_/g, " ")),
      axisLabel: { color: c.muted },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: c.grid } },
      axisLabel: { color: c.muted },
    },
    series: [
      {
        type: "bar",
        data: rows.map((r) => r.count),
        itemStyle: { color: c.primary, borderRadius: [6, 6, 0, 0] },
        barMaxWidth: 40,
      },
    ],
  };
}

/** Day × 2-hour bucket activity matrix for heatmaps. */
export function peakActivityHeatmap(messages: MessageDisplayRow[]) {
  const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const hours = Array.from({ length: 12 }, (_, i) => `${String(i * 2).padStart(2, "0")}`);
  const matrix = days.map(() => hours.map(() => 0));
  for (const row of messages) {
    if (!row.timestamp || row.timestamp.length < 13) continue;
    const date = new Date(row.timestamp);
    if (Number.isNaN(date.getTime())) continue;
    matrix[date.getDay()][Math.floor(date.getHours() / 2)] += 1;
  }
  return { days, hours, matrix };
}
