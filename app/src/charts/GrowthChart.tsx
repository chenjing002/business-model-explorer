import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { toPercent, yearOf } from "../data";
import type { CapitalSummaryRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette } from "./theme";

const CALCULATIONS = ["revenue_growth", "noa_growth", "reinvestment_rate"];

/** Revenue growth vs NOA growth vs reinvestment rate (%, all precomputed).
 *  Suppressed/first-year values arrive as null and draw gaps. */
export function GrowthChart({ summary }: { summary: CapitalSummaryRow[] }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...summary].sort((a, b) => a.end_date.localeCompare(b.end_date));
    return {
      textStyle: baseTextStyle,
      grid: baseGrid,
      tooltip: { trigger: "axis", valueFormatter: (v) => (v == null ? "—" : `${(v as number).toFixed(1)}%`) },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "%", ...axisStyle() },
      series: [
        { name: "营业总收入增长率", type: "line", data: rows.map((r) => toPercent(r.revenue_growth)), color: palette.operating, symbolSize: 5 },
        { name: "净经营资产增长率", type: "line", data: rows.map((r) => toPercent(r.noa_growth)), color: palette.financing, symbolSize: 5 },
        { name: "再投资率（ΔNOA／OI）", type: "line", data: rows.map((r) => toPercent(r.reinvestment_rate)), color: palette.warn, symbolSize: 5, lineStyle: { type: "dashed" } },
      ],
    };
  }, [summary]);
  return <div ref={useECharts(option, CALCULATIONS)} className="chart" />;
}
