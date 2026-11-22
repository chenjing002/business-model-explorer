import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { formatYiValue } from "../format";
import { toYiYuan, yearOf } from "../data";
import type { ResidualIncomeRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette } from "./theme";

const CALCULATIONS = ["margin_effect", "turnover_effect", "growth_effect", "delta_reoi"];

/** Penman drivers of ΔReOI (亿元): margin + turnover (profitability) + growth,
 *  stacked by sign; the ΔReOI line is their exact sum (check RI2). Years
 *  where RNOA is not meaningful arrive as null and draw nothing. */
export function DriverEffectsChart({ rows: input }: { rows: ResidualIncomeRow[] }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...input]
      .filter((r) => r.drivers_available)
      .sort((a, b) => a.end_date.localeCompare(b.end_date));
    const bar = { type: "bar" as const, stack: "drivers", barWidth: "50%", itemStyle: { borderColor: "#fff", borderWidth: 1 } };
    return {
      textStyle: baseTextStyle,
      grid: baseGrid,
      tooltip: { trigger: "axis", valueFormatter: (v) => (formatYiValue(v, 2)) },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "亿元", ...axisStyle() },
      series: [
        { ...bar, name: "利润率影响", data: rows.map((r) => toYiYuan(r.margin_effect)), color: palette.operating },
        { ...bar, name: "周转率影响", data: rows.map((r) => toYiYuan(r.turnover_effect)), color: palette.financing },
        { ...bar, name: "经营资本增长影响", data: rows.map((r) => toYiYuan(r.growth_effect)), color: palette.warn },
        { name: "剩余经营收益变动", type: "line", data: rows.map((r) => toYiYuan(r.delta_reoi)), color: palette.ink, symbolSize: 6, z: 5 },
      ],
    };
  }, [input]);
  return <div ref={useECharts(option, CALCULATIONS)} className="chart" />;
}
