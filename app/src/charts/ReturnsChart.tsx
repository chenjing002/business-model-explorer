import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { toPercent, yearOf } from "../data";
import type { RatioRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette, selectedYearLine } from "./theme";

const CALCULATIONS = ["rnoa", "rotce_direct", "roce_parent"];

/** RNOA vs ROTCE vs parent ROCE (%, average-capital basis). */
export function ReturnsChart({ ratios, year }: { ratios: RatioRow[]; year?: string }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = ratios
      .filter((r) => r.basis === "average")
      .sort((a, b) => a.end_date.localeCompare(b.end_date));
    return {
      textStyle: baseTextStyle,
      grid: baseGrid,
      tooltip: { trigger: "axis", valueFormatter: (v) => (v == null ? "—" : `${(v as number).toFixed(1)}%`) },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "%", ...axisStyle() },
      series: [
        { name: "经营收益率（RNOA）", type: "line", data: rows.map((r) => toPercent(r.rnoa)), color: palette.operating, symbolSize: 5, markLine: selectedYearLine(year) },
        { name: "合并权益收益率（含少数股东）", type: "line", data: rows.map((r) => toPercent(r.rotce_direct)), color: palette.financing, symbolSize: 5 },
        { name: "归母权益收益率（ROCE）", type: "line", data: rows.map((r) => toPercent(r.roce_parent)), color: palette.equity, symbolSize: 5, lineStyle: { type: "dashed" } },
      ],
    };
  }, [ratios, year]);
  return <div ref={useECharts(option, CALCULATIONS)} className="chart" />;
}
