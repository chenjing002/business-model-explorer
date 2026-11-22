import type { EChartsOption } from "echarts";
import { useMemo } from "react";
import { toPercent } from "../data";
import type { ReverseCurvePoint } from "../types";
import { useECharts } from "../useECharts";
import { axisStyle, baseGrid, baseTextStyle, palette } from "./theme";

const CURVES = {
  implied_g_reoi: ["ReOI 基数", "（r × 经营溢价 − 基期 ReOI）÷（经营溢价 ＋ 基期 ReOI）；基期 ReOI＝OI − r × 期初 NOA", ["market_ev", "noa", "oi_after_tax", "@noa"]],
  implied_g_rnoa: ["RNOA 基数", "r −（期初 RNOA − r）× 年末 NOA ÷ 经营溢价", ["market_ev", "noa", "rnoa_open"]],
  implied_g_fcf: ["自由现金流基数", "（r × 市场隐含经营资产价值 − FCF）÷（市场隐含经营资产价值 ＋ FCF）", ["market_ev", "fcf_from_oi"]],
  implied_g_equity: ["剩余权益收益基数", "（r × 权益溢价 − 基期 RE）÷（权益溢价 ＋ 基期 RE）；基期 RE＝归母综合收益 − r × 期初归母权益", ["market_cap", "cse_calc", "raw:comprehensive_income_parent", "@cse_calc"]],
} as const;

/** For one year's price: which (r, g) pairs justify it? Implied perpetual
 *  growth as a function of the required return (both %). */
export function ReverseCurveChart({ points, rAssumed }: { points: ReverseCurvePoint[]; rAssumed: number | null }) {
  const pts = useMemo(() => [...points].sort((a, b) => a.r - b.r), [points]);
  const option = useMemo<EChartsOption>(() => {
    const xy = (f: (p: ReverseCurvePoint) => number | null) =>
      pts.map((p) => [toPercent(p.r), toPercent(f(p))]);
    return {
      textStyle: baseTextStyle,
      grid: { ...baseGrid, top: 54, bottom: 40 },
      tooltip: {
        trigger: "axis",
        formatter: (params) => {
          const items = params as unknown as { seriesName: string; value: [number, number | null]; marker: string }[];
          const lines = items.map((p) => `${p.marker}${p.seriesName}: <b>${p.value[1] == null ? "—" : `${p.value[1].toFixed(2)}%`}</b>`);
          lines.unshift(`<b>r = ${items[0].value[0].toFixed(1)}%</b>`);
          return lines.join("<br/>");
        },
      },
      legend: { type: "scroll", top: 0, textStyle: { color: palette.muted, fontSize: 12 } },
      xAxis: { type: "value", name: "必要报酬率 r（%）", nameLocation: "middle", nameGap: 26, min: "dataMin", max: "dataMax", ...axisStyle() },
      yAxis: { type: "value", name: "隐含增长率 g（%）", ...axisStyle() },
      series: [
        {
          name: "剩余经营收益基数", type: "line", data: xy((p) => p.implied_g_reoi), color: palette.operating, symbolSize: 6, lineStyle: { width: 2 },
          markLine: rAssumed == null ? undefined : {
            silent: true, symbol: "none",
            lineStyle: { color: palette.muted, type: "dotted" },
            label: { formatter: `假设 r＝${(rAssumed * 100).toFixed(1)}%`, color: palette.muted, fontSize: 10 },
            data: [{ xAxis: rAssumed * 100 }],
          },
        },
        { name: "经营回报率基数", type: "line", data: xy((p) => p.implied_g_rnoa), color: palette.financing, symbolSize: 6, lineStyle: { width: 2 } },
        { name: "自由现金流基数（反向DCF）", type: "line", data: xy((p) => p.implied_g_fcf), color: palette.warn, symbolSize: 6, lineStyle: { width: 2 } },
        { name: "剩余权益收益（RE）", type: "line", data: xy((p) => p.implied_g_equity), color: palette.accent, symbolSize: 6, lineStyle: { width: 2 } },
      ],
    };
  }, [pts, rAssumed]);
  return <div ref={useECharts(option, (point) => {
    const row = pts[point.dataIndex];
    const code = (Object.keys(CURVES) as (keyof typeof CURVES)[])[point.seriesIndex];
    if (!row || !code) return;
    const [name, formula, inputs] = CURVES[code];
    return { date: row.end_date, code, override: {
      label: `隐含永续增长率（${name}）`, value: row[code], unit: "pct",
      formula, inputs: [...inputs], note: `当前情景必要报酬率 r＝${(row.r * 100).toFixed(1)}%`,
    } };
  })} className="chart" />;
}
