import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { formatYiValue } from "../format";
import { toYiYuan, yearOf } from "../data";
import type { ValuationRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette } from "./theme";

const CALCULATIONS = ["forward_pe_market", "forward_pe_model", "trailing_pe", "normal_pe"];
const EXTRA = ["aeg_actual", "cum_div_growth"];

/** Forward P/E (market and model) vs the normal P/E 1/r_e: a market P/E
 *  above normal prices positive abnormal earnings growth (AEG). Actual
 *  historical AEG is in the tooltip (亿元; no second axis). */
export function PeChart({ rows: input }: { rows: ValuationRow[] }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...input].sort((a, b) => a.end_date.localeCompare(b.end_date));
    return {
      textStyle: baseTextStyle,
      grid: { ...baseGrid, top: 54 },
      tooltip: {
        trigger: "axis",
        formatter: (params) => {
          const items = params as { dataIndex: number; seriesName: string; value: number | null; marker: string }[];
          const r = rows[items[0].dataIndex];
          const lines = items.map((p) => `${p.marker}${p.seriesName}: <b>${p.value == null ? "—" : p.value.toFixed(1)}</b>`);
          lines.unshift(`<b>${yearOf(r.end_date)}</b>`);
          const aeg = toYiYuan(r.aeg_actual);
          lines.push(`本年实际异常盈余增长： <b>${formatYiValue(aeg, 2)}</b>`);
          lines.push(`含净分配的盈余增长率： <b>${r.cum_div_growth == null ? "—" : `${(r.cum_div_growth * 100).toFixed(1)}%`}</b>；r_e＝${(r.r_e_assumed * 100).toFixed(1)}%`);
          return lines.join("<br/>");
        },
      },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "倍", ...axisStyle() },
      series: [
        { name: "市场前瞻收益倍数", type: "line", data: rows.map((r) => r.forward_pe_market), color: palette.operating, symbolSize: 8, lineStyle: { width: 2 } },
        { name: "模型前瞻收益倍数", type: "line", data: rows.map((r) => r.forward_pe_model), color: palette.financing, symbolSize: 8, lineStyle: { type: "dashed", width: 2 } },
        { name: "同年归母净利润口径市盈率", type: "line", data: rows.map((r) => r.trailing_pe), color: palette.warn, symbolSize: 8, lineStyle: { width: 2 } },
        { name: "正常市盈率（1／r_e）", type: "line", data: rows.map((r) => r.normal_pe), color: palette.equity, symbol: "none", lineStyle: { type: "dotted", width: 1.5 } },
      ],
    };
  }, [input]);
  return <div ref={useECharts(option, CALCULATIONS, EXTRA)} className="chart" />;
}
