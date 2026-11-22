/** Restrained shared chart styling. Visual conventions:
 *  stocks (balances) render as bars, flows/returns as lines,
 *  calculated series dashed, reported solid.
 */
import type * as echarts from "echarts";

export const palette = {
  ink: "#1f2430",
  muted: "#6b7280",
  grid: "#e5e7eb",
  operating: "#1d4ed8",
  financing: "#0d9488",
  equity: "#334155",
  warn: "#b45309",
  accent: "#7c3aed", // 4th categorical slot (validated: blue, teal, amber, purple)
  negative: "#b91c1c",
  neutral: "#9ca3af",
};

export const baseGrid: echarts.GridComponentOption = {
  left: 56,
  right: 16,
  top: 52,
  bottom: 28,
};

export const baseTextStyle = {
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  color: palette.ink,
};

export function axisStyle(): Record<string, unknown> {
  return {
    axisLine: { lineStyle: { color: palette.grid } },
    axisTick: { show: false },
    axisLabel: { color: palette.muted, fontSize: 12 },
    splitLine: { lineStyle: { color: palette.grid, type: "dashed" as const } },
  };
}

export function selectedYearLine(year?: string) {
  return year ? {
    silent: true,
    symbol: "none",
    label: { show: false },
    lineStyle: { color: palette.neutral, type: "dashed" as const },
    data: [{ xAxis: year }],
  } : undefined;
}
