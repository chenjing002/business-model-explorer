import * as echarts from "echarts";
import { useContext, useEffect, useRef } from "react";

import { CalculationContext } from "./CalculationPopover";
import { calculationHtml, calculationValue, escapeTooltip, type ChartCalculation, type ChartPoint } from "./calculationDetails";
import { textZh } from "./locale";

export function useECharts(option: echarts.EChartsOption, calculation?: ChartCalculation, extra?: readonly string[]) {
  const index = useContext(CalculationContext);
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current);
    chartRef.current = chart;
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const tooltip = option.tooltip;
    if (!index || !calculation || !tooltip || Array.isArray(tooltip)) {
      chartRef.current?.setOption(option, true);
      return;
    }
    const format: echarts.TooltipComponentFormatterCallback<echarts.TooltipComponentFormatterCallbackParams> = (params, ticket) => {
      const points = (Array.isArray(params) ? params : [params]) as ChartPoint[];
      const matches = points.flatMap((point) => {
        const ref = typeof calculation === "function" ? calculation(point) : {
          date: `${point.axisValueLabel ?? ""}1231`, code: calculation[point.seriesIndex],
        };
        const detail = ref?.override ?? (ref && index[ref.date]?.[ref.code]);
        return ref && detail ? [{ ref, detail }] : [];
      });
      if (!matches.length) {
        return typeof tooltip.formatter === "function" ? tooltip.formatter(params, ticket) : "";
      }
      const year = escapeTooltip(matches[0].ref.date.slice(0, 4));
      const date = matches[0].ref.date;
      for (const code of extra ?? []) {
        const detail = index[date]?.[code];
        if (detail) matches.push({ ref: { date, code }, detail });
      }
      const content = matches.map(({ ref, detail }, i) => {
        const html = calculationHtml(index, ref.date, ref.code, ref.override);
        return matches.length === 1 ? html : `<details class="calc-chart-series"${i === 0 ? " open" : ""}>
          <summary><span>${escapeTooltip(textZh(detail.label))}</span><b>${escapeTooltip(calculationValue(detail))}</b></summary>
          ${html}</details>`;
      }).join("");
      return `<div class="calc-panel"><header>${year} 年 · 原始计算项</header>${content}</div>`;
    };
    chartRef.current?.setOption({
      ...option,
      tooltip: { ...tooltip, enterable: true, hideDelay: 180, appendTo: document.body, formatter: format },
    }, true);
  }, [option, index, calculation, extra]);

  return ref;
}
