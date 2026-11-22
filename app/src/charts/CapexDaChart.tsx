import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { formatYiValue } from "../format";
import { toYiYuan, yearOf } from "../data";
import type { CapitalSummaryRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette } from "./theme";

const CALCULATIONS = ["raw:capex_paid", "da_total"];
const EXTRA = ["capex_to_da"];

/** Cash capex vs disclosed D&A (亿元, one axis). The precomputed capex/D&A
 *  ratio is surfaced in the tooltip — no frontend math. */
export function CapexDaChart({ summary }: { summary: CapitalSummaryRow[] }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...summary].sort((a, b) => a.end_date.localeCompare(b.end_date));
    return {
      textStyle: baseTextStyle,
      grid: baseGrid,
      tooltip: {
        trigger: "axis",
        formatter: (params) => {
          const items = params as { dataIndex: number; seriesName: string; value: number | null; marker: string }[];
          const r = rows[items[0].dataIndex];
          const lines = items.map((p) => `${p.marker}${p.seriesName}: <b>${formatYiValue(p.value, 2)}</b>`);
          lines.unshift(`<b>${yearOf(r.end_date)}</b>`);
          lines.push(`资本开支／折旧摊销： <b>${r.capex_to_da == null ? "—" : `${r.capex_to_da.toFixed(2)}×`}</b>`);
          return lines.join("<br/>");
        },
      },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "亿元", ...axisStyle() },
      series: [
        { name: "现金资本开支", type: "bar", data: rows.map((r) => toYiYuan(r.capex_paid)), color: palette.operating, barGap: "10%" },
        { name: "折旧摊销（披露）", type: "bar", data: rows.map((r) => toYiYuan(r.da_total)), color: palette.financing },
      ],
    };
  }, [summary]);
  return <div ref={useECharts(option, CALCULATIONS, EXTRA)} className="chart" />;
}
