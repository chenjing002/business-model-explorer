import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { toPercent, yearOf } from "../data";
import type { ResidualIncomeRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette } from "./theme";

const CALCULATIONS = ["spread_op", "spread_e"];

/** Spreads over the assumed required returns (opening capital, %).
 *  Suppressed bases arrive as null and draw gaps. */
export function SpreadChart({ rows: input }: { rows: ResidualIncomeRow[] }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...input].sort((a, b) => a.end_date.localeCompare(b.end_date));
    return {
      textStyle: baseTextStyle,
      grid: baseGrid,
      tooltip: { trigger: "axis", valueFormatter: (v) => (v == null ? "—" : `${(v as number).toFixed(1)} 个百分点`) },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "百分点", ...axisStyle() },
      series: [
        { name: "经营收益率减必要报酬率", type: "line", data: rows.map((r) => toPercent(r.spread_op)), color: palette.operating, symbolSize: 5 },
        { name: "归母收益率减必要报酬率", type: "line", data: rows.map((r) => toPercent(r.spread_e)), color: palette.financing, symbolSize: 5 },
      ],
    };
  }, [input]);
  return <div ref={useECharts(option, CALCULATIONS)} className="chart" />;
}
