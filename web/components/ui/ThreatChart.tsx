"use client";

import type { EChartsOption } from "echarts";

import { EChart } from "@/components/EChart";
import { useTheme } from "@/components/theme/ThemeProvider";
import { withThemeColors } from "@/lib/charts";

type ThreatChartProps = {
  option: EChartsOption;
  height?: number;
  className?: string;
  ariaLabel?: string;
};

/** Theme-aware EChart wrapper for SOC surfaces. */
export function ThreatChart({
  option,
  height = 280,
  className = "",
  ariaLabel = "Threat chart",
}: ThreatChartProps) {
  const { theme } = useTheme();
  const themed = withThemeColors(option, theme);
  return (
    <EChart
      option={themed}
      height={height}
      className={`threat-chart ${className}`.trim()}
      ariaLabel={ariaLabel}
    />
  );
}
