import type { EChartsOption } from "echarts";
import { useContext, useMemo } from "react";
import type { ValuationGridCell } from "../types";
import { useECharts } from "../useECharts";
import { baseTextStyle, palette } from "./theme";
import { formatAmount, formatPrice } from "../format";

import { CalculationContext } from "../CalculationPopover";
import { sensitivityRef } from "../calculationDetails";

const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

/** Model value / market cap over an (r, g) grid for one year. Diverging
 *  around V/P = 1: blue = model above the price, amber = price above the
 *  model, gray = agreement. Colour uses log2(V/P) so 0.5× and 2× sit
 *  symmetrically (display scaling only); cells are labelled with V/P. */
export function SensitivityHeatmap({ cells, assumed }: { cells: ValuationGridCell[]; assumed: { r: number; g: number } | null }) {
  const index = useContext(CalculationContext);
  const option = useMemo<EChartsOption>(() => {
    const rs = [...new Set(cells.map((c) => c.r))].sort((a, b) => a - b);
    const gs = [...new Set(cells.map((c) => c.g))].sort((a, b) => a - b);
    const data = cells.map((c) => {
      const isAssumed = assumed != null && Math.abs(c.r - assumed.r) < 1e-9 && Math.abs(c.g - assumed.g) < 1e-9;
      return {
        value: [gs.indexOf(c.g), rs.indexOf(c.r), c.v_to_p == null || c.v_to_p <= 0 ? null : Math.log2(c.v_to_p), c.v_to_p],
        itemStyle: isAssumed ? { borderColor: palette.ink, borderWidth: 2 } : { borderColor: "#fff", borderWidth: 2 },
        // dark ends of the diverging ramp need light text to stay legible
        label: { color: c.v_to_p != null && c.v_to_p > 0 && Math.abs(Math.log2(c.v_to_p)) > 0.6 ? "#fff" : palette.ink },
      };
    });
    return {
      textStyle: baseTextStyle,
      grid: { left: 64, right: 16, top: 12, bottom: 72 },
      tooltip: {
        formatter: (p) => {
          const v = (p as unknown as { value: [number, number, number | null, number | null] }).value;
          const cell = cells.find((c) => c.g === gs[v[0]] && c.r === rs[v[1]]);
          if (!cell) return "";
          return [`<b>r ${pct(cell.r)}, g ${pct(cell.g)}</b>`,
            `模型股权价值： <b>${formatAmount(cell.v_equity)}</b>`,
            `模型每股价值： <b>${formatPrice(cell.v_per_share)}</b>`,
            `V/P: <b>${cell.v_to_p == null ? "—" : cell.v_to_p.toFixed(2)}</b>`].join("<br/>");
        },
      },
      xAxis: { type: "category", data: gs.map(pct), name: "永续增长率 g", nameLocation: "middle", nameGap: 26, axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: palette.muted, fontSize: 12 } },
      yAxis: { type: "category", data: rs.map(pct), name: "经营必要报酬率", axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: palette.muted, fontSize: 12 } },
      visualMap: {
        type: "continuous", min: -1, max: 1, dimension: 2, calculable: false,
        orient: "horizontal", left: "center", bottom: 0, itemHeight: 160, itemWidth: 10,
        text: ["模型价值为市值2倍", "市值为模型价值2倍"], textStyle: { color: palette.muted, fontSize: 10 },
        inRange: { color: [palette.warn, "#f3d9bf", "#e5e7eb", "#c7d4f5", palette.operating] },
        outOfRange: { color: palette.neutral },
      },
      series: [{
        type: "heatmap", data,
        label: { show: true, fontSize: 10, color: palette.ink, formatter: (p) => {
          const v = (p as unknown as { value: [number, number, number | null, number | null] }).value[3];
          return v == null ? "—" : v.toFixed(2);
        } },
        emphasis: { itemStyle: { borderColor: palette.ink, borderWidth: 1 } },
      }],
    };
  }, [cells, assumed]);
  return <div ref={useECharts(option, (point) => index && cells[point.dataIndex] ? sensitivityRef(cells[point.dataIndex], index) : undefined)} className="chart chart--tall" />;
}
