import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { yearOf } from "../data";
import type { WorkingCapitalRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette, selectedYearLine } from "./theme";

const CALCULATIONS = ["dio", "dso", "dpo", "advance_days"];

/** Cash-conversion days. DIO lives on its own axis (Moutai: >1,000 days);
 *  gaps in lines = year not disclosed (null preserved, never zeroed). */
export function WcDaysChart({ wc, year }: { wc: WorkingCapitalRow[]; year?: string }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...wc].sort((a, b) => a.end_date.localeCompare(b.end_date));
    return {
      textStyle: baseTextStyle,
      grid: { ...baseGrid, right: 56 },
      tooltip: { trigger: "axis", valueFormatter: (v) => (v == null ? "未披露或无法计算" : `${(v as number).toFixed(0)} 天`) },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: [
        { type: "value", name: "存货天数", ...axisStyle() },
        { type: "value", name: "天", ...axisStyle(), splitLine: { show: false } },
      ],
      series: [
        { name: "存货天数（DIO）", type: "line", yAxisIndex: 0, data: rows.map((r) => r.dio), color: palette.operating, symbolSize: 5, markLine: selectedYearLine(year) },
        { name: "应收天数（DSO）", type: "line", yAxisIndex: 1, data: rows.map((r) => r.dso), color: palette.financing, symbolSize: 5, connectNulls: false },
        { name: "应付天数（DPO）", type: "line", yAxisIndex: 1, data: rows.map((r) => r.dpo), color: palette.warn, symbolSize: 5 },
        { name: "客户预收款天数", type: "line", yAxisIndex: 1, data: rows.map((r) => r.advance_days), color: palette.equity, symbolSize: 5, lineStyle: { type: "dashed" } },
      ],
    };
  }, [wc, year]);
  return <div ref={useECharts(option, CALCULATIONS)} className="chart" />;
}
