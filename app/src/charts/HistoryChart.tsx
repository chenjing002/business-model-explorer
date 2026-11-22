import type { EChartsOption } from "echarts";
import { toPercent } from "../data";
import { formatNumber, formatPrice, formatYiValue, toYiYuan } from "../format";
import { fmtMetric } from "../metrics";
import { useECharts } from "../useECharts";
import { axisStyle, baseTextStyle, palette } from "./theme";

type Unit = "亿元" | "元/股" | "%" | "倍" | "天";
interface Series {
  label: string;
  color: string;
  values: (number | null)[];
  bars?: boolean;
}

interface Props {
  label: string;
  years: string[];
  series: Series[];
  unit: Unit;
}

const axisValues = { "亿元": toYiYuan, "%": toPercent };
const tooltipValue = (unit: Unit, value: number) => {
  if (unit === "亿元") return formatYiValue(value);
  if (unit === "元/股") return formatPrice(value);
  if (unit === "天") return fmtMetric(value, "days");
  return `${formatNumber(value)}${unit === "倍" ? " 倍" : "%"}`;
};

function Plot({ label, years, series, unit }: Props) {
  const scale = unit === "亿元" || unit === "%" ? axisValues[unit] : (value: number | null) => value;
  const option: EChartsOption = {
    animation: false,
    textStyle: baseTextStyle,
    grid: { left: 2, right: 14, top: series.length > 1 ? 48 : 24, bottom: 2, containLabel: true },
    legend: series.length > 1 ? { top: 0, textStyle: { color: palette.muted } } : undefined,
    tooltip: {
      trigger: "axis", confine: true,
      valueFormatter: (value) => typeof value === "number" && Number.isFinite(value)
        ? tooltipValue(unit, value) : "未披露或无法计算",
    },
    xAxis: {
      type: "category", data: years, ...axisStyle(),
      axisLine: { onZero: false, lineStyle: { color: palette.grid } },
      axisLabel: { color: palette.muted, fontSize: 11, showMinLabel: true, showMaxLabel: true },
    },
    yAxis: {
      type: "value", name: unit, scale: unit === "%" || unit === "倍", ...axisStyle(),
      splitNumber: 3, nameTextStyle: { color: palette.muted },
    },
    series: series.map(({ label, color, values, bars }) => {
      const data = values.map(scale);
      return bars
        ? { name: label, type: "bar", data, color, barMaxWidth: 34 }
        : { name: label, type: "line", data, color, symbol: "circle", symbolSize: 6, lineStyle: { width: 2 } };
    }),
  };

  return <div ref={useECharts(option)} className="overview__history-chart" role="img" aria-label={`${label}历年趋势，单位${unit}`} />;
}

export function HistoryChart(props: Props) {
  if (props.series.every(({ values }) => values.every((value) => value == null))) {
    return <p className="overview__history-chart overview__history-empty">暂无可绘制数据</p>;
  }
  return <Plot {...props} />;
}
