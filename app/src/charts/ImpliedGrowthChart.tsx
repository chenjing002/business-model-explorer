import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { toPercent, yearOf } from "../data";
import type { ValuationRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette } from "./theme";

const CALCULATIONS = ["implied_g_reoi", "implied_g_rnoa", "implied_g_fcf", "implied_g_equity"];

/** Perpetual growth implied by the year-end price at the assumed rates (%).
 *  Undefined solutions (non-positive anchor) arrive as null and draw gaps. */
export function ImpliedGrowthChart({ rows: input }: { rows: ValuationRow[] }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...input].sort((a, b) => a.end_date.localeCompare(b.end_date));
    const g = rows.find((r) => r.g_assumed != null)?.g_assumed ?? null;
    return {
      textStyle: baseTextStyle,
      grid: { ...baseGrid, top: 54 },
      tooltip: {
        trigger: "axis",
        formatter: (params) => {
          const items = params as { dataIndex: number; seriesName: string; value: number | null; marker: string }[];
          const r = rows[items[0].dataIndex];
          const pct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(2)}%`);
          const lines = items.map((p) => `${p.marker}${p.seriesName}: <b>${p.value == null ? "—" : `${p.value.toFixed(2)}%`}</b>`);
          lines.unshift(`<b>${yearOf(r.end_date)}</b>`);
          lines.push(`隐含经营必要报酬率，g＝ ${pct(r.g_assumed)}: <b>${pct(r.implied_r_op)}</b>`);
          lines.push(`隐含权益必要报酬率，g＝ ${pct(r.g_assumed)}: <b>${pct(r.implied_r_e)}</b>`);
          return lines.join("<br/>");
        },
      },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "%", ...axisStyle() },
      series: [
        {
          name: "剩余经营收益基数", type: "line", data: rows.map((r) => toPercent(r.implied_g_reoi)), color: palette.operating, symbolSize: 8, lineStyle: { width: 2 },
          markLine: g == null ? undefined : {
            silent: true, symbol: "none",
            lineStyle: { color: palette.muted, type: "dotted" },
            label: { formatter: `假设 g＝${(g * 100).toFixed(1)}%`, position: "insideEndTop", color: palette.muted, fontSize: 10 },
            data: [{ yAxis: g * 100 }],
          },
        },
        { name: "经营回报率基数", type: "line", data: rows.map((r) => toPercent(r.implied_g_rnoa)), color: palette.financing, symbolSize: 8, lineStyle: { width: 2 } },
        { name: "自由现金流基数（反向DCF）", type: "line", data: rows.map((r) => toPercent(r.implied_g_fcf)), color: palette.warn, symbolSize: 8, lineStyle: { width: 2 } },
        { name: "剩余权益收益（RE）", type: "line", data: rows.map((r) => toPercent(r.implied_g_equity)), color: palette.accent, symbolSize: 8, lineStyle: { width: 2 } },
      ],
    };
  }, [input]);
  return <div ref={useECharts(option, CALCULATIONS)} className="chart" />;
}
