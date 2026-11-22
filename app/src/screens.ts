/** 好生意榜单: typed mirror and loader of `data/screens.json`
 *  (`pipeline/screens.py`). Every value and every ranking is computed in
 *  Python; this module only fetches and formats.
 */
import { formatAmount, formatNumber } from "./format";
import { fmtMetric } from "./metrics";
import { siteUrl } from "./site";

export type ScreenUnit = "CNY_yuan" | "pct" | "days" | "count" | "x" | "text";

export interface ScreenRow {
  ts_code: string;
  name: string | null;
  industry: string | null;
  values: Record<string, number | string | null>;
  /** One value per window year, oldest first; null = not disclosed. */
  trend: (number | null)[];
}

export interface ScreenList {
  id: string;
  title: string;
  summary: string;
  criteria: string[];
  sort: string;
  concepts: string[];
  columns: { key: string; label: string; unit: ScreenUnit }[];
  trend: { label: string; unit: ScreenUnit };
  count: number;
  rows: ScreenRow[];
}

export interface Screens {
  schema_version: number;
  unit: string;
  fiscal_year: string;
  window: string[];
  exported_at: string;
  universe: {
    analyzed_ok: number;
    excluded_check_failures: number;
    excluded_incomplete_years: number;
    excluded_below_revenue_floor: number;
    revenue_floor: number;
    ranked: number;
  };
  lists: ScreenList[];
}

export async function loadScreens(signal?: AbortSignal): Promise<Screens> {
  const res = await fetch(siteUrl("/data/screens.json"), { signal });
  if (!res.ok) throw new Error(`无法加载好生意榜单：${res.status}`);
  if (res.headers.get("content-type")?.includes("text/html")) throw new Error("尚未生成好生意榜单数据");
  const data = await res.json() as Screens;
  if (data.schema_version !== 1) throw new Error(`不支持的榜单数据版本：${data.schema_version}`);
  if (data.unit !== "CNY_yuan") throw new Error(`金额单位应为人民币元（CNY_yuan），收到：${data.unit}`);
  return data;
}

export function formatScreenValue(value: number | string | null | undefined, unit: ScreenUnit): string {
  if (value == null || value === "") return "—";
  if (typeof value === "string") return value;
  if (!Number.isFinite(value)) return "—";
  switch (unit) {
    case "CNY_yuan": return formatAmount(value);
    case "pct": return `${formatNumber(value * 100, 1)}%`;
    case "days": return fmtMetric(value, "days");
    case "x": return `${formatNumber(value, 2)} 倍`;
    case "count": return formatNumber(value, 0);
    default: return String(value);
  }
}
