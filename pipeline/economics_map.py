"""Module 8 — Business Economics Map: node/check assembly (annual).

Five layers of the economic engine per year. All values, components and
identity residuals are computed HERE; the frontend only renders them and
joins declared `related` metric keys against already-exported tables.
Relations are accounting identities or definitions — never causal claims.

Layer identities (residuals reported, never forced):
  L1  CSE + MI + FO + OL                     = total assets (funding view)
  L2  inv + recv + ppe + intang + otherOA+FA = total assets (employment view)
  L4  NI + noncash + ΔOWC                    = CFO   (the reported bridge)
  L5  CFO + CFI + CFF + FX                   = Δcash (reported statement)
L3 consistency is Module 3's R4 (carried through as the layer check).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .store import Store

SUPPLIER_CREDIT = {"accounts_payable", "payables_combined", "notes_payable"}
CUSTOMER_ADVANCES = {"advances_from_customers", "contract_liabilities"}
INVENTORY = {"inventory"}
RECEIVABLES_PREPAY = {"notes_receivable", "accounts_receivable",
                      "receivables_combined", "receivables_financing",
                      "contract_assets", "other_receivables",
                      "other_receivables_combined", "prepayments",
                      "dividends_receivable"}
PPE_GROUP = {"ppe", "ppe_combined", "construction_in_progress", "cip_combined",
             "construction_materials", "right_of_use_assets",
             "assets_held_for_disposal"}
INTANGIBLES_GROUP = {"intangible_assets", "goodwill", "development_expenditure",
                     "long_term_deferred_expenses"}
OWC_BRIDGE_STEPS = {"supp_inventory_decrease",
                    "supp_operating_receivables_decrease",
                    "supp_operating_payables_increase"}

CAPEX_NOTE = ("Cash capex as reported. The maintenance-vs-growth split is NOT "
              "knowable from financial statements; any split is an assumption.")
DIV_NOTE = ("CAS combined line 分配股利、利润或偿付利息支付的现金 — includes "
            "interest paid; dividends are not separable here.")
OTHER_FIN_NOTE = ("Other financing outflows — may include share buybacks and "
                  "lease payments; composition not separable from this line.")


def _node(ts_code, end_date, layer, layer_name, node_id, label, value,
          kind, components=None, note="", related=None):
    return dict(ts_code=ts_code, end_date=end_date, layer=layer,
                layer_name=layer_name, node_id=node_id, label=label,
                value=None if value is None or pd.isna(value) else float(value),
                flow_or_stock=kind,
                components_json=json.dumps(components or [], ensure_ascii=False),
                note=note, related_json=json.dumps(related or []))


def _comp_list(comp_df, concepts):
    sel = comp_df[comp_df.concept.isin(concepts)]
    return [{"concept": r.concept, "value": r.value} for r in sel.itertuples()]


def _comp_sum(comp_df, concepts):
    sel = comp_df[comp_df.concept.isin(concepts)]
    return sel.value.sum() if not sel.empty else np.nan


def build_econ_map(store: Store, ts_code: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    bs = store.con.execute(
        "SELECT * FROM reformulated_bs WHERE ts_code=? AND end_date LIKE '%1231'",
        [ts_code]).df()
    is_ = store.con.execute(
        "SELECT * FROM reformulated_is WHERE ts_code=? AND period_kind='cumulative' "
        "AND end_date LIKE '%1231'", [ts_code]).df()
    comp = store.con.execute(
        "SELECT * FROM reformulated_bs_components WHERE ts_code=? AND end_date LIKE '%1231'",
        [ts_code]).df()
    bridge = store.con.execute(
        "SELECT * FROM cash_bridge_annual WHERE ts_code=?", [ts_code]).df()
    cash = store.con.execute(
        "SELECT * FROM cash_summary_annual WHERE ts_code=?", [ts_code]).df()
    cf_facts = store.con.execute(
        "SELECT * FROM std_facts WHERE ts_code=? AND statement='cashflow' "
        "AND period_kind='cumulative' AND value_type='reported' "
        "AND report_type='1' AND end_date LIKE '%1231'", [ts_code]).df()
    inc_facts = store.con.execute(
        "SELECT * FROM std_facts WHERE ts_code=? AND statement='income' "
        "AND period_kind='cumulative' AND value_type='reported' "
        "AND report_type='1' AND end_date LIKE '%1231'", [ts_code]).df()

    nodes, checks = [], []
    for b in bs.itertuples():
        ed = b.end_date
        cy = comp[comp.end_date == ed]
        iy = {r.concept: r.value for r in inc_facts[inc_facts.end_date == ed].itertuples()}
        ry = is_[is_.end_date == ed]
        r = ry.iloc[0] if not ry.empty else None
        cfy = {x.concept: x.value for x in cf_facts[cf_facts.end_date == ed].itertuples()}
        br = bridge[bridge.end_date == ed]
        csr = cash[cash.end_date == ed]
        cs = csr.iloc[0] if not csr.empty else None

        # ---- L1 capital sources ----
        ol = cy[cy.effective_class == "operating_liability"]
        oa = cy[cy.effective_class == "operating_asset"]
        supplier = _comp_sum(ol, SUPPLIER_CREDIT)
        advances = _comp_sum(ol, CUSTOMER_ADVANCES)
        other_ol = b.ol - (0 if pd.isna(supplier) else supplier) \
            - (0 if pd.isna(advances) else advances)
        L1 = "Capital sources"
        nodes += [
            _node(ts_code, ed, 1, L1, "common_equity", "Common equity", b.cse_calc,
                  "stock", note="CSE = NOA − NFO − MI (Module 3)",
                  related=["roce_parent", "rotce_direct"]),
            _node(ts_code, ed, 1, L1, "minority_interests", "Minority interests",
                  b.minority_interests, "stock"),
            _node(ts_code, ed, 1, L1, "financial_debt", "Financial debt",
                  b.fo, "stock",
                  components=_comp_list(cy, set(cy.loc[cy.effective_class == "financial_obligation", "concept"])),
                  note="Financial obligations incl. finance-subsidiary deposits (judgmental)"),
            _node(ts_code, ed, 1, L1, "supplier_credit", "Supplier credit",
                  supplier, "stock", components=_comp_list(ol, SUPPLIER_CREDIT),
                  related=["dpo", "dpo_cogs"]),
            _node(ts_code, ed, 1, L1, "customer_advances", "Customer advances",
                  advances, "stock", components=_comp_list(ol, CUSTOMER_ADVANCES),
                  note="预收款项 + 合同负债: customers financing the business",
                  related=["advance_days"]),
            _node(ts_code, ed, 1, L1, "other_operating_liabilities",
                  "Other operating liabilities", other_ol, "stock",
                  note="Salaries, taxes and other operating credit (OL remainder)"),
        ]
        src_sum = sum(0 if pd.isna(v) else v for v in
                      [b.cse_calc, b.minority_interests, b.fo, b.ol])
        checks.append(dict(ts_code=ts_code, end_date=ed, layer=1,
                           check="L1_sources_vs_total_assets",
                           residual=b.total_assets_reported - src_sum))

        # ---- L2 capital employment ----
        inv = _comp_sum(oa, INVENTORY)
        recv = _comp_sum(oa, RECEIVABLES_PREPAY)
        ppe = _comp_sum(oa, PPE_GROUP)
        intang = _comp_sum(oa, INTANGIBLES_GROUP)
        known = sum(0 if pd.isna(v) else v for v in [inv, recv, ppe, intang])
        other_oa = b.oa - known
        L2 = "Capital employment"
        nodes += [
            _node(ts_code, ed, 2, L2, "inventory", "Inventory", inv, "stock",
                  components=_comp_list(oa, INVENTORY),
                  note="Raw materials, work in progress and finished goods tie up capital until sold",
                  related=["dio", "inventory_to_sales"]),
            _node(ts_code, ed, 2, L2, "receivables_prepaid",
                  "Receivables & prepayments", recv, "stock",
                  components=_comp_list(oa, RECEIVABLES_PREPAY),
                  related=["dso"]),
            _node(ts_code, ed, 2, L2, "ppe_cip", "PP&E & construction", ppe,
                  "stock", components=_comp_list(oa, PPE_GROUP),
                  related=["ppe_to_sales", "cip_to_sales"]),
            _node(ts_code, ed, 2, L2, "intangibles_other_lt",
                  "Intangibles & other LT operating", intang, "stock",
                  components=_comp_list(oa, INTANGIBLES_GROUP)),
            _node(ts_code, ed, 2, L2, "other_operating_assets",
                  "Other operating assets", other_oa, "stock",
                  note="Operating assets remainder (incl. deferred tax assets)"),
            _node(ts_code, ed, 2, L2, "financial_assets", "Financial assets",
                  b.fa, "stock",
                  note="Cash and investments — not employed in operations",
                  related=["flev", "nbc"]),
        ]
        emp_sum = sum(0 if pd.isna(v) else v
                      for v in [inv, recv, ppe, intang, other_oa, b.fa])
        checks.append(dict(ts_code=ts_code, end_date=ed, layer=2,
                           check="L2_employment_vs_total_assets",
                           residual=b.total_assets_reported - emp_sum))

        # ---- L3 operating performance ----
        L3 = "Operating performance"
        if r is not None:
            rev, cogs = iy.get("revenue", np.nan), iy.get("cost_of_goods_sold", np.nan)
            gross = rev - cogs if not (pd.isna(rev) or pd.isna(cogs)) else np.nan
            nodes += [
                _node(ts_code, ed, 3, L3, "total_revenue", "Total revenue",
                      r.total_revenue, "flow", related=["ato"]),
                _node(ts_code, ed, 3, L3, "gross_profit", "Gross profit",
                      gross, "flow",
                      note="营业收入 − 营业成本; excludes finance-sub interest lines",
                      related=["gross_margin"]),
                _node(ts_code, ed, 3, L3, "oi_core_pretax",
                      "Core operating income (pretax)", r.oi_core_pretax, "flow",
                      related=["opm_core"]),
                _node(ts_code, ed, 3, L3, "unusual_items", "Unusual items (pretax)",
                      r.unusual_pretax, "flow",
                      note="Nonrecurring: non-operating items, impairments, disposals"),
                _node(ts_code, ed, 3, L3, "oi_after_tax",
                      "Operating income after tax", r.oi_after_tax, "flow",
                      note="NI + NFE×(1−t); t is the statutory-rate assumption",
                      related=["rnoa", "opm"]),
            ]
            checks.append(dict(ts_code=ts_code, end_date=ed, layer=3,
                               check="L3_pretax_classification_residual",
                               residual=r.r4_pretax_residual))

        # ---- L4 cash conversion ----
        L4 = "Cash conversion"
        if not br.empty and cs is not None:
            adj = br[br.step_kind == "adjustment"]
            owc = adj[adj.concept.isin(OWC_BRIDGE_STEPS)].value.sum()
            noncash = adj[~adj.concept.isin(OWC_BRIDGE_STEPS)].value.sum()
            ni = br[br.step_kind == "start"].value.sum()
            nodes += [
                _node(ts_code, ed, 4, L4, "net_income", "Net income", ni, "flow"),
                _node(ts_code, ed, 4, L4, "noncash_addbacks", "Noncash add-backs",
                      noncash, "flow",
                      components=[{"concept": a.concept, "value": a.value}
                                  for a in adj.itertuples()
                                  if a.concept not in OWC_BRIDGE_STEPS]),
                _node(ts_code, ed, 4, L4, "owc_change", "Working capital change",
                      owc, "flow",
                      components=[{"concept": a.concept, "value": a.value}
                                  for a in adj.itertuples()
                                  if a.concept in OWC_BRIDGE_STEPS],
                      note="Negative = cash absorbed into working capital",
                      related=["incr_owc_per_incr_revenue"]),
                _node(ts_code, ed, 4, L4, "cfo", "Cash from operations",
                      cs.cfo, "flow", related=["cash_conversion"]),
                _node(ts_code, ed, 4, L4, "capex", "Cash capex", cs.capex_paid,
                      "flow", note=CAPEX_NOTE),
                _node(ts_code, ed, 4, L4, "fcf_simple", "Free cash flow (simple)",
                      cs.fcf_simple, "flow",
                      note="CFO − capex. Level alone is not a verdict: see drivers."),
            ]
            checks.append(dict(ts_code=ts_code, end_date=ed, layer=4,
                               check="L4_bridge_residual",
                               residual=cs.c1_bridge_residual))

        # ---- L5 capital allocation ----
        L5 = "Capital allocation"
        fx = cfy.get("fx_effect_on_cash", np.nan)
        dcash = cfy.get("net_increase_in_cash", np.nan)
        nodes += [
            _node(ts_code, ed, 5, L5, "capex_alloc", "Reinvestment (capex)",
                  cfy.get("capex_paid"), "flow", note=CAPEX_NOTE,
                  related=["reinvestment_rate", "capex_to_da"]),
            _node(ts_code, ed, 5, L5, "dividends_interest",
                  "Dividends & interest paid",
                  cfy.get("dividends_and_interest_paid"), "flow", note=DIV_NOTE),
            _node(ts_code, ed, 5, L5, "debt_repaid", "Debt repaid",
                  cfy.get("debt_repayments"), "flow"),
            _node(ts_code, ed, 5, L5, "other_financing_out",
                  "Other financing outflows",
                  cfy.get("other_financing_cash_paid"), "flow", note=OTHER_FIN_NOTE),
            _node(ts_code, ed, 5, L5, "equity_raised", "Equity raised",
                  cfy.get("cash_from_equity_issuance"), "flow"),
            _node(ts_code, ed, 5, L5, "net_cash_change", "Net change in cash",
                  dcash, "flow", note="CFO + CFI + CFF + FX effect"),
        ]
        parts = [cfy.get("cfo", np.nan), cfy.get("cfi", np.nan),
                 cfy.get("cff", np.nan), fx]
        l5_res = dcash - sum(parts) if all(not pd.isna(p) for p in [dcash, *parts]) else np.nan
        checks.append(dict(ts_code=ts_code, end_date=ed, layer=5,
                           check="L5_cash_statement_identity", residual=l5_res))

    return pd.DataFrame(nodes), pd.DataFrame(checks)


def build_economics_map(store: Store, ts_code: str) -> dict:
    nodes, checks = build_econ_map(store, ts_code)
    for table, df in [("econ_map_nodes", nodes), ("econ_map_checks", checks)]:
        store.con.register("_df", df)
        exists = store.con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name=?",
            [table]).fetchall()[0][0]
        if exists:
            store.con.execute(f"DELETE FROM {table} WHERE ts_code = ?", [ts_code])
            store.con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM _df")
        else:
            store.con.execute(f"CREATE TABLE {table} AS SELECT * FROM _df")
        store.con.unregister("_df")
    return {"nodes": nodes, "checks": checks}
