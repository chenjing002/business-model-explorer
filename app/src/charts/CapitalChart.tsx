import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { formatYiValue } from "../format";
import { toYiYuan, yearOf } from "../data";
import type { ReformulatedBsRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette, selectedYearLine } from "./theme";

const CALCULATIONS = ["noa", "nfo", "cse_calc"];

/** Stocks at year end: NOA and NFO as bars (NFO < 0 = net financial assets),
 *  common equity as a line for reference. */
export function CapitalChart({ bs, year }: { bs: ReformulatedBsRow[]; year?: string }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...bs].sort((a, b) => a.end_date.localeCompare(b.end_date));
    return {
      textStyle: baseTextStyle,
      grid: baseGrid,
      tooltip: { trigger: "axis", valueFormatter: (v) => (formatYiValue(v, 1)) },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "亿元", ...axisStyle() },
      series: [
        { name: "净经营资产（NOA）", type: "bar", data: rows.map((r) => toYiYuan(r.noa)), color: palette.operating, barWidth: "22%", markLine: selectedYearLine(year) },
        { name: "净金融负债（负值为净金融资产）", type: "bar", data: rows.map((r) => toYiYuan(r.nfo)), color: palette.financing, barWidth: "22%" },
        { name: "归母权益（CSE）", type: "line", data: rows.map((r) => toYiYuan(r.cse_calc)), color: palette.equity, symbolSize: 5 },
      ],
    };
  }, [bs, year]);
  return <div ref={useECharts(option, CALCULATIONS)} className="chart" />;
}
