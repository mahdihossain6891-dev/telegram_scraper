"use client";

import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

import { useTheme } from "@/components/theme/ThemeProvider";
import { withThemeColors } from "@/lib/charts";

type EChartProps = {
  option: EChartsOption;
  height?: number;
  className?: string;
  ariaLabel?: string;
};

export function EChart({
  option,
  height = 300,
  className = "",
  ariaLabel = "Chart",
}: EChartProps) {
  const { theme } = useTheme();
  const themed = withThemeColors(option, theme);

  return (
    <div
      className={`chart-wrap ${className}`.trim()}
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
    >
      <ReactECharts
        key={theme}
        option={themed}
        notMerge
        lazyUpdate
        style={{ height: "100%", width: "100%" }}
        opts={{ renderer: "canvas" }}
      />
    </div>
  );
}
