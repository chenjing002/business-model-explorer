"""Export the operands actually selected by the annual analytical pipeline.

The index references existing results and source facts. Formula strings describe
the computation for inspection; they are never evaluated by the browser.
"""
from __future__ import annotations

import json

from .capital_bridge import DA_CONCEPTS, LIABILITY_GROUPS
from .econ_evolution import PANEL_MEMBERS
from .mapping import load_mapping
from .ratios import ATO_COMPONENTS
from .working_capital import DAYS, WC_GROUPS, OWC_SIGNS

# Input codes beginning with @ refer to the preceding fiscal year.
BS = {
    "noa": ("净经营资产（NOA）", "经营资产 − 经营负债", "oa ol"),
    "nfo": ("净金融负债（NFO）", "金融负债 − 金融资产", "fo fa"),
    "cse_calc": ("重构归母权益（CSE）", "净经营资产 − 净金融负债 − 少数股东权益", "noa nfo minority_interests"),
}
INCOME = {
    "oi_after_tax": ("税后经营收益（OI）", "合并净利润 ＋ 税后净财务费用", "raw:net_income_total nfe_after_tax"),
    "oi_pretax": ("税前经营收益", "税前核心经营收益 ＋ 税前特殊项目净额", "oi_core_pretax unusual_pretax"),
    "nfe_after_tax": ("税后净财务费用", "税前净财务费用 ×（1 − 假设税率）", "nfe_pretax tax_rate_assumed"),
    "unusual_after_tax": ("税后特殊项目净额", "税前特殊项目净额 ×（1 − 假设税率）", "unusual_pretax tax_rate_assumed"),
    "oi_core_after_tax": ("税后核心经营收益", "税后经营收益 − 税后特殊项目净额", "oi_after_tax unusual_after_tax"),
}
RATIOS = {
    "te_capital": ("平均合并权益", "平均净经营资产 − 平均净金融负债", "noa_capital nfo_capital"),
    "rnoa": ("净经营资产收益率（RNOA）", "税后经营收益 ÷ 平均净经营资产", "oi_after_tax noa_capital"),
    "opm": ("税后经营利润率（OPM）", "税后经营收益 ÷ 营业总收入", "oi_after_tax raw:total_revenue"),
    "opm_core": ("核心经营利润率", "税后核心经营收益 ÷ 营业总收入", "oi_core_after_tax raw:total_revenue"),
    "ato": ("净经营资产周转率（ATO）", "营业总收入 ÷ 平均净经营资产", "raw:total_revenue noa_capital"),
    "ollev": ("经营负债杠杆（OLLEV）", "平均经营负债 ÷ 平均净经营资产", "ol_capital noa_capital"),
    "flev": ("财务杠杆（FLEV）", "平均净金融负债 ÷ 平均合并权益", "nfo_capital te_capital"),
    "nbc": ("净借款成本（NBC）", "税后净财务费用 ÷ 平均净金融负债", "nfe_after_tax nfo_capital"),
    "spread": ("经营回报与净借款成本之差", "RNOA − NBC", "rnoa nbc"),
    "rotce_direct": ("合并权益收益率（ROTCE）", "合并净利润 ÷ 平均合并权益", "raw:net_income_total te_capital"),
    "roce_parent": ("归母权益收益率（ROCE）", "归母净利润 ÷ 平均归母权益", "raw:net_income_parent cse_capital"),
    "gross_margin": ("毛利率", "毛利 ÷ 营业收入", "gross_profit raw:revenue"),
}
WC = {
    "purchases_est": ("估算采购额", "营业成本 ＋（期末存货 − 期初存货）", "raw:cost_of_goods_sold wc:inventory @wc:inventory"),
    "dio": ("存货周转天数（DIO）", "365 × 平均存货 ÷ 营业成本", "days_per_year inventory_avg raw:cost_of_goods_sold"),
    "dso": ("应收款项周转天数（DSO）", "365 × 平均贸易应收款项 ÷ 营业收入", "days_per_year trade_receivables_avg raw:revenue"),
    "dpo": ("应付款项周转天数（DPO）", "365 × 平均贸易应付款项 ÷ 估算采购额", "days_per_year trade_payables_avg purchases_est"),
    "dpo_cogs": ("应付天数（营业成本口径）", "365 × 平均贸易应付款项 ÷ 营业成本", "days_per_year trade_payables_avg raw:cost_of_goods_sold"),
    "advance_days": ("客户预收款天数", "365 × 平均客户预收款 ÷ 营业收入", "days_per_year customer_advances_avg raw:revenue"),
    "ccc": ("现金循环周期（CCC）", "DIO ＋ DSO − DPO", "dio dso dpo"),
    "ccc_net_advances": ("扣除客户预收款的现金循环周期", "DIO ＋ DSO − DPO − 客户预收款天数", "ccc advance_days"),
    "owc_avg": ("平均经营营运资本", "（期初经营营运资本 ＋ 期末经营营运资本）÷ 2", "owc_begin owc_end"),
    "owc_pct_sales": ("平均经营营运资本／营业收入", "平均经营营运资本 ÷ 营业收入", "owc_avg raw:revenue"),
    "d_owc": ("经营营运资本增加额", "期末经营营运资本 − 期初经营营运资本", "owc_end owc_begin"),
    "d_revenue": ("营业收入增加额", "本年营业收入 − 上年营业收入", "raw:revenue @raw:revenue"),
    "incr_owc_per_incr_revenue": ("经营营运资本增加额／营业收入增加额", "经营营运资本增加额 ÷ 营业收入增加额", "d_owc d_revenue"),
}
CASH = {
    "fcf_simple": ("简式自由现金流", "经营活动现金流量净额 − 现金资本开支", "raw:cfo raw:capex_paid"),
    "fcf_after_disposals": ("含处置回收的简式自由现金流", "简式自由现金流 ＋ 长期资产处置回收现金", "fcf_simple raw:cash_from_asset_disposals"),
    "cash_conversion": ("经营现金流量净额／净利润", "经营活动现金流量净额 ÷ 合并净利润", "raw:cfo raw:net_income_total"),
}
CAPITAL = {
    "delta_noa": ("净经营资产增加额", "期末净经营资产 − 期初净经营资产", "noa @noa"),
    "delta_nfo": ("净金融负债变动", "期末净金融负债 − 期初净金融负债", "nfo @nfo"),
    "delta_cse": ("归母权益变动", "期末归母权益 − 期初归母权益", "cse_calc @cse_calc"),
    "delta_mi": ("少数股东权益变动", "期末少数股东权益 − 期初少数股东权益", "minority_interests @minority_interests"),
    "noa_growth": ("净经营资产增长率", "期末净经营资产 ÷ 期初净经营资产 − 1", "noa @noa"),
    "revenue_growth": ("营业总收入增长率", "本年营业总收入 ÷ 上年营业总收入 − 1", "raw:total_revenue @raw:total_revenue"),
    "reinvestment_rate": ("再投资率", "净经营资产增加额 ÷ 税后经营收益", "delta_noa oi_after_tax"),
    "da_total": ("折旧摊销（披露）", "加总已披露的折旧与摊销项目", " ".join(f"raw:{key}" for key in DA_CONCEPTS)),
    "capex_to_da": ("现金资本开支／折旧摊销", "现金资本开支 ÷ 披露折旧摊销之和", "raw:capex_paid da_total"),
    "fcf_from_oi": ("重构自由现金流", "税后经营收益 − 净经营资产增加额", "oi_after_tax delta_noa"),
    "fcf_articulation_diff": ("两种自由现金流口径差额", "重构自由现金流 − 简式自由现金流", "fcf_from_oi fcf_simple"),
}
RESIDUAL = {
    "capital_charge": ("经营资本费用", "经营必要报酬率 × 期初净经营资产", "ri_r_op @noa"),
    "equity_charge": ("权益资本费用", "权益必要报酬率 × 期初归母权益", "ri_r_e @cse_calc"),
    "reoi": ("剩余经营收益（ReOI）", "税后经营收益 − 经营资本费用", "oi_after_tax capital_charge"),
    "reoi_core": ("核心剩余经营收益", "税后核心经营收益 − 经营资本费用", "oi_core_after_tax capital_charge"),
    "re_common": ("剩余权益收益（RE）", "归母综合收益 − 权益资本费用", "raw:comprehensive_income_parent equity_charge"),
    "rnoa_open": ("期初口径经营收益率", "税后经营收益 ÷ 期初净经营资产", "oi_after_tax @noa"),
    "roce_open": ("期初口径归母收益率", "归母净利润 ÷ 期初归母权益", "raw:net_income_parent @cse_calc"),
    "ato_open": ("期初口径净经营资产周转率", "营业总收入 ÷ 期初净经营资产", "raw:total_revenue @noa"),
    "spread_op": ("经营收益率与必要报酬率之差", "期初口径经营收益率 − 经营必要报酬率", "rnoa_open ri_r_op"),
    "spread_e": ("归母收益率与必要报酬率之差", "期初口径归母收益率 − 权益必要报酬率", "roce_open ri_r_e"),
    "delta_reoi": ("剩余经营收益变动", "本年剩余经营收益 − 上年剩余经营收益", "reoi @reoi"),
    "pm": ("税后经营利润率", "税后经营收益 ÷ 营业总收入", "oi_after_tax raw:total_revenue"),
    "pm_core": ("核心经营利润率", "税后核心经营收益 ÷ 营业总收入", "oi_core_after_tax raw:total_revenue"),
    "pm_unusual": ("特殊项目利润率", "税后经营利润率 − 核心经营利润率", "pm pm_core"),
    "sales_effect": ("收入变动效应", "营业总收入变动 × 上年经营利润率", "raw:total_revenue @raw:total_revenue @pm"),
    "core_margin_effect": ("核心利润率变动效应", "本年营业总收入 × 核心经营利润率变动", "raw:total_revenue pm_core @pm_core"),
    "unusual_effect": ("特殊项目变动效应", "本年营业总收入 × 特殊项目利润率变动", "raw:total_revenue pm_unusual @pm_unusual"),
    "capital_charge_effect": ("资本费用变动效应", "上年经营资本费用 − 本年经营资本费用", "@capital_charge capital_charge"),
    "margin_effect": ("利润率影响", "经营利润率变动 × 上年周转率 × 本年期初净经营资产", "pm @pm @ato_open @noa"),
    "turnover_effect": ("周转率影响", "本年经营利润率 × 周转率变动 × 本年期初净经营资产", "pm ato_open @ato_open @noa"),
    "growth_effect": ("经营资本增长影响", "上年经营超额回报 × 两年期初净经营资产之差", "@spread_op @noa @@noa"),
}
VALUATION = {
    "market_ev": ("市场隐含经营资产价值", "总市值 ＋ 净金融负债 ＋ 少数股东权益", "market_cap nfo minority_interests"),
    "reoi_0": ("基期剩余经营收益", "税后经营收益 − r_op × 期初净经营资产", "oi_after_tax r_op_assumed @noa"),
    "re_0": ("基期剩余权益收益", "归母综合收益 − r_e × 期初归母权益", "raw:comprehensive_income_parent r_e_assumed @cse_calc"),
    "reoi_1_rnoa": ("按期初回报率估算首年剩余经营收益", "（期初口径 RNOA − r_op）× 年末净经营资产", "rnoa_open r_op_assumed noa"),
    "v_noa_reoi_flat": ("剩余经营收益零增长估值", "年末净经营资产 ＋ 基期 ReOI ÷ r_op", "noa reoi_0 r_op_assumed"),
    "v_noa_reoi_g": ("剩余经营收益增长估值", "年末净经营资产 ＋ 基期 ReOI ×（1 ＋ g）÷（r_op − g）", "noa reoi_0 r_op_assumed g_assumed"),
    "v_noa_rnoa_g": ("按期初回报率估算经营资产价值", "年末净经营资产 ＋ 首年 ReOI ÷（r_op − g）", "noa reoi_1_rnoa r_op_assumed g_assumed"),
    "v_equity_ri": ("剩余权益收益估值", "年末归母权益 ＋ 基期 RE ×（1 ＋ g）÷（r_e − g）", "cse_calc re_0 r_e_assumed g_assumed"),
    "earn_1": ("首年预测归母综合收益", "r_e × 年末归母权益 ＋ 基期 RE ×（1 ＋ g）", "r_e_assumed cse_calc re_0 g_assumed"),
    "aeg_2": ("第二年模型异常盈利增长", "基期 RE ×（1 ＋ g）× g", "re_0 g_assumed"),
    "v_equity_aeg": ("异常盈利增长估值", "［首年预测归母综合收益 ＋ 第二年 AEG ÷（r_e − g）］÷ r_e", "earn_1 aeg_2 r_e_assumed g_assumed"),
    "net_payout_implied": ("隐含归母净分配", "归母综合收益 − 归母权益变动", "raw:comprehensive_income_parent delta_cse"),
    "cum_div_growth": ("含净分配的综合收益增长率", "（本年归母综合收益 ＋ r_e × 上年隐含净分配）÷ 上年归母综合收益 − 1", "raw:comprehensive_income_parent r_e_assumed @net_payout_implied @raw:comprehensive_income_parent"),
    "aeg_actual": ("历史异常盈利增长（AEG）", "本年归母综合收益 ＋ r_e × 上年隐含净分配 −（1 ＋ r_e）× 上年归母综合收益", "raw:comprehensive_income_parent r_e_assumed @net_payout_implied @raw:comprehensive_income_parent"),
    "trailing_pe": ("年末市值／同年归母净利润", "总市值 ÷ 同年归母净利润（事后口径）", "market_cap raw:net_income_parent"),
    "normal_pe": ("正常前瞻市盈率", "1 ÷ r_e", "r_e_assumed"),
    "forward_pe_market": ("市场前瞻收益倍数", "总市值 ÷ 首年预测归母综合收益", "market_cap earn_1"),
    "forward_pe_model": ("模型前瞻收益倍数", "AEG 估值 ÷ 首年预测归母综合收益", "v_equity_aeg earn_1"),
    "v_to_p": ("模型价值／总市值", "ReOI 增长模型股权价值 ÷ 总市值", "v_equity_reoi_g market_cap"),
    "v_per_share": ("模型每股价值", "ReOI 增长模型股权价值 ÷ 总股本", "v_equity_reoi_g shares"),
    "implied_g_reoi": ("隐含永续增长率（ReOI）", "（r_op × 经营溢价 − 基期 ReOI）÷（经营溢价 ＋ 基期 ReOI）；经营溢价＝市场隐含经营资产价值 − NOA", "r_op_assumed market_ev noa reoi_0"),
    "implied_g_rnoa": ("隐含永续增长率（RNOA）", "r_op − 首年 ReOI ÷（市场隐含经营资产价值 − NOA）", "r_op_assumed reoi_1_rnoa market_ev noa"),
    "implied_g_fcf": ("隐含永续增长率（反向 DCF）", "（r_op × 市场隐含经营资产价值 − 重构自由现金流）÷（市场隐含经营资产价值 ＋ 重构自由现金流）", "r_op_assumed market_ev fcf_from_oi"),
    "implied_g_equity": ("隐含永续增长率（RE）", "（r_e × 权益溢价 − 基期 RE）÷（权益溢价 ＋ 基期 RE）；权益溢价＝总市值 − 归母权益", "r_e_assumed market_cap cse_calc re_0"),
    "implied_r_op": ("隐含经营必要报酬率", "［税后经营收益 ×（1 ＋ g）＋ g × 经营溢价］÷［经营溢价 ＋（1 ＋ g）× 期初 NOA］", "oi_after_tax g_assumed market_ev noa @noa"),
    "implied_r_e": ("隐含权益必要报酬率", "［归母综合收益 ×（1 ＋ g）＋ g × 权益溢价］÷［权益溢价 ＋（1 ＋ g）× 期初归母权益］", "raw:comprehensive_income_parent g_assumed market_cap cse_calc @cse_calc"),
}

WIDE = {
    "reformulated_bs": BS, "reformulated_is": INCOME, "ratios": RATIOS,
    "working_capital": WC, "cash_summary": CASH, "capital_summary": CAPITAL,
    "residual_income": RESIDUAL, "valuation": VALUATION,
}
PCT = {
    "tax_rate_assumed", "rnoa", "opm", "opm_core", "nbc", "rotce_direct",
    "roce_parent", "gross_margin", "owc_pct_sales", "noa_growth", "revenue_growth",
    "reinvestment_rate", "rnoa_open", "roce_open", "pm", "pm_core", "pm_unusual",
    "ri_r_op", "ri_r_e", "r_op_assumed", "r_e_assumed", "g_assumed",
    "implied_g_reoi", "implied_g_rnoa", "implied_g_fcf", "implied_g_equity",
    "implied_r_op", "implied_r_e", "cum_div_growth",
}
PP = {"spread", "spread_op", "spread_e"}
TIMES = {
    "ato", "ollev", "flev", "ato_open", "cash_conversion", "capex_to_da", "v_to_p",
    "trailing_pe", "normal_pe", "forward_pe_market", "forward_pe_model",
    "incr_owc_per_incr_revenue",
}
DAY_CODES = {"dio", "dso", "dpo", "dpo_cogs", "advance_days", "ccc", "ccc_net_advances", "days_per_year"}
MAP_ALIASES = {
    "common_equity": "cse_calc", "minority_interests": "minority_interests",
    "financial_debt": "fo", "financial_assets": "fa", "unusual_items": "unusual_pretax",
    "total_revenue": "raw:total_revenue", "net_income": "raw:supp_net_profit",
    "cfo": "raw:cfo", "capex": "raw:capex_paid", "capex_alloc": "raw:capex_paid",
    "dividends_interest": "raw:dividends_and_interest_paid", "debt_repaid": "raw:debt_repayments",
    "other_financing_out": "raw:other_financing_cash_paid", "equity_raised": "raw:cash_from_equity_issuance",
    "net_cash_change": "raw:net_increase_in_cash",
}
FLOW_RAW = {
    "inventory_change_supp": "-raw:supp_inventory_decrease",
    "operating_receivables_change_supp": "-raw:supp_operating_receivables_decrease",
    "operating_payables_change_supp": "raw:supp_operating_payables_increase",
    "ni_parent": "raw:net_income_parent",
    "minority_equity_contributions": "raw:minority_equity_contributions",
    "dividends_paid_to_minority": "-raw:dividends_paid_to_minority",
    "debt_repayments": "-raw:debt_repayments",
    "asset_disposal_proceeds": "-raw:cash_from_asset_disposals",
}


def _unit(code):
    if code == "v_per_share":
        return "price"
    if code == "fcf_articulation_diff":
        return "residual"
    if code in PCT:
        return "pct"
    if code in PP:
        return "pp"
    if code in TIMES:
        return "x"
    if code in DAY_CODES:
        return "days"
    return "CNY_yuan"


def build_calculation_details(store, bundle, facts):
    """Index year → metric key → value, formula and references to immediate operands."""
    index = {r["end_date"]: {} for table in WIDE for r in bundle[table]}
    bs_by_date = {r["end_date"]: r for r in bundle["reformulated_bs"]}
    mapping = load_mapping()
    for statement in ("balancesheet", "income", "cashflow"):
        for raw_field, spec in mapping[statement]["fields"].items():
            rows = facts[(facts.statement == statement) & (facts.raw_field == raw_field)]
            by_date = {r.end_date: r for r in rows.itertuples(index=False)}
            for ed, year in index.items():
                row = by_date.get(ed)
                unit = "price" if spec["class"] == "per_share" else "CNY_yuan"
                year[f"raw:{spec['concept']}"] = {
                    "label": spec["label_zh"],
                    "value": float(row.value) if row else None,
                    "unit": unit,
                    "formula": "Tushare 年度合并报表披露值",
                    "source": f"{statement}.{raw_field}",
                    **({"ann_date": row.f_ann_date, "row_hash": row.source_row_hash} if row else {}),
                }

    def put(year, code, label, value, formula, inputs="", unit=None, reason=None, **source):
        year[code] = {
            "label": label, "value": value, "unit": unit or _unit(code),
            "formula": formula, "inputs": inputs.split(),
            **({"reason": reason} if reason and value is None else {}), **source,
        }

    components = {}
    for row in bundle["bs_components"]:
        components.setdefault(row["end_date"], []).append(row)
    def class_inputs(rows, group):
        return " ".join(f"raw:{r['concept']}" for r in rows if r["effective_class"] == group)

    for row in bundle["reformulated_bs"]:
        ed = row["end_date"]
        year = index[ed]
        comp = components.get(ed, [])
        for code, label, group in [
            ("oa", "经营资产", "operating_asset"), ("ol", "经营负债", "operating_liability"),
            ("fa", "金融资产", "financial_asset"), ("fo", "金融负债", "financial_obligation"),
        ]:
            put(year, code, label, row.get(code), f"加总归入{label}的已披露科目", class_inputs(comp, group))
        mi_reported = year["raw:minority_interests"]["value"] is not None
        put(year, "minority_interests", "少数股东权益", row.get("minority_interests"),
            "报表披露值" if mi_reported else "合并权益 − 归母权益",
            "raw:minority_interests" if mi_reported else "raw:total_equity raw:parent_equity")
        for code, label, ref in [
            ("noa_capital", "平均净经营资产", "noa"), ("nfo_capital", "平均净金融负债", "nfo"),
            ("ol_capital", "平均经营负债", "ol"), ("cse_capital", "平均归母权益", "cse_calc"),
        ]:
            prev = bs_by_date.get(f"{int(ed[:4]) - 1}1231", {})
            start = prev.get(ref)
            end = row.get(ref)
            value = (start + end) / 2 if start is not None and end is not None else None
            put(year, code, label, value, "（期初余额 ＋ 期末余额）÷ 2", f"@{ref} {ref}",
                reason="缺少上年年末或本年年末余额")
        for group in OWC_SIGNS:
            selected = [r for r in comp if WC_GROUPS.get(r["concept"]) == group
                        and r["effective_class"] in {"operating_asset", "operating_liability"}]
            label = {"inventory": "存货", "trade_receivables": "贸易应收款项",
                     "trade_payables": "贸易应付款项", "customer_advances": "客户预收款",
                     "prepayments": "预付款项", "other_op_payables": "其他经营应付款项"}[group]
            put(year, f"wc:{group}", label, sum(r["value"] for r in selected) if selected else None,
                "加总适用的已披露科目", " ".join(f"raw:{r['concept']}" for r in selected))
        put(year, "days_per_year", "周转天数基准", DAYS, "模型约定")
        opening_assets = bs_by_date.get(f"{int(ed[:4]) - 1}1231", {}).get("total_assets_reported")
        closing_assets = row.get("total_assets_reported")
        change = closing_assets - opening_assets if closing_assets is not None and opening_assets is not None else None
        put(year, "delta_assets", "资产总计变动", change, "期末资产总计 − 期初资产总计",
            "raw:total_assets @raw:total_assets")

    for ed, year in index.items():
        r = next((r for r in bundle["reformulated_is"] if r["end_date"] == ed), {})
        terms = json.loads(r.get("is_terms") or "{}")
        for code, label, formula in [
            ("nfe_pretax", "税前净财务费用", "按融资分类加总：费用为加项、收益为减项；已披露的联营合营收益单独转入经营"),
            ("unusual_pretax", "税前特殊项目净额", "按各项报表的列报口径确定加减号"),
            ("oi_core_pretax", "税前核心经营收益", "经营收入 − 经营费用，另加已披露的联营合营投资收益"),
        ]:
            put(year, code, label, r.get(code), formula, " ".join(terms.get(code, [])))
        tax_rate = r.get("tax_rate_assumed")
        put(year, "tax_rate_assumed", "税率假设", tax_rate, "所得税分摊假设")

    for table, specs in WIDE.items():
        for row in bundle[table]:
            if row.get("basis", "average") != "average":
                continue
            year = index.setdefault(row["end_date"], {})
            flags = next((val for key, val in row.items() if key.endswith("_flags")), None)
            for key, (label, formula, inputs) in specs.items():
                put(year, key, label, row.get(key), formula, inputs, reason=flags)
            if table == "working_capital":
                for group in ("inventory", "trade_receivables", "trade_payables", "customer_advances"):
                    ref = f"wc:{group}"
                    put(year, f"{group}_avg", f"平均{year.get(ref, {}).get('label', '余额')}",
                        row.get(f"{group}_avg"), "（期初余额 ＋ 期末余额）÷ 2",
                        f"@{ref} {ref}", reason=flags)
                refs = [f"{'-' if sign < 0 else ''}wc:{key}" for key, sign in OWC_SIGNS.items()]
                put(year, "owc_end", "期末经营营运资本", row.get("owc_end"),
                    "经营性营运资产 − 经营性营运负债；两期均缺少的组不参与加总", " ".join(refs), reason=flags)
                put(year, "owc_begin", "期初经营营运资本", row.get("owc_begin"),
                    "同一期末定义，取上年年末各组余额",
                    " ".join(f"-@{ref[1:]}" if ref.startswith("-") else f"@{ref}" for ref in refs), reason=flags)
            if table == "residual_income":
                put(year, "ri_r_op", "经营必要报酬率", row.get("r_op_assumed"), "价值创造模块假设")
                put(year, "ri_r_e", "权益必要报酬率", row.get("r_e_assumed"), "价值创造模块假设")
            if table == "valuation":
                for code, label in [("r_op_assumed", "经营必要报酬率"),
                                    ("r_e_assumed", "权益必要报酬率"), ("g_assumed", "永续增长率")]:
                    put(year, code, label, row.get(code), "估值模型假设")
                for model, name in [("reoi_g", "剩余经营收益增长模型"),
                                    ("reoi_flat", "剩余经营收益零增长模型"), ("rnoa_g", "经营回报率基数模型")]:
                    put(year, f"v_equity_{model}", f"{name}的股权价值", row.get(f"v_equity_{model}"),
                        "经营资产价值 − 账面净金融负债 − 账面少数股东权益",
                        f"v_noa_{model} nfo minority_interests", reason=flags)

    raw_market = (store.load_raw("daily_basic", bundle["ts_code"])
                  if store.con.execute(
                      "SELECT count(*) FROM information_schema.tables WHERE table_name='raw_daily_basic'"
                  ).fetchone()[0] else facts.iloc[:0])
    traded = ({r["trade_date"]: r for r in raw_market.sort_values("_fetched_at").to_dict("records")}
              if not raw_market.empty else {})
    for row in bundle["market_snapshot"]:
        year = index.setdefault(row["end_date"], {})
        paid = traded.get(row["trade_date"], {})
        for key, label, unit, field, original_unit in [
            ("price", "年末收盘价", "price", "close", "price"),
            ("shares", "总股本", "shares", "total_share", "wan_shares"),
            ("market_cap", "总市值", "CNY_yuan", "total_mv", "wan_yuan"),
        ]:
            code = f"raw:daily_basic.{field}"
            original = paid.get(field)
            details = dict(source=f"daily_basic.{field}", trade_date=row["trade_date"],
                           row_hash=paid.get("_row_hash"))
            put(year, code, label, float(original) if original is not None and original == original else None,
                "Tushare 年末最后一笔交易日披露值", unit=original_unit, **details)
            put(year, key, label, row.get("close" if key == "price" else key),
                "原始单位 × 10,000" if unit != original_unit else "年末最后一个交易日收盘价",
                code, unit=unit)

    for row in bundle["econ_map_nodes"]:
        year = index[row["end_date"]]
        node = row["node_id"]
        inputs = [f"raw:{c['concept']}" for c in json.loads(row["components_json"])]
        formula = "加总已披露科目"
        book = MAP_ALIASES.get(node, node)
        base = year.get(book)
        if base is not None:
            formula, inputs = base["formula"], base.get("inputs", [])
            if base.get("source"):
                inputs = [book]
        elif node == "gross_profit":
            formula, inputs = "营业收入 − 营业成本", ["raw:revenue", "raw:cost_of_goods_sold"]
        elif node == "other_operating_assets":
            formula = "经营资产 − 已单列的经营资产组"
            inputs = ["oa", "map:inventory", "map:receivables_prepaid", "map:ppe_cip", "map:intangibles_other_lt"]
        elif node == "other_operating_liabilities":
            formula = "经营负债 − 已单列的供应商信用及客户预收款"
            inputs = ["ol", "map:supplier_credit", "map:customer_advances"]
        put(year, f"map:{node}", row["label"], row["value"], formula, " ".join(inputs),
            note=row["note"])
        if node == "gross_profit":
            year[node] = year[f"map:{node}"]

    for row in bundle["driver_tree_nodes"]:
        if row["basis"] != "average":
            continue
        year = index[row["end_date"]]
        code = row["node_id"]
        base = year.get("rotce_direct" if code == "rotce" else code)
        if base:
            inputs = " ".join(base["inputs"])
            formula = base["formula"]
        elif code.endswith("_to_sales") and code not in {"noa_to_sales", "other_net_to_sales"}:
            group = code.removesuffix("_to_sales")
            refs = []
            for prior in (True, False):
                ed = f"{int(row['end_date'][:4]) - int(prior)}1231"
                prefix = "@raw:" if prior else "raw:"
                refs.extend(prefix + c["concept"] for c in components.get(ed, [])
                            if ATO_COMPONENTS.get(c["concept"]) == group)
            inputs = "raw:total_revenue " + " ".join(refs)
            formula = "该组期初、期末余额的平均值 ÷ 本年营业总收入"
        elif code == "noa_to_sales":
            formula, inputs = "1 ÷ 净经营资产周转率", "ato"
        elif code == "opm_unusual":
            formula, inputs = "经营利润率 − 核心经营利润率", "opm opm_core"
        else:
            refs = [r["node_id"] for r in bundle["driver_tree_nodes"]
                    if r["end_date"] == row["end_date"] and r["basis"] == "average"
                    and r["relation"] == "component"]
            formula = "净经营资产／营业总收入 − 各已列分子项目的带符号比值"
            inputs = "tree:noa_to_sales " + " ".join(f"tree:{key}" for key in refs)
        unit = "pp" if code == "spread" else row["fmt"]
        put(year, f"tree:{code}", row["label"], row["value"], formula, inputs, unit=unit,
            reason=row["node_flags"], note=row["note"])

    for table in ("cash_bridge", "capital_bridge", "value_bridge", "valuation_bridge"):
        for row in bundle[table]:
            year = index[row["end_date"]]
            key = row["concept"]
            if table == "cash_bridge":
                refs = f"raw:{key}"
                formula = "现金流量表补充资料披露值"
                if row["step_kind"] == "total":
                    formula += "；与下列调节输入对照"
                    refs += " " + " ".join(
                        f"raw:{r['concept']}" for r in bundle[table]
                        if r["end_date"] == row["end_date"] and r["step_kind"] != "total")
            elif table == "capital_bridge":
                if key in ("noa_begin", "noa_end"):
                    formula, refs = "取净经营资产余额", "@noa" if key == "noa_begin" else "noa"
                else:
                    liability = key in {g[0] for g in LIABILITY_GROUPS} | {"other_operating_liabilities"}
                    formula = "期初余额 − 期末余额（负债增加减少 NOA）" if liability else "期末余额 − 期初余额"
                    refs = f"@map:{key} map:{key}"
            elif table == "value_bridge":
                ref = "@reoi" if key == "reoi_prev" else key
                formula, refs = year.get(key, {}).get("formula", "取对应年度剩余经营收益"), ref
            else:
                ref = {
                    "v_equity": "v_equity_reoi_g", "market_cap": "market_cap", "noa": "noa",
                    "reoi_flat_value": "reoi_0 r_op_assumed",
                    "growth_value": "v_noa_reoi_g v_noa_reoi_flat",
                    "net_financial_assets": "nfo", "minority_interests": "minority_interests",
                    "market_premium": "market_cap v_equity_reoi_g",
                }.get(key, "")
                formula = {
                    "reoi_flat_value": "基期 ReOI ÷ r_op",
                    "growth_value": "经营资产增长估值 − 经营资产零增长估值",
                    "net_financial_assets": "− 净金融负债",
                    "minority_interests": "− 少数股东权益",
                    "market_premium": "总市值 − 模型股权价值",
                }.get(key, "取对应金额")
                refs = ref
            put(year, f"{table}:{key}", row["label"], row["value"], formula, refs)

    for row in bundle["econ_evolution_groups"]:
        year = index[row["end_date"]]
        gid = row["group_id"]
        put(year, f"delta:{gid}", row["label"], row.get("delta"),
            "期末余额 − 期初余额", f"map:{gid} @map:{gid}", reason=row["evo_flags"])

    flows = {}
    for row in bundle["econ_evolution_flows"]:
        flows.setdefault((row["end_date"], row["panel_id"]), []).append(row)
    for (ed, panel), rows in flows.items():
        year = index[ed]
        prefix = f"flow:{panel}:"
        for row in rows:
            key = row["concept"]
            if key in ("opening_balance", "closing_balance"):
                prev = "@" if key == "opening_balance" else ""
                formula = "加总该组余额；缺项列于输入明细"
                refs = " ".join(f"{prev}map:{gid}" for gid in PANEL_MEMBERS[panel])
            elif key == "inferred_residual":
                formula = "期末账面余额 − 期初账面余额 − 已列示调整"
                refs = " ".join(prefix + r["concept"] for r in rows if r["concept"] != key)
            elif key in {"depreciation_disclosed", "amortization_disclosed"}:
                cf = DA_CONCEPTS[:2] if key == "depreciation_disclosed" else DA_CONCEPTS[2:]
                formula = "− 加总已披露科目"
                refs = " ".join(f"-raw:{k}" for k in cf)
            elif key == "ni_minority":
                formula, refs = "合并净利润 − 归母净利润", "raw:net_income_total raw:net_income_parent"
            else:
                refs = FLOW_RAW.get(key, f"raw:{key}")
                formula = "披露金额取相反数" if refs.startswith("-") else "披露金额"
            put(year, prefix + key, row["label"], row["value"], formula, refs, note=row["note"])

    return index
