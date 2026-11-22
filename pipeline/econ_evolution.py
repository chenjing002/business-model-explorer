"""Module 8 extension — annual evolution of the economics map (begin → end).

Tracks every Map L1/L2 balance group from opening to closing balance and
articulates the year's change against DISCLOSED flows only:

    begin + Σ disclosed flows + inferred residual = end   (exact by construction)

Disclosed flows are reported lines — cash-flow statement, indirect-method
supplemental disclosure, income statement — each tagged with its basis.
The residual is an explicitly labeled balancing item: it is NEVER a claim
that a balance-sheet difference equals a direct asset conversion. Scope
differences between disclosed lines and balance groups (e.g. supplemental
"operating receivables" vs this app's receivables group) are stated in
notes and left visible in the residual, not forced to zero.

Articulation panels group balance items at the grain the DISCLOSURE
supports: PP&E/CIP and intangibles share one panel because cash capex is
one combined reported line; the three operating-liability groups share one
panel because the supplemental payables line is combined.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .economics_map import (CUSTOMER_ADVANCES, INTANGIBLES_GROUP, INVENTORY,
                            PPE_GROUP, RECEIVABLES_PREPAY, SUPPLIER_CREDIT,
                            _comp_sum)
from .store import Store

GROUPS = [
    # (side, group_id, label — identical to the Map node labels, panel_id)
    ("employment", "inventory", "Inventory", "inventory"),
    ("employment", "receivables_prepaid", "Receivables & prepayments",
     "receivables_prepaid"),
    ("employment", "ppe_cip", "PP&E & construction", "long_term_operating"),
    ("employment", "intangibles_other_lt", "Intangibles & other LT operating",
     "long_term_operating"),
    ("employment", "other_operating_assets", "Other operating assets",
     "other_operating_assets"),
    ("employment", "financial_assets", "Financial assets", "financial_assets"),
    ("sources", "common_equity", "Common equity", "common_equity"),
    ("sources", "minority_interests", "Minority interests",
     "minority_interests"),
    ("sources", "financial_debt", "Financial debt", "financial_debt"),
    ("sources", "supplier_credit", "Supplier credit", "operating_liabilities"),
    ("sources", "customer_advances", "Customer advances",
     "operating_liabilities"),
    ("sources", "other_operating_liabilities", "Other operating liabilities",
     "operating_liabilities"),
]

PANEL_LABELS = {
    "inventory": "Inventory",
    "receivables_prepaid": "Receivables & prepayments",
    "long_term_operating": "Long-term operating assets",
    "other_operating_assets": "Other operating assets",
    "financial_assets": "Financial assets",
    "common_equity": "Common equity",
    "minority_interests": "Minority interests",
    "financial_debt": "Financial debt",
    "operating_liabilities": "Operating liabilities (combined)",
}
PANEL_SIDE = {p: s for s, _, _, p in GROUPS}
PANEL_MEMBERS: dict[str, list[str]] = {}
for _s, _g, _l, _p in GROUPS:
    PANEL_MEMBERS.setdefault(_p, []).append(_g)

# ---- notes carried verbatim to the UI (translated there) ----
NOTE_SUPP_INV = ("Indirect-method supplemental line; its scope can differ "
                 "from this balance group — the difference stays in the "
                 "inferred residual.")
NOTE_SUPP_RECV = ("Supplemental 'operating receivables' scope differs from "
                  "this group (e.g. finance-subsidiary placements) — the "
                  "difference stays in the inferred residual.")
NOTE_SUPP_PAY = ("Supplemental 'operating payables' covers supplier credit, "
                 "customer advances and salary/tax payables combined — not "
                 "separable by group, so it is compared against the three "
                 "groups' combined change.")
NOTE_CAPEX_COMBINED = ("Cash paid for fixed assets, intangibles and other LT "
                       "assets is one combined reported line — not separable "
                       "by asset type.")
NOTE_DISPOSAL = ("Cash proceeds, not the book value removed; disposal "
                 "gains/losses and impairments remain in the residual.")
NOTE_CASH_IDENTITY = ("= CFO + CFI + CFF + FX effect, per the reported "
                      "cash-flow statement.")
NOTE_DEPOSITS = ("Net increase in finance-subsidiary deposits taken — "
                 "disclosed within operating cash flow, classified here as a "
                 "financial obligation (judgmental).")
NOTE_PANEL_LT = ("PP&E/construction and intangibles are articulated together "
                 "because disclosed capex is a combined line.")
RES_GENERIC = ("Balance delta minus disclosed flows: undisclosed movements, "
               "reclassifications and measurement changes — an inferred "
               "balancing item, NOT a direct conversion.")
RES_EQUITY = ("Mainly dividends to shareholders (not separable from the CAS "
              "combined dividends+interest cash line), share changes and "
              "other comprehensive income — inferred net amount.")
RES_FA = ("Non-cash financial assets (investments, restricted and finance-"
          "subsidiary deposits) and the cash-equivalents vs monetary-funds "
          "scope difference — inferred.")

RESIDUAL_LABEL = "Undisclosed movements (inferred)"
RESIDUAL_NOTES = {"common_equity": RES_EQUITY, "financial_assets": RES_FA}


def _nz(v) -> float:
    return 0.0 if v is None or pd.isna(v) else float(v)


# Groups summed from classified line items. No lines in a year whose statement
# exists = a structural zero: _balances already counts it as 0 inside the
# "other" group of that year, so the opening→closing delta must too (else the
# group's whole closing balance drops out of E1/E2 — 215 company-years on the
# first full A-share run, e.g. 920799.BJ 2015 with no 预收款项 in 2014).
COMPONENT_GROUPS = {"supplier_credit", "customer_advances", "inventory",
                    "receivables_prepaid", "ppe_cip", "intangibles_other_lt"}


def _balances(b, cy: pd.DataFrame) -> dict[str, float]:
    """Group balances for one year — mirrors the Map's L1/L2 node values."""
    ol = cy[cy.effective_class == "operating_liability"]
    oa = cy[cy.effective_class == "operating_asset"]
    supplier = _comp_sum(ol, SUPPLIER_CREDIT)
    advances = _comp_sum(ol, CUSTOMER_ADVANCES)
    inv = _comp_sum(oa, INVENTORY)
    recv = _comp_sum(oa, RECEIVABLES_PREPAY)
    ppe = _comp_sum(oa, PPE_GROUP)
    intang = _comp_sum(oa, INTANGIBLES_GROUP)
    return {
        "common_equity": b.cse_calc,
        "minority_interests": b.minority_interests,
        "financial_debt": b.fo,
        "supplier_credit": supplier,
        "customer_advances": advances,
        "other_operating_liabilities": b.ol - _nz(supplier) - _nz(advances),
        "inventory": inv,
        "receivables_prepaid": recv,
        "ppe_cip": ppe,
        "intangibles_other_lt": intang,
        "other_operating_assets":
            b.oa - sum(_nz(v) for v in [inv, recv, ppe, intang]),
        "financial_assets": b.fa,
    }


def _panel_items(panel_id: str, cfy: dict, ni_parent, ni_total) -> list[dict]:
    """Disclosed flow items per panel, signed as contributions to the
    balance increase. Missing lines are SKIPPED (never silently zero) —
    the residual then carries them, as its note says."""
    def it(concept, label, value, basis, note=""):
        if value is None or pd.isna(value):
            return None
        return dict(concept=concept, label=label, value=float(value),
                    basis=basis, note=note)

    g = cfy.get
    if panel_id == "inventory":
        raw = [it("inventory_change_supp",
                  "Inventory change (supplemental disclosure)",
                  -g("supp_inventory_decrease", np.nan),
                  "disclosed_supplemental", NOTE_SUPP_INV)]
    elif panel_id == "receivables_prepaid":
        raw = [it("operating_receivables_change_supp",
                  "Operating receivables change (supplemental disclosure)",
                  -g("supp_operating_receivables_decrease", np.nan),
                  "disclosed_supplemental", NOTE_SUPP_RECV)]
    elif panel_id == "long_term_operating":
        dep = [g(c) for c in ("supp_depreciation",
                              "supp_rou_asset_depreciation")]
        dep = [v for v in dep if v is not None and not pd.isna(v)]
        amort = [g(c) for c in ("supp_intangible_amortization",
                                "supp_lt_deferred_amortization")]
        amort = [v for v in amort if v is not None and not pd.isna(v)]
        raw = [
            it("capex_paid", "Cash capex (reported)",
               g("capex_paid", np.nan), "disclosed_cashflow",
               NOTE_CAPEX_COMBINED),
            it("depreciation_disclosed", "Depreciation (disclosed)",
               -sum(dep) if dep else np.nan, "disclosed_supplemental"),
            it("amortization_disclosed", "Amortization (disclosed)",
               -sum(amort) if amort else np.nan, "disclosed_supplemental"),
            it("asset_disposal_proceeds", "Asset disposal proceeds (cash)",
               -g("cash_from_asset_disposals", np.nan),
               "disclosed_cashflow", NOTE_DISPOSAL),
        ]
    elif panel_id == "other_operating_assets":
        raw = []  # no separable disclosed flows — change is wholly inferred
    elif panel_id == "financial_assets":
        raw = [it("net_increase_in_cash",
                  "Net increase in cash & equivalents (reported)",
                  g("net_increase_in_cash", np.nan),
                  "disclosed_cashflow", NOTE_CASH_IDENTITY)]
    elif panel_id == "common_equity":
        raw = [it("ni_parent",
                  "Net income attributable to parent (reported)",
                  ni_parent, "disclosed_income")]
    elif panel_id == "minority_interests":
        ni_min = (ni_total - ni_parent
                  if not pd.isna(ni_total) and not pd.isna(ni_parent)
                  else np.nan)
        raw = [
            it("ni_minority", "Net income to minority (reported)",
               ni_min, "disclosed_income"),
            it("minority_equity_contributions",
               "Minority capital contributions (reported)",
               g("minority_equity_contributions", np.nan),
               "disclosed_cashflow"),
            it("dividends_paid_to_minority",
               "Dividends paid to minority (reported)",
               -g("dividends_paid_to_minority", np.nan),
               "disclosed_cashflow"),
        ]
    elif panel_id == "financial_debt":
        raw = [
            it("cash_from_borrowings", "Cash from borrowings (reported)",
               g("cash_from_borrowings", np.nan), "disclosed_cashflow"),
            it("debt_repayments", "Debt repayments (reported)",
               -g("debt_repayments", np.nan), "disclosed_cashflow"),
            it("net_increase_deposits_taken",
               "Net deposits taken (reported)",
               g("net_increase_deposits_taken", np.nan),
               "disclosed_cashflow", NOTE_DEPOSITS),
        ]
    elif panel_id == "operating_liabilities":
        raw = [it("operating_payables_change_supp",
                  "Operating payables change (supplemental disclosure)",
                  g("supp_operating_payables_increase", np.nan),
                  "disclosed_supplemental", NOTE_SUPP_PAY)]
    else:  # pragma: no cover
        raise ValueError(panel_id)
    return [x for x in raw if x is not None]


def compute_econ_evolution(
    bs: pd.DataFrame, is_: pd.DataFrame, comp: pd.DataFrame,
    cf_facts: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Pure assembly for one company. Returns (groups, flows, checks)."""
    bs = bs[bs.end_date.str.endswith("1231")].sort_values("end_date")
    isa = is_[(is_.period_kind == "cumulative")
              & is_.end_date.str.endswith("1231")]
    comp = comp[comp.end_date.str.endswith("1231")]
    cf = cf_facts[
        (cf_facts.statement == "cashflow") & (cf_facts.report_type == "1")
        & (cf_facts.period_kind == "cumulative")
        & (cf_facts.value_type == "reported")
        & cf_facts.end_date.str.endswith("1231")
    ]

    bs_by_year = {r.end_date[:4]: r for r in bs.itertuples()}
    is_by_year = {r.end_date[:4]: r for r in isa.itertuples()}
    cf_by_year = {y: dict(zip(g.concept, g.value))
                  for y, g in cf.groupby(cf.end_date.str[:4])}

    group_rows, flow_rows, check_rows = [], [], []
    for year in sorted(bs_by_year):
        cur = bs_by_year[year]
        prev = bs_by_year.get(str(int(year) - 1))
        ts, ed = cur.ts_code, cur.end_date
        gc = _balances(cur, comp[comp.end_date == ed])

        if prev is None:
            for side, gid, label, panel in GROUPS:
                group_rows.append(dict(
                    ts_code=ts, end_date=ed, side=side, group_id=gid,
                    label=label, panel_id=panel, begin_value=np.nan,
                    end_value=gc[gid], delta=np.nan,
                    delta_share_of_assets=np.nan,
                    evo_flags="no_opening_balance"))
            continue

        gp = _balances(prev, comp[comp.end_date == prev.end_date])
        ta_begin = prev.total_assets_reported
        cfy = cf_by_year.get(year, {})
        r = is_by_year.get(year)
        ni_parent = r.ni_parent if r is not None else np.nan
        ni_total = r.ni_total if r is not None else np.nan

        side_delta = {"sources": 0.0, "employment": 0.0}
        for side, gid, label, panel in GROUPS:
            begin, end = gp[gid], gc[gid]
            flags = []
            if gid in COMPONENT_GROUPS and pd.isna(begin) != pd.isna(end):
                if pd.isna(begin):
                    begin = 0.0
                    flags.append("group_absent_begin")
                else:
                    end = 0.0
                    flags.append("group_absent_end")
            if pd.isna(begin) or pd.isna(end):
                delta = np.nan
                flags.append("balance_not_disclosed")
            else:
                delta = end - begin
                side_delta[side] += delta
            share = (delta / ta_begin
                     if not pd.isna(delta) and not pd.isna(ta_begin)
                     and ta_begin > 0 else np.nan)
            group_rows.append(dict(
                ts_code=ts, end_date=ed, side=side, group_id=gid,
                label=label, panel_id=panel, begin_value=begin,
                end_value=end, delta=delta, delta_share_of_assets=share,
                evo_flags=",".join(flags)))

        d_ta = cur.total_assets_reported - ta_begin
        check_rows += [
            dict(ts_code=ts, end_date=ed,
                 check="E1_sources_delta_vs_reported_assets",
                 residual=side_delta["sources"] - d_ta),
            dict(ts_code=ts, end_date=ed,
                 check="E2_employment_delta_vs_reported_assets",
                 residual=side_delta["employment"] - d_ta),
        ]

        for panel, members in PANEL_MEMBERS.items():
            begin = sum(_nz(gp[m]) for m in members)
            end = sum(_nz(gc[m]) for m in members)
            items = _panel_items(panel, cfy, ni_parent, ni_total)
            residual = (end - begin) - sum(x["value"] for x in items)
            start_note = NOTE_PANEL_LT if panel == "long_term_operating" else ""
            steps = (
                [dict(concept="opening_balance", label="Opening balance",
                      value=begin, step_kind="start", basis="balance",
                      note=start_note)]
                + [dict(step_kind="adjustment", **x) for x in items]
                + [dict(concept="inferred_residual", label=RESIDUAL_LABEL,
                        value=residual, step_kind="adjustment",
                        basis="inferred_residual",
                        note=RESIDUAL_NOTES.get(panel, RES_GENERIC)),
                   dict(concept="closing_balance", label="Closing balance",
                        value=end, step_kind="total", basis="balance",
                        note="")]
            )
            for order, s in enumerate(steps):
                flow_rows.append(dict(
                    ts_code=ts, end_date=ed, side=PANEL_SIDE[panel],
                    panel_id=panel, panel_label=PANEL_LABELS[panel],
                    step_order=order, **s))
            check_rows.append(dict(
                ts_code=ts, end_date=ed, check=f"E3_panel_additive_{panel}",
                residual=begin + sum(
                    s["value"] for s in steps
                    if s["step_kind"] == "adjustment") - end))

        cb, ce = cfy.get("cash_beginning", np.nan), cfy.get("cash_ending", np.nan)
        dc = cfy.get("net_increase_in_cash", np.nan)
        check_rows.append(dict(
            ts_code=ts, end_date=ed, check="E4_cash_rollforward",
            residual=(ce - cb) - dc
            if not any(pd.isna(v) for v in (cb, ce, dc)) else np.nan))

    groups = pd.DataFrame(group_rows, columns=[
        "ts_code", "end_date", "side", "group_id", "label", "panel_id",
        "begin_value", "end_value", "delta", "delta_share_of_assets",
        "evo_flags"])
    flows = pd.DataFrame(flow_rows, columns=[
        "ts_code", "end_date", "side", "panel_id", "panel_label",
        "step_order", "concept", "label", "value", "step_kind", "basis",
        "note"])
    checks = pd.DataFrame(check_rows, columns=[
        "ts_code", "end_date", "check", "residual"])
    return groups, flows, checks


def build_econ_evolution(store: Store, ts_code: str) -> dict:
    bs = store.con.execute(
        "SELECT * FROM reformulated_bs WHERE ts_code = ?", [ts_code]).df()
    is_ = store.con.execute(
        "SELECT * FROM reformulated_is WHERE ts_code = ?", [ts_code]).df()
    comp = store.con.execute(
        "SELECT * FROM reformulated_bs_components WHERE ts_code = ?",
        [ts_code]).df()
    cf_facts = store.con.execute(
        "SELECT * FROM std_facts WHERE ts_code = ? AND statement='cashflow'",
        [ts_code]).df()
    if bs.empty:
        raise RuntimeError(
            f"No reformulated data for {ts_code}; run `reformulate` first.")
    groups, flows, checks = compute_econ_evolution(bs, is_, comp, cf_facts)
    for table, df in [("econ_evolution_groups", groups),
                      ("econ_evolution_flows", flows),
                      ("econ_evolution_checks", checks)]:
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
    return {"groups": groups, "flows": flows, "checks": checks}
