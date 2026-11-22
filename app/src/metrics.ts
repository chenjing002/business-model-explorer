/** Shared related-metric lookup: where each declared metric key lives in the
 *  bundle and how to format it. Pure join + formatting — no financial math.
 */
import type { Bundle } from "./types";
import { yearOf } from "./data";

export type MetricFmt = "pct" | "days" | "x" | "ratio";

export const METRIC_SOURCES: Record<
  string,
  { table: "ratios" | "working_capital" | "cash_summary" | "capital_summary"; fmt: MetricFmt; label: string }
> = {
  rnoa: { table: "ratios", fmt: "pct", label: "净经营资产收益率（RNOA）" },
  opm: { table: "ratios", fmt: "pct", label: "税后经营利润率（OPM）" },
  opm_core: { table: "ratios", fmt: "pct", label: "核心经营利润率" },
  ato: { table: "ratios", fmt: "x", label: "净经营资产周转率（ATO）" },
  gross_margin: { table: "ratios", fmt: "pct", label: "毛利率" },
  roce_parent: { table: "ratios", fmt: "pct", label: "归母净资产收益率（ROCE）" },
  rotce_direct: { table: "ratios", fmt: "pct", label: "合并净资产收益率（ROTCE）" },
  flev: { table: "ratios", fmt: "x", label: "财务杠杆（FLEV）" },
  nbc: { table: "ratios", fmt: "pct", label: "净借款成本（NBC）" },
  inventory_to_sales: { table: "ratios", fmt: "x", label: "存货／营业总收入" },
  ppe_to_sales: { table: "ratios", fmt: "x", label: "固定资产等／营业总收入" },
  cip_to_sales: { table: "ratios", fmt: "x", label: "在建工程／营业总收入" },
  dio: { table: "working_capital", fmt: "days", label: "存货周转天数（DIO）" },
  dso: { table: "working_capital", fmt: "days", label: "应收款项周转天数（DSO）" },
  dpo: { table: "working_capital", fmt: "days", label: "应付款项周转天数（DPO）" },
  dpo_cogs: { table: "working_capital", fmt: "days", label: "应付天数（营业成本口径）" },
  advance_days: { table: "working_capital", fmt: "days", label: "客户预收款天数" },
  ccc: { table: "working_capital", fmt: "days", label: "现金循环周期（CCC）" },
  incr_owc_per_incr_revenue: { table: "working_capital", fmt: "ratio", label: "营运资本增加额／收入增加额" },
  cash_conversion: { table: "cash_summary", fmt: "x", label: "经营现金流量净额／净利润" },
  reinvestment_rate: { table: "capital_summary", fmt: "pct", label: "再投资率（净经营资产增加额／税后经营收益）" },
  capex_to_da: { table: "capital_summary", fmt: "x", label: "资本开支／折旧摊销" },
};

export function fmtMetric(v: unknown, fmt: string): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "未披露或无法计算";
  if (fmt === "pp") return `${(v * 100).toFixed(1)} 个百分点`;
  if (fmt === "pct") return `${(v * 100).toFixed(1)}%`;
  if (fmt === "days") return `${v.toFixed(0)} 天`;
  if (fmt === "x") return `${v.toFixed(2)} 倍`;
  return v.toFixed(2);
}

export function relatedValue(bundle: Bundle, year: string, key: string): unknown {
  const src = METRIC_SOURCES[key];
  if (!src) return undefined;
  if (src.table === "ratios") {
    const row = bundle.ratios.find(
      (r) => yearOf(r.end_date) === year && r.basis === "average",
    );
    return row?.[key];
  }
  const rows = src.table === "working_capital" ? bundle.working_capital
    : src.table === "capital_summary" ? bundle.capital_summary : bundle.cash_summary;
  const row = rows.find((r) => yearOf(r.end_date) === year);
  return (row as unknown as Record<string, unknown>)?.[key];
}
