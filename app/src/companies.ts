/** Company picker index: loading, search and industry grouping.
 *  Pure list handling — no financial data lives here.
 */
import { siteUrl } from "./site";

export interface CompanyEntry {
  ts_code: string;
  name: string | null;
  industry: string | null;
  cnspell: string | null;
  market: string | null;
}

export type UnavailableReason = "financial" | "no_annual_report" | "error";

export interface CompanyIndex {
  companies: CompanyEntry[];
  analyzed: Set<string>;
  byCode: Map<string, CompanyEntry>;
  /** Latest batch-analysis reason for a company without a bundle; absent = not run yet. */
  unavailable: Map<string, { reason: UnavailableReason; step: string | null }>;
  /** Identity-check families that failed for an analysed company (reported, not corrected). */
  checkFailures: Map<string, string[]>;
}

interface RawIndex {
  companies: CompanyEntry[];
  analyzed: string[];
  unavailable?: Record<string, { reason: UnavailableReason; step: string | null }>;
  check_failures?: Record<string, string[]>;
}

export const UNAVAILABLE_LABELS: Record<UnavailableReason | "not_run", { tag: string; text: string }> = {
  financial: { tag: "金融类", text: "属于金融类公司（银行、保险、证券等），报表结构与一般工商企业不同；本项目尚未建立金融类科目映射，因此不生成重构报表及后续分析。" },
  no_annual_report: { tag: "无年报", text: "尚无年度合并报表（新上市公司目前只有季度报告），年度分析至少需要一期年报。" },
  error: { tag: "分析失败", text: "批量分析流程未能完成，未生成数据包；失败原因记录在批量分析报告 data/analysis_failures.csv 中。" },
  not_run: { tag: "未分析", text: "原始三表已入库，但尚未运行分析流程（科目映射、报表重构及后续分析）。" },
};

/** Pipeline steps (pipeline/bulk_analyze.py) in Chinese. */
export const STEP_LABELS: Record<string, string> = {
  map: "科目映射", reformulate: "报表重构", ratios: "比率分解", wc: "营运资本",
  cash: "利润与现金调节", econmap: "商业经济地图", evolution: "年度演化", drivertree: "盈利驱动树",
  capital: "资本与再投资", residual: "剩余收益", market: "年末市值", valuation: "估值", export: "数据包导出",
};

/** Check families (pipeline/bulk_analyze.py CHECK_FAMILIES) in Chinese. */
export const CHECK_FAMILY_LABELS: Record<string, string> = {
  R1: "资产重构 R1", R2: "负债重构 R2", R3: "权益重构 R3", R4: "税前利润分类 R4",
  L: "经济地图恒等式 L1–L3/L5", E: "年度演化 E1–E3", T: "驱动树 T1–T5", B: "资本桥 B1–B3",
  RI: "剩余收益 RI1–RI4", V: "估值 V1–V10/M1",
};

export function availability(index: CompanyIndex, code: string) {
  if (index.analyzed.has(code)) return null;
  const entry = index.unavailable.get(code);
  const label = UNAVAILABLE_LABELS[entry?.reason ?? "not_run"] ?? UNAVAILABLE_LABELS.not_run;
  const step = entry?.reason === "error" && entry.step ? STEP_LABELS[entry.step] ?? entry.step : null;
  return { ...label, step };
}

export interface IndustryGroup {
  industry: string;
  companies: CompanyEntry[];
}

/** stock_basic leaves industry blank for some listings; never invent one. */
export const UNKNOWN_INDUSTRY = "行业未披露";

export const industryOf = (entry: CompanyEntry | undefined) => entry?.industry || UNKNOWN_INDUSTRY;

export function buildIndex(raw: RawIndex): CompanyIndex {
  return {
    companies: raw.companies,
    analyzed: new Set(raw.analyzed),
    byCode: new Map(raw.companies.map((entry) => [entry.ts_code, entry])),
    unavailable: new Map(Object.entries(raw.unavailable ?? {})),
    checkFailures: new Map(Object.entries(raw.check_failures ?? {})),
  };
}

export async function loadCompanyIndex(signal?: AbortSignal): Promise<CompanyIndex> {
  const res = await fetch(siteUrl("/data/companies.json"), { signal });
  if (!res.ok) throw new Error(`无法加载公司列表：${res.status}`);
  const raw = await res.json() as RawIndex & { schema_version: number };
  if (raw.schema_version !== 1) throw new Error(`不支持的公司列表版本：${raw.schema_version}`);
  return buildIndex(raw);
}

const collator = new Intl.Collator("zh-CN");

/** Lower is better; null means no match. Industry hits rank after company hits. */
function matchRank(entry: CompanyEntry, term: string): number | null {
  const code = entry.ts_code.toLowerCase();
  const symbol = code.split(".")[0];
  const name = (entry.name ?? "").toLowerCase();
  const spell = (entry.cnspell ?? "").toLowerCase();
  if (code === term || symbol === term || name === term || spell === term) return 0;
  if (symbol.startsWith(term) || name.startsWith(term) || spell.startsWith(term)) return 1;
  if (code.includes(term) || name.includes(term) || spell.includes(term)) return 2;
  if ((entry.industry ?? "").toLowerCase().includes(term)) return 3;
  return null;
}

/** Filter by name, code, symbol, pinyin initials or industry and group by industry.
 *  Empty query: every company, `current`'s industry first, then industries
 *  in Chinese collation order. With a query, groups follow their best match. */
export function searchCompanies(index: CompanyIndex, query: string, current = ""): IndustryGroup[] {
  const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const currentEntry = index.byCode.get(current);
  const currentIndustry = currentEntry ? industryOf(currentEntry) : null;
  const groups = new Map<string, { companies: { entry: CompanyEntry; rank: number }[]; best: number }>();
  for (const entry of index.companies) {
    let rank = 0;
    for (const term of terms) {
      const hit = matchRank(entry, term);
      if (hit === null) { rank = -1; break; }
      rank = Math.max(rank, hit);
    }
    if (rank < 0) continue;
    const industry = industryOf(entry);
    const group = groups.get(industry) ?? { companies: [], best: Infinity };
    group.companies.push({ entry, rank });
    group.best = Math.min(group.best, rank);
    groups.set(industry, group);
  }
  const analyzedFirst = (a: CompanyEntry, b: CompanyEntry) =>
    Number(index.analyzed.has(b.ts_code)) - Number(index.analyzed.has(a.ts_code));
  return [...groups.entries()]
    .sort(([a, ga], [b, gb]) => (terms.length ? ga.best - gb.best : 0) ||
      Number(b === currentIndustry) - Number(a === currentIndustry) ||
      Number(a === UNKNOWN_INDUSTRY) - Number(b === UNKNOWN_INDUSTRY) ||
      collator.compare(a, b))
    .map(([industry, group]) => ({
      industry,
      companies: group.companies
        .sort((a, b) => a.rank - b.rank || analyzedFirst(a.entry, b.entry) ||
          a.entry.ts_code.localeCompare(b.entry.ts_code))
        .map(({ entry }) => entry),
    }));
}

/** ←/→ browse order: the picker's grouping without a current-company bias
 *  (industries in collation order, analysed first within each). */
export function companyOrder(index: CompanyIndex): string[] {
  return searchCompanies(index, "").flatMap((group) => group.companies.map((entry) => entry.ts_code));
}

/** Previous/next analysed company in `order`, wrapping at the ends; companies
 *  without a bundle are stepped over. null when no other company is analysed. */
export function adjacentCompany(index: CompanyIndex, order: string[], current: string, step: 1 | -1): string | null {
  const n = order.length;
  let at = order.indexOf(current);
  if (at < 0) at = step > 0 ? -1 : n;
  for (let k = 1; k <= n; k += 1) {
    const code = order[(((at + step * k) % n) + n) % n];
    if (code !== current && index.analyzed.has(code)) return code;
  }
  return null;
}
