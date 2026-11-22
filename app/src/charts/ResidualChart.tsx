import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { formatYiValue, formatAmount } from "../format";
import { toYiYuan, yearOf } from "../data";
import type { ResidualIncomeRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette } from "./theme";

const CALCULATIONS = ["oi_after_tax", "reoi", "re_common"];
const EXTRA = ["capital_charge", "equity_charge"];

/** OI vs residual operating income vs common-equity residual earnings (亿元).
 *  Residual series are dashed: they depend on the assumed required return.
 *  The precomputed capital charges are surfaced in the tooltip. */
export function ResidualChart({ rows: input }: { rows: ResidualIncomeRow[] }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...input].sort((a, b) => a.end_date.localeCompare(b.end_date));
    const b = (v: number | null) => formatAmount(v);
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
          lines.push(`经营资本费用（r_op ${(r.r_op_assumed * 100).toFixed(1)}%）： <b>${b(r.capital_charge)}</b>`);
          lines.push(`权益资本费用（r_e ${(r.r_e_assumed * 100).toFixed(1)}%）： <b>${b(r.equity_charge)}</b>`);
          return lines.join("<br/>");
        },
      },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "亿元", ...axisStyle() },
      series: [
        { name: "税后经营收益（OI）", type: "line", data: rows.map((r) => toYiYuan(r.oi_after_tax)), color: palette.neutral, symbolSize: 5 },
        { name: "剩余经营收益（ReOI）", type: "line", data: rows.map((r) => toYiYuan(r.reoi)), color: palette.operating, symbolSize: 5, lineStyle: { type: "dashed" } },
        { name: "剩余权益收益（RE）", type: "line", data: rows.map((r) => toYiYuan(r.re_common)), color: palette.financing, symbolSize: 5, lineStyle: { type: "dashed" } },
      ],
    };
  }, [input]);
  return <div ref={useECharts(option, CALCULATIONS, EXTRA)} className="chart" />;
}
