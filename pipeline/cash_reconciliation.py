"""Module 6 — Earnings-to-cash reconciliation (NI → CFO → FCF).

Built from the REPORTED indirect-method supplemental block (supp_* concepts).
Every add-back is stored with Tushare's own sign (positive = adds to cash);
the bridge residual (C1) verifies the convention per year and is REPORTED,
never forced to zero. Years without supplemental disclosure get no bridge —
flagged, not imputed.

CAS conventions preserved (NOT adjusted): interest received sits in investing
cash flow, interest and dividends paid in financing. Chinese CFO therefore
already excludes financing interest. FCF variants carry their formulas as
text so no definition is ever implicit.

Judgment rule: this module computes; it never labels FCF levels good or bad.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .store import Store

# Ordered bridge steps: (concept, display label). Sign: value adds to cash.
BRIDGE_STEPS = [
    ("supp_impairment_provisions", "Asset impairment provisions"),
    ("supp_credit_impairment_loss", "Credit impairment loss"),
    ("supp_depreciation", "Depreciation of fixed assets"),
    ("supp_rou_asset_depreciation", "Right-of-use asset depreciation"),
    ("supp_intangible_amortization", "Intangible amortization"),
    ("supp_lt_deferred_amortization", "LT deferred expense amortization"),
    ("supp_asset_disposal_loss", "Loss on asset disposals"),
    ("supp_asset_writeoff_loss", "Fixed asset write-off loss"),
    ("supp_fair_value_loss", "Fair value change loss"),
    ("supp_finance_expense", "Finance expense add-back"),
    ("supp_investment_loss", "Investment loss (− = income)"),
    ("supp_deferred_tax_asset_decrease", "Deferred tax asset decrease"),
    ("supp_deferred_tax_liab_increase", "Deferred tax liability increase"),
    ("supp_inventory_decrease", "Inventory decrease (− = build)"),
    ("supp_operating_receivables_decrease", "Operating receivables decrease"),
    ("supp_operating_payables_increase", "Operating payables increase"),
    ("supp_net_capital_disposal", "Net cash from subsidiary disposal"),
]

FCF_DEFINITIONS = {
    "fcf_simple": "CFO − cash capex (购建固定/无形/长期资产支付的现金)",
    "fcf_after_disposals": "CFO − cash capex + asset disposal proceeds "
                           "(处置固定/无形/长期资产收回的现金净额)",
}

NI_NEAR_ZERO_FRAC = 0.02  # |NI| < 2% of CFO scale -> conversion suppressed


def _annual_cf_facts(facts: pd.DataFrame) -> pd.DataFrame:
    return facts[
        (facts.statement == "cashflow") & (facts.report_type == "1")
        & (facts.period_kind == "cumulative") & (facts.value_type == "reported")
        & facts.end_date.str.endswith("1231")
    ]


def build_bridge(facts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (bridge_long, summary_wide) for one company, annual.

    bridge_long: ordered steps per year for waterfall rendering.
    summary_wide: CFO/FCF variants, conversion metrics, check residuals.
    """
    cf = _annual_cf_facts(facts)
    inc = facts[
        (facts.statement == "income") & (facts.report_type == "1")
        & (facts.period_kind == "cumulative")
        & (facts.value_type == "reported") & facts.end_date.str.endswith("1231")
    ]
    ni_is = {r.end_date: r.value for r in
             inc[inc.concept == "net_income_total"].itertuples()}

    bridge_rows, summary_rows = [], []
    for end_date, g in cf.groupby("end_date"):
        vals = dict(zip(g.concept, g.value))
        cfo_direct = vals.get("cfo", np.nan)
        capex = vals.get("capex_paid", np.nan)
        disposals = vals.get("cash_from_asset_disposals", np.nan)
        flags = []

        ni_supp = vals.get("supp_net_profit", np.nan)
        cfo_indirect = vals.get("supp_cfo_indirect", np.nan)
        if pd.isna(ni_supp) or pd.isna(cfo_indirect):
            flags.append("supplemental_not_disclosed")
            bridge_total = np.nan
            c1 = np.nan
        else:
            order = 0
            bridge_rows.append(dict(
                end_date=end_date, step_order=order, concept="supp_net_profit",
                label="Net income (supplemental)", value=ni_supp,
                step_kind="start"))
            bridge_total = ni_supp
            for concept, label in BRIDGE_STEPS:
                v = vals.get(concept)
                if v is None or pd.isna(v):
                    continue  # not disclosed that year -> no bar, no zero
                order += 1
                bridge_rows.append(dict(
                    end_date=end_date, step_order=order, concept=concept,
                    label=label, value=v, step_kind="adjustment"))
                bridge_total += v
            order += 1
            bridge_rows.append(dict(
                end_date=end_date, step_order=order, concept="supp_cfo_indirect",
                label="CFO (indirect, reported)", value=cfo_indirect,
                step_kind="total"))
            c1 = bridge_total - cfo_indirect

        c0 = (ni_supp - ni_is.get(end_date, np.nan))
        c2 = (cfo_indirect - cfo_direct
              if not pd.isna(cfo_indirect) and not pd.isna(cfo_direct) else np.nan)

        fcf_simple = (cfo_direct - capex
                      if not pd.isna(cfo_direct) and not pd.isna(capex) else np.nan)
        fcf_after_disp = (fcf_simple + disposals
                          if not pd.isna(fcf_simple) and not pd.isna(disposals)
                          else np.nan)
        ni = ni_is.get(end_date, np.nan)
        if pd.isna(ni) or abs(ni) < NI_NEAR_ZERO_FRAC * max(abs(cfo_direct), 1.0):
            conversion = np.nan
            if not pd.isna(ni):
                flags.append("ni_near_zero_suppressed")
        else:
            conversion = cfo_direct / ni
        summary_rows.append(dict(
            end_date=end_date, ni_total=ni, cfo=cfo_direct, capex_paid=capex,
            asset_disposal_proceeds=disposals,
            fcf_simple=fcf_simple, fcf_after_disposals=fcf_after_disp,
            fcf_simple_def=FCF_DEFINITIONS["fcf_simple"],
            fcf_after_disposals_def=FCF_DEFINITIONS["fcf_after_disposals"],
            cash_conversion=conversion, accruals=ni - cfo_direct,
            c0_supp_vs_is_ni=c0, c1_bridge_residual=c1,
            c2_indirect_vs_direct=c2, cf_flags=",".join(flags),
        ))
    bridge = pd.DataFrame(
        bridge_rows, columns=["end_date", "step_order", "concept", "label",
                              "value", "step_kind"])
    summary = pd.DataFrame(summary_rows).sort_values("end_date").reset_index(drop=True)
    return bridge, summary


def build_cash_reconciliation(store: Store, ts_code: str) -> dict:
    facts = store.con.execute(
        "SELECT * FROM std_facts WHERE ts_code = ?", [ts_code]).df()
    if facts.empty:
        raise RuntimeError(f"No std_facts for {ts_code}; run `map` first.")
    bridge, summary = build_bridge(facts)
    bridge.insert(0, "ts_code", ts_code)
    summary.insert(0, "ts_code", ts_code)
    for table, df in [("cash_bridge_annual", bridge),
                      ("cash_summary_annual", summary)]:
        store.con.register("_df", df)
        exists = store.con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
            [table]).fetchall()[0][0]
        if exists:
            store.con.execute(f"DELETE FROM {table} WHERE ts_code = ?", [ts_code])
            store.con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM _df")
        else:
            store.con.execute(f"CREATE TABLE {table} AS SELECT * FROM _df")
        store.con.unregister("_df")
    return {"bridge": bridge, "summary": summary}
