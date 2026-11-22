import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { formatYiValue } from "../format";
import { toYiYuan, yearOf } from "../data";
import type { ValuationRow } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette } from "./theme";

const CALCULATIONS = ["market_cap", "v_equity_reoi_g", "v_equity_reoi_flat", "v_equity_rnoa_g"];

/** Year-end market cap (reported, solid reference line) vs model equity
 *  values (assumption-driven, dashed), 亿元. All values precomputed. */
export function ModelVsMarketChart({ rows: input }: { rows: ValuationRow[] }) {
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
          const lines = items.map((p) => `${p.marker}${p.seriesName}: <b>${formatYiValue(p.value, 0)}</b>`);
          lines.unshift(`<b>${yearOf(r.end_date)}</b>${r.trade_date ? `（价格日期 ${r.trade_date}）` : ""}`);
          lines.push(`价值／市值（剩余经营收益模型）： <b>${r.v_to_p == null ? "—" : r.v_to_p.toFixed(2)}</b>`);
          return lines.join("<br/>");
        },
      },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", name: "亿元", ...axisStyle() },
      series: [
        { name: "总市值", type: "line", data: rows.map((r) => toYiYuan(r.market_cap)), color: palette.equity, symbolSize: 8, lineStyle: { width: 2.5 } },
        { name: "剩余经营收益增长模型", type: "line", data: rows.map((r) => toYiYuan(r.v_equity_reoi_g)), color: palette.operating, symbolSize: 8, lineStyle: { type: "dashed", width: 2 } },
        { name: "剩余经营收益零增长模型", type: "line", data: rows.map((r) => toYiYuan(r.v_equity_reoi_flat)), color: palette.financing, symbolSize: 8, lineStyle: { type: "dashed", width: 2 } },
        { name: "经营回报率基数模型（SF3）", type: "line", data: rows.map((r) => toYiYuan(r.v_equity_rnoa_g)), color: palette.warn, symbolSize: 8, lineStyle: { type: "dashed", width: 2 } },
      ],
    };
  }, [input]);
  return <div ref={useECharts(option, CALCULATIONS)} className="chart" />;
}
