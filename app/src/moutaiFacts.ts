/** 贵州茅台（600519.SH）导览案例的数据选取。
 *  只做行查找、取值与展示年份挑选 —— 所有财务结果均来自 Python 管道导出的
 *  数据包，本模块与组件不做任何财务计算。
 */
import { yearOf } from "./data";
import type {
  Bundle, CapitalSummaryRow, EconMapNode, RatioRow, ResidualIncomeRow, ValuationRow,
} from "./types";

export const MOUTAI_CASE_ID = "moutai-600519";
export const MOUTAI_TS_CODE = "600519.SH";

const annualOnly = <T extends { end_date: string }>(rows: T[]): T[] =>
  rows.filter((r) => r.end_date.endsWith("1231"));

const byYear = <T extends { end_date: string }>(rows: T[], year: string): T | undefined =>
  rows.find((r) => yearOf(r.end_date) === year);

/** 在已导出的数值中挑选展示年份（最大/最小值所在年），不产生新数值。 */
function pickYear<T extends { end_date: string }>(
  rows: T[], key: keyof T, mode: "max" | "min",
): T | undefined {
  let best: T | undefined;
  for (const row of rows) {
    const v = row[key];
    if (typeof v !== "number" || !Number.isFinite(v)) continue;
    const current = best?.[key] as number | undefined;
    if (current === undefined || (mode === "max" ? v > current : v < current)) best = row;
  }
  return best;
}

export interface MoutaiFacts {
  latestYear: string;
  exportedAt: string;
  /** 比率表（平均资本口径）按年升序。 */
  ratioRows: RatioRow[];
  atoPeak: RatioRow | null;
  overview: {
    totalRevenue: number | null; oiAfterTax: number | null; niParent: number | null;
    rnoa: number | null; rotce: number | null; opm: number | null;
    grossMargin: number | null; flev: number | null;
    noa: number | null; nfo: number | null;
    cfo: number | null; fcfSimple: number | null; cashConversion: number | null;
  };
  /** 最新年度经济地图第 1、2 层节点（资金来源／资金投向）。 */
  mapSources: EconMapNode[];
  mapUses: EconMapNode[];
  dividendsInterest: number | null;
  capexAlloc: number | null;
  /** 驱动树：最新年度 NOA/销售 及其加项（平均资本口径）。 */
  noaToSales: number | null;
  intensity: { nodeId: string; label: string; value: number | null; weight: number | null }[];
  capitalRows: CapitalSummaryRow[];
  reinvestMin: CapitalSummaryRow | null;
  latestCapital: CapitalSummaryRow | null;
  /** 最新年度资本投入桥中的存货变动（Δ存货）。 */
  inventoryDelta: number | null;
  advancesPeak: { year: string; days: number } | null;
  advancesLatest: { year: string; days: number } | null;
  dioLatest: number | null;
  cashConversionMin: { year: string; value: number } | null;
  valueLatest: ResidualIncomeRow | null;
  valuationRows: ValuationRow[];
  vToPMin: ValuationRow | null;
  valuationLatest: ValuationRow | null;
}

export function buildMoutaiFacts(bundle: Bundle): MoutaiFacts {
  const bs = annualOnly(bundle.reformulated_bs);
  const latestYear = bs.length ? yearOf(bs[bs.length - 1].end_date) : "";
  const ratioRows = annualOnly(bundle.ratios)
    .filter((r) => r.basis === "average")
    .filter((r) => r.rnoa !== null || r.opm !== null || r.ato !== null)
    .sort((a, b) => a.end_date.localeCompare(b.end_date));
  const latestRatio = byYear(ratioRows, latestYear);
  const latestIs = annualOnly(bundle.reformulated_is)
    .find((r) => yearOf(r.end_date) === latestYear && r.period_kind === "cumulative");
  const latestBs = byYear(bs, latestYear);
  const latestCash = byYear(annualOnly(bundle.cash_summary), latestYear);
  const mapLatest = bundle.econ_map_nodes.filter((n) => yearOf(n.end_date) === latestYear);
  const treeLatest = bundle.driver_tree_nodes.filter(
    (n) => yearOf(n.end_date) === latestYear && n.basis === "average",
  );
  const capitalRows = annualOnly(bundle.capital_summary)
    .sort((a, b) => a.end_date.localeCompare(b.end_date));
  const wcRows = annualOnly(bundle.working_capital);
  const advancesPeakRow = pickYear(wcRows, "advance_days", "max");
  const advancesLatestRow = byYear(wcRows, latestYear);
  const convMinRow = pickYear(annualOnly(bundle.cash_summary), "cash_conversion", "min");
  const valuationRows = annualOnly(bundle.valuation)
    .sort((a, b) => a.end_date.localeCompare(b.end_date))
    .filter((r) => r.v_to_p !== null);

  return {
    latestYear,
    exportedAt: bundle.exported_at,
    ratioRows,
    atoPeak: pickYear(ratioRows, "ato", "max") ?? null,
    overview: {
      totalRevenue: latestIs?.total_revenue ?? null,
      oiAfterTax: latestIs?.oi_after_tax ?? null,
      niParent: latestIs?.ni_parent ?? null,
      rnoa: latestRatio?.rnoa ?? null,
      rotce: latestRatio?.rotce ?? null,
      opm: latestRatio?.opm ?? null,
      grossMargin: latestRatio?.gross_margin ?? null,
      flev: latestRatio?.flev ?? null,
      noa: latestBs?.noa ?? null,
      nfo: latestBs?.nfo ?? null,
      cfo: latestCash?.cfo ?? null,
      fcfSimple: latestCash?.fcf_simple ?? null,
      cashConversion: latestCash?.cash_conversion ?? null,
    },
    mapSources: mapLatest.filter((n) => n.layer === 1),
    mapUses: mapLatest.filter((n) => n.layer === 2),
    dividendsInterest: mapLatest.find((n) => n.node_id === "dividends_interest")?.value ?? null,
    capexAlloc: mapLatest.find((n) => n.node_id === "capex_alloc")?.value ?? null,
    noaToSales: treeLatest.find((n) => n.node_id === "noa_to_sales")?.value ?? null,
    intensity: treeLatest
      .filter((n) => n.parent_id === "noa_to_sales" && n.weight !== null)
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((n) => ({ nodeId: n.node_id, label: n.label, value: n.value, weight: n.weight })),
    capitalRows,
    reinvestMin: pickYear(capitalRows, "reinvestment_rate", "min") ?? null,
    latestCapital: byYear(capitalRows, latestYear) ?? null,
    inventoryDelta: bundle.capital_bridge.find(
      (s) => yearOf(s.end_date) === latestYear && s.concept === "inventory",
    )?.value ?? null,
    advancesPeak: advancesPeakRow?.advance_days != null
      ? { year: yearOf(advancesPeakRow.end_date), days: advancesPeakRow.advance_days } : null,
    advancesLatest: advancesLatestRow?.advance_days != null
      ? { year: latestYear, days: advancesLatestRow.advance_days } : null,
    dioLatest: advancesLatestRow?.dio ?? null,
    cashConversionMin: convMinRow?.cash_conversion != null
      ? { year: yearOf(convMinRow.end_date), value: convMinRow.cash_conversion } : null,
    valueLatest: byYear(annualOnly(bundle.residual_income), latestYear) ?? null,
    valuationRows,
    vToPMin: pickYear(valuationRows, "v_to_p", "min") ?? null,
    valuationLatest: byYear(valuationRows, latestYear) ?? null,
  };
}
