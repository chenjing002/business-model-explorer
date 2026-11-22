import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { formatYiValue, formatResidual } from "../format";
import { toYiYuan, yearOf } from "../data";
import type { CapitalSummaryRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette } from "./theme";

const CALCULATIONS = ["fcf_simple", "fcf_from_oi"];
const EXTRA = ["fcf_articulation_diff"];

/** Two FCF measures: cash-statement fcf_simple (reported lines, solid) vs
 *  Penman fcf_from_oi = OI − ΔNOA (calculated, dashed). The gap is the
 *  articulation difference — expected, reported, never forced to zero. */
export function FcfChart({ summary }: { summary: CapitalSummaryRow[] }) {
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
          const d = r.fcf_articulation_diff;
          lines.push(`勾稽差额： <b>${d == null ? "—" : formatResidual(d)}</b>`);
          return lines.join("<br/>");
        },
      },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "亿元", ...axisStyle() },
      series: [
        { name: "简式自由现金流（CFO－资本开支）", type: "line", data: rows.map((r) => toYiYuan(r.fcf_simple)), color: palette.operating, symbolSize: 5 },
        { name: "重构自由现金流（OI－ΔNOA）", type: "line", data: rows.map((r) => toYiYuan(r.fcf_from_oi)), color: palette.warn, symbolSize: 5, lineStyle: { type: "dashed" } },
      ],
    };
  }, [summary]);
  return <div ref={useECharts(option, CALCULATIONS, EXTRA)} className="chart" />;
}
