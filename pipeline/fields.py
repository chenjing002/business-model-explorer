"""Explicit field lists for Tushare statement APIs.

The gateway's DEFAULT response omits newer CAS line items (receiv_financing,
use_right_assets, lease_liab, contract_assets, oth_eq_invest, oth_income,
asset_disp_income, credit_impa_loss, ...), which produced unexplained R1/R4
reconciliation residuals. Requesting fields explicitly returns them.

Lists follow the official Tushare Pro docs; fields not applicable to a company
(e.g., insurance/securities items for an industrial firm) come back null and
store nothing. Cashflow uses the API default, which is already complete for
our checks.

Module 15 (2026-11-20): the lists are the union of the earlier explicit list
and every column of the gateway's default response. The explicit list alone
dropped the financial-industry lines (bank deposits `depos`, central-bank
reserves `cash_reser_cb`, insurance reserves, securities client deposits,
`deriv_liab`), which banks, insurers, brokers and some industrials (000002.SZ
deriv_liab) report. The gateway returns all 158 / 93 fields in one call.
600519.SH has no values in the added fields, so its results are unchanged.
The cashflow default already includes the newer lines (credit_impa_loss,
use_right_asset_dep, end_bal_cash, ...).
"""

BALANCESHEET_FIELDS = ",".join([
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type",
    "comp_type", "end_type", "update_flag",
    # equity
    "total_share", "cap_rese", "undistr_porfit", "surplus_rese", "special_rese",
    "treasury_share", "ordin_risk_reser", "forex_differ", "minority_int",
    "oth_comp_income", "oth_eqt_tools", "oth_eqt_tools_p_shr",
    "total_hldr_eqy_exc_min_int", "total_hldr_eqy_inc_min_int",
    # current assets
    "money_cap", "trad_asset", "notes_receiv", "accounts_receiv",
    "accounts_receiv_bill", "receiv_financing", "oth_receiv", "oth_rcv_total",
    "prepayment", "div_receiv", "int_receiv", "inventories", "contract_assets",
    "nca_within_1y", "oth_cur_assets", "total_cur_assets", "hfs_assets",
    # financial-institution assets
    "sett_rsrv", "loanto_oth_bank_fi", "pur_resale_fa", "decr_in_disbur",
    "depos_in_oth_bfi", "prec_metals", "deriv_assets", "lending_funds",
    # non-current assets
    "fa_avail_for_sale", "htm_invest", "debt_invest", "oth_debt_invest",
    "lt_eqt_invest", "oth_eq_invest", "oth_illiq_fin_assets", "oth_eq_ppbond",
    "invest_real_estate", "time_deposits", "lt_rec", "fix_assets",
    "fix_assets_total", "cip", "cip_total", "const_materials",
    "fixed_assets_disp", "produc_bio_assets", "oil_and_gas_assets",
    "use_right_assets", "intan_assets", "r_and_d", "goodwill", "lt_amor_exp",
    "defer_tax_assets", "oth_nca", "oth_assets", "total_nca", "total_assets",
    # current liabilities
    "st_borr", "cb_borr", "depos_ib_deposits", "loan_oth_bank", "trading_fl",
    "notes_payable", "acct_payable", "accounts_pay", "adv_receipts",
    "contract_liab", "sold_for_repur_fa", "comm_payable", "payroll_payable",
    "taxes_payable", "int_payable", "div_payable", "oth_payable",
    "oth_pay_total", "acc_exp", "deferred_inc", "st_bonds_payable",
    "non_cur_liab_due_1y", "oth_cur_liab", "total_cur_liab", "hfs_sales",
    # non-current liabilities
    "lt_borr", "bond_payable", "lease_liab", "lt_payable", "long_pay_total",
    "specific_payables", "estimated_liab", "defer_tax_liab",
    "defer_inc_non_cur_liab", "lt_payroll_payable", "oth_ncl", "oth_liab",
    "total_ncl", "total_liab", "total_liab_hldr_eqy",
    # in the gateway default response only (mostly financial industry)
    "amor_exp", "premium_receiv", "reinsur_receiv", "reinsur_res_receiv",
    "cash_reser_cb", "rr_reins_une_prem", "rr_reins_outstd_cla",
    "rr_reins_lins_liab", "rr_reins_lthins_liab", "refund_depos",
    "ph_pledge_loans", "refund_cap_depos", "indep_acct_assets",
    "client_depos", "client_prov", "transac_seat_fee", "invest_as_receiv",
    "payable_to_reinsurer", "rsrv_insur_cont", "acting_trading_sec",
    "acting_uw_sec", "depos_oth_bfi", "deriv_liab", "depos",
    "agency_bus_liab", "prem_receiv_adva", "depos_received", "ph_invest",
    "reser_une_prem", "reser_outstd_claims", "reser_lins_liab",
    "reser_lthins_liab", "indept_acc_liab", "pledge_borr", "indem_payable",
    "policy_div_payable", "invest_loss_unconf", "acc_receivable",
    "st_fin_payable", "payables", "cost_fin_assets", "fair_value_fin_assets",
])

INCOME_FIELDS = ",".join([
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type",
    "comp_type", "end_type", "update_flag",
    "basic_eps", "diluted_eps",
    "total_revenue", "revenue", "int_income", "prem_earned", "comm_income",
    "oth_b_income", "fv_value_chg_gain", "invest_income", "ass_invest_income",
    "forex_gain", "total_cogs", "oper_cost", "int_exp", "comm_exp",
    "biz_tax_surchg", "sell_exp", "admin_exp", "rd_exp", "fin_exp",
    "fin_exp_int_exp", "fin_exp_int_inc", "assets_impair_loss",
    "credit_impa_loss", "oth_impair_loss_assets", "net_expo_hedging_benefits",
    "oth_income", "asset_disp_income", "operate_profit", "non_oper_income",
    "non_oper_exp", "nca_disploss", "total_profit", "income_tax", "n_income",
    "n_income_attr_p", "minority_gain", "oth_compr_income", "t_compr_income",
    "compr_inc_attr_p", "compr_inc_attr_m_s", "ebit", "ebitda",
    "continued_net_profit", "end_net_profit",
    # in the gateway default response only (financial industry, profit
    # distribution) plus total_opcost / amodcost_fin_assets from the docs
    "n_commis_income", "n_oth_income", "n_oth_b_income", "prem_income",
    "out_prem", "une_prem_reser", "reins_income", "n_sec_tb_income",
    "n_sec_uw_income", "n_asset_mg_income", "prem_refund", "compens_payout",
    "reser_insur_liab", "div_payt", "reins_exp", "oper_exp",
    "compens_payout_refu", "insur_reser_refu", "reins_cost_refund",
    "other_bus_cost", "insurance_exp", "undist_profit", "distable_profit",
    "transfer_surplus_rese", "transfer_housing_imprest", "transfer_oth",
    "adj_lossgain", "withdra_legal_surplus", "withdra_legal_pubfund",
    "withdra_biz_devfund", "withdra_rese_fund", "withdra_oth_ersu",
    "workers_welfare", "distr_profit_shrhder", "prfshare_payable_dvd",
    "comshare_payable_dvd", "capit_comstock_div", "total_opcost",
    "amodcost_fin_assets",
])

API_FIELDS = {
    "balancesheet": BALANCESHEET_FIELDS,
    "income": INCOME_FIELDS,
    # cashflow: API default is complete for our purposes
}
