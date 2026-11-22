import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { formatYiValue } from "../format";
import { waterfallBars } from "../data";
import type { CashBridgeStep } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseTextStyle, palette } from "./theme";

/** True NI → CFO waterfall from reported indirect-method steps.
 *  Bars absent in the source are simply not drawn (no invented zeros). */
export function WaterfallChart({ steps, table = "cash_bridge" }: {
  steps: CashBridgeStep[]; table?: "cash_bridge" | "capital_bridge" | "valuation_bridge" | "value_bridge";
}) {
  const ordered = useMemo(() => [...steps].sort((a, b) => a.step_order - b.step_order), [steps]);
  const option = useMemo<EChartsOption>(() => {
    const bars = waterfallBars(steps);
    const color = (b: (typeof bars)[number]) =>
      b.kind !== "adjustment"
        ? palette.equity
        : b.span >= 0
          ? palette.operating
          : palette.negative;
    return {
      textStyle: baseTextStyle,
      grid: { left: 56, right: 16, top: 12, bottom: 110 },
      tooltip: {
        trigger: "axis",
        formatter: (params) => {
          const p = (params as { dataIndex: number }[])[1];
          const b = bars[p.dataIndex];
          return `${b.label}<br/><b>${b.span >= 0 ? "+" : ""}${formatYiValue(b.span)}</b>`;
        },
      },
      xAxis: {
        type: "category",
        data: bars.map((b) => b.label),
        ...axisStyle(),
        axisLabel: { color: palette.muted, fontSize: 10, rotate: 42, width: 110, overflow: "truncate" as const },
      },
      yAxis: { type: "value", name: "亿元", ...axisStyle() },
      series: [
        { name: "辅助底座", type: "bar", stack: "wf", itemStyle: { color: "transparent" }, emphasis: { itemStyle: { color: "transparent" } }, data: bars.map((b) => b.base), silent: true },
        { name: "金额", type: "bar", stack: "wf", data: bars.map((b) => ({ value: Math.abs(b.span), itemStyle: { color: color(b) } })), barWidth: "55%" },
      ],
    };
  }, [steps]);
  return <div ref={useECharts(option, (point) => {
    const row = ordered[point.dataIndex];
    return point.seriesIndex === 1 && row ? { date: row.end_date, code: `${table}:${row.concept}` } : undefined;
  })} className="chart chart--tall" />;
}
