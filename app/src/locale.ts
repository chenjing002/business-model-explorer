import texts from "./locale/texts.json";
import accounts from "./locale/accounts.json";
import type { Bundle } from "./types";

export function textZh(text: string): string {
  const translated = (texts as Record<string, string>)[text];
  if (translated) return translated;
  if (/^NOA, end \d{4}$/.test(text)) return `${text.slice(-4)}年末净经营资产`;
  if (/^ReOI \d{4}$/.test(text)) return `${text.slice(-4)}年剩余经营收益`;
  return text;
}

const FLAGS: Record<string, string> = {
  no_opening_balance: "缺少期初余额", no_prior_reoi: "缺少上期剩余经营收益",
  net_financial_assets: "净金融资产为正（净金融负债为负）",
  receivables_not_disclosed: "未披露应收款项数据",
  comprehensive_income_parent_missing: "未披露归母综合收益",
  owc_components_incomplete: "期初或期末营运资本科目披露不全",
  non_positive_revenue: "营业总收入缺失或非正值",
  non_positive_equity_capital: "权益资本基数缺失或非正值",
  ni_near_zero_suppressed: "净利润接近零，净现比无法计算",
  implied_g_reoi_undefined: "经营剩余收益模型无法反推出有效永续增长率",
  implied_g_rnoa_undefined: "经营回报模型无法反推出有效永续增长率",
  implied_g_fcf_undefined: "现金流模型无法反推出有效永续增长率",
  implied_g_equity_undefined: "剩余权益收益模型无法反推出有效永续增长率",
  balance_not_disclosed: "期初或期末余额未披露",
  group_absent_begin: "期初无此类科目，期初按零计",
  group_absent_end: "期末无此类科目，期末按零计",
  delta_revenue_near_zero_suppressed: "收入变动过小，增量比率不予展示",
  noa_near_zero_suppressed: "净经营资产基数过小，比率不予展示",
  nfo_near_zero_suppressed: "净金融负债基数过小，比率不予展示",
  negative_noa: "净经营资产为负", no_market_data: "缺少行情数据",
  growth_not_below_rate: "永续增长率不低于必要报酬率，模型不适用",
  rnoa_anchor_suppressed: "经营回报率基数不适用",
  market_ev_at_or_below_noa: "市场经营资产价值不高于账面净经营资产",
  da_not_disclosed: "补充资料未披露折旧摊销",
  // Flags first seen when the pipeline ran beyond 600519.SH (Module 16).
  reoi_base_not_positive_suppressed: "上期剩余经营收益非正或过小，增长率不予展示",
  oi_near_zero_suppressed: "税后经营收益接近零，再投资率不予展示",
  drivers_suppressed: "缺少收入或期初基数，剩余经营收益变动的利润率／周转／增长分解不予展示",
  negative_noa_base: "期初净经营资产为负，相关增长率与收益率不予展示",
  noa_base_near_zero_suppressed: "期初净经营资产接近零，相关增长率与收益率不予展示",
  supplemental_not_disclosed: "未披露现金流量表补充资料（间接法），无法逐项调节净利润与经营现金流",
  no_balance_sheet: "该年无资产负债表数据",
  non_positive_cse_base: "期初归母权益缺失或非正值，权益收益率不予计算",
  no_prior_revenue: "上年营业总收入缺失或为零，增长率不予计算",
  no_income_statement: "该年无利润表数据",
  no_revenue: "营业总收入缺失或非正值，利润率与周转率不予计算",
  bridge_unavailable_no_revenue: "缺少收入数据，无法构造剩余经营收益变动桥",
};

export function flagText(text: string): string {
  return text.split(/[,;]/).map((flag) => FLAGS[flag.trim()] ?? flag.trim()).filter(Boolean).join("；");
}

export function accountLabel(concept: string): string {
  return (accounts as Record<string, string>)[concept] ?? concept;
}

/** Copy display text only. Financial numbers, dates, identifiers and source
 *  classifications are retained exactly; raw export and database stay intact. */
export function localizeBundle(bundle: Bundle): Bundle {
  const result = { ...bundle, conventions: Object.fromEntries(
    Object.entries(bundle.conventions).map(([key, value]) => [key, textZh(value)]),
  ) };
  for (const [table, rows] of Object.entries(bundle)) {
    if (!Array.isArray(rows)) continue;
    (result as unknown as Record<string, unknown>)[table] = rows.map((row: Record<string, unknown>) =>
      Object.fromEntries(Object.entries(row).map(([key, value]) => {
        if (typeof value !== "string") return [key, value];
        if (key.endsWith("_flags")) return [key, flagText(value)];
        if (["label", "layer_name", "panel_label", "note", "formula", "dpo_method"].includes(key) || key.endsWith("_note")) {
          return [key, textZh(value)];
        }
        return [key, value];
      })),
    );
  }
  return result;
}
