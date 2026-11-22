"""Module 3 — Penman reformulation engine.

Balance sheet:  NOA = OA − OL,  NFO = FO − FA,  CSE = NOA − NFO − MI
Income stmt:    OI_after_tax = NI_total + NFE_after_tax,
                NFE_after_tax = NFE_pretax × (1 − t),  t = statutory-rate ASSUMPTION

Conventions (documented, auditable):
- Effective class = YAML default class, overridden per company by
  config/overrides.yml (each override carries a reason).
- Tushare combined presentation fields vs granular fields are resolved per
  period by COALESCE_GROUPS; every choice is recorded in reclass_decisions.
- All cash is classified per YAML default (financial_asset); no invented
  operating-cash split.
- Reconciliation residuals (R1–R4) are computed and REPORTED, never forced
  to zero. Missing inputs leave NaN, never 0.
- IS reformulation works at consolidated/total level (incl. minority claims);
  minority income is carried explicitly.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .config import PROJECT_ROOT
from .mapping import QUARTER_ORDER
from .store import Store
from .validate import ABS_TOL, REL_TOL

DEFAULT_OVERRIDES_PATH = PROJECT_ROOT / "config" / "overrides.yml"
DEFAULT_TAX_RATE = 0.25  # PRC statutory CIT rate; an assumption, reported as such

BS_CLASSES = {"operating_asset", "financial_asset", "operating_liability",
              "financial_obligation"}

# (combined concept, granular members, class used when combined is taken)
COALESCE_GROUPS = [
    ("receivables_combined", ["notes_receivable", "accounts_receivable"], "operating_asset"),
    ("other_receivables_combined", ["other_receivables", "interest_receivable", "dividends_receivable"], "operating_asset"),
    ("ppe_combined", ["ppe", "assets_held_for_disposal"], "operating_asset"),
    ("cip_combined", ["construction_in_progress", "construction_materials"], "operating_asset"),
    ("payables_combined", ["notes_payable", "accounts_payable"], "operating_liability"),
    ("other_payables_combined", ["other_payables", "interest_payable", "dividends_payable"], "operating_liability"),
    ("long_term_payables_combined", ["long_term_payables", "specific_payables"], "operating_liability"),
]

# Income-statement memo ("其中") lines: breakdowns of other lines — never summed.
IS_MEMO_CONCEPTS = {"finance_interest_expense", "finance_interest_income",
                    "noncurrent_asset_disposal_loss"}
# Financing-class concepts and their sign in NFE (+ = expense).
NFE_SIGNS = {"net_finance_expense": +1, "investment_income": -1,
             "fair_value_change_gain": -1, "net_hedging_income": -1,
             "fx_gain": -1}
# Items treated as unusual/nonrecurring within operating income, with their
# sign as a contribution to pretax income.
UNUSUAL_SIGNS = {
    "non_operating_income": +1,
    "non_operating_expenses": -1,
    "asset_impairment_loss": +1,          # see IMPAIRMENT_CONCEPTS
    "credit_impairment_loss": +1,
    "other_asset_impairment_loss": +1,
    "asset_disposal_income": +1,          # income-signed (can be negative)
}
UNUSUAL_CONCEPTS = set(UNUSUAL_SIGNS)
# Impairment lines follow the statement format, which Tushare stores as
# displayed. Old CAS format (to FY2018, incl. 财会〔2018〕15号): the lines sit
# inside 营业总成本, + = loss (expense-signed). 财会〔2019〕6号 format (from the
# 2019 interim report): below operating costs, "损失以'-'号填列" (income-signed).
# All-A-share check (2026-11-21, annual consolidated rows, comp_type 1):
# 2009–2018 资产减值损失 reconciles operating profit only as an expense line
# inside 营业总成本 (≈23k rows, none in the new layout); FY2019+ values are
# 96% negative; 信用减值损失 is 81% positive in FY2018 (early adopters of the
# new financial-instrument standard, old layout) vs ~82% negative from FY2019.
# 2019 interim adoption was mixed (~80% by Q2/Q3, Moutai Q1 old layout).
# The period gives the default; the statement's own 营业总成本 decides when it
# can (see impairment_signs). Per-company `income_sign_by_period` overrides
# take precedence, and any remaining mismatch shows up in R4.
IMPAIRMENT_CONCEPTS = {"asset_impairment_loss", "credit_impairment_loss",
                       "other_asset_impairment_loss"}
NEW_IS_FORMAT_FROM = "20190630"
# 营业总成本 lines other than impairments (both layouts, incl. finance-subsidiary
# cost lines). Insurance cost lines are not all mapped; when present the
# structural test finds no unique match and the period default applies.
TOTAL_COST_LINES = ("cost_of_goods_sold", "interest_expense_fin_sub", "fee_commission_expense",
                    "taxes_and_surcharges", "selling_expenses", "admin_expenses",
                    "rd_expenses", "net_finance_expense", "insurance_reserve_provision")


def unusual_sign(concept: str, end_date: str) -> int:
    if concept in IMPAIRMENT_CONCEPTS and end_date < NEW_IS_FORMAT_FROM:
        return -1
    return UNUSUAL_SIGNS[concept]


def impairment_signs(vals: dict, end_date: str) -> dict[str, int]:
    """Sign of each impairment line as a contribution to pretax income.

    Where a line sits inside 营业总成本 the statement shows how it was stored:
    营业总成本 − other cost lines = Σ(−sign × value). All-A-share check
    (2026-11-21): 213 FY2016–2018 rows stored the loss with the new display
    sign (negative) while 营业总成本 included it as a positive cost — restated
    comparatives — and the period default alone left R4 = 2 × the line.
    The sign combination is used only when exactly one matches; otherwise
    (impairments outside 营业总成本, unmapped cost lines) the period default."""
    present = sorted(c for c in IMPAIRMENT_CONCEPTS if vals.get(c))
    default = {c: unusual_sign(c, end_date) for c in present}
    total = vals.get("total_operating_costs")
    if not present or total is None or pd.isna(total):
        return default
    gap = total - sum(vals.get(c, 0.0) for c in TOTAL_COST_LINES)
    matches = [combo for combo in itertools.product((-1, +1), repeat=len(present))
               if abs(sum(-s * vals[c] for s, c in zip(combo, present)) - gap)
               <= _tol(gap, total)]
    return dict(zip(present, matches[0])) if len(matches) == 1 else default


def _tol(a: float, b: float) -> float:
    return max(ABS_TOL, REL_TOL * max(abs(a), abs(b)))


def load_overrides(path: Path | str = DEFAULT_OVERRIDES_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def effective_class(row, overrides_for_code: dict) -> str:
    stmt_over = overrides_for_code.get(row.statement, {})
    if row.concept in stmt_over:
        return stmt_over[row.concept]["class"]
    return row.penman_class


def _bs_period_frame(facts: pd.DataFrame) -> pd.DataFrame:
    return facts[
        (facts.statement == "balancesheet")
        & (facts.value_type == "reported")
        & (facts.report_type == "1")
    ]


def reformulate_bs(
    facts: pd.DataFrame, overrides: dict
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (reformulated_bs, reclass_decisions, components).

    components holds the RESOLVED per-period line items (post-coalesce,
    post-override) that sum exactly to OA/FA/OL/FO — the auditable bridge
    between reported line items and the reformulated aggregates, and the
    input for turnover decomposition and the driver tree.
    """
    bs = _bs_period_frame(facts)
    rows, decisions, components = [], [], []
    for (ts_code, end_date), g in bs.groupby(["ts_code", "end_date"]):
        ocode = overrides.get(ts_code, {})
        vals = dict(zip(g.concept, g.value))
        cls = {r.concept: effective_class(r, ocode) for r in g.itertuples()}
        for r in g.itertuples():
            if effective_class(r, ocode) != r.penman_class:
                decisions.append(dict(
                    ts_code=ts_code, end_date=end_date, kind="override",
                    concept=r.concept, choice=cls[r.concept],
                    reason=ocode[r.statement][r.concept].get("reason", ""),
                ))
        excluded: set[str] = set()
        # Resolve combined-vs-granular per group, recording the decision.
        for combined, members, group_class in COALESCE_GROUPS:
            comb = vals.get(combined)
            present = [m for m in members if m in vals]
            if comb is None:
                # No combined field this period: granular facts stand on
                # their own — nothing to decide, nothing to record.
                excluded.add(combined)
                continue
            gsum = sum(vals[m] for m in present)
            if present and abs(gsum - comb) <= _tol(gsum, comb):
                excluded.add(combined)
                decisions.append(dict(
                    ts_code=ts_code, end_date=end_date, kind="coalesce",
                    concept=combined, choice="granular_match",
                    reason=f"granular {present} sums to combined"))
            else:
                excluded.update(members)
                cls[combined] = group_class
                decisions.append(dict(
                    ts_code=ts_code, end_date=end_date, kind="coalesce",
                    concept=combined, choice="combined_used",
                    reason=(f"granular {present} sum {gsum:.0f} != combined "
                            f"{comb:.0f}; whole lump classed {group_class} "
                            "(mixed-class judgment)")))

        sums = {c: 0.0 for c in BS_CLASSES}
        for concept, v in vals.items():
            if concept in excluded:
                continue
            c = cls.get(concept)
            if c in BS_CLASSES:
                sums[c] += v
                components.append(dict(
                    ts_code=ts_code, end_date=end_date, concept=concept,
                    effective_class=c, value=v))
        oa, fa = sums["operating_asset"], sums["financial_asset"]
        ol, fo = sums["operating_liability"], sums["financial_obligation"]
        mi = vals.get("minority_interests", np.nan)
        noa, nfo = oa - ol, fo - fa
        pe = vals.get("parent_equity", np.nan)
        if pd.isna(mi):
            mi = vals.get("total_equity", np.nan) - pe
        cse_calc = noa - nfo - mi
        ta = vals.get("total_assets", np.nan)
        tl = vals.get("total_liabilities", np.nan)
        rows.append(dict(
            ts_code=ts_code, end_date=end_date,
            oa=oa, fa=fa, ol=ol, fo=fo, noa=noa, nfo=nfo,
            minority_interests=mi, cse_calc=cse_calc,
            total_assets_reported=ta, total_liabilities_reported=tl,
            parent_equity_reported=pe,
            r1_assets_residual=(ta - oa - fa) if not pd.isna(ta) else np.nan,
            r2_liab_residual=(tl - ol - fo) if not pd.isna(tl) else np.nan,
            r3_cse_residual=(pe - cse_calc) if not pd.isna(pe) else np.nan,
        ))
    decision_cols = ["ts_code", "end_date", "kind", "concept", "choice", "reason"]
    component_cols = ["ts_code", "end_date", "concept", "effective_class", "value"]
    return (pd.DataFrame(rows).sort_values("end_date").reset_index(drop=True),
            pd.DataFrame(decisions, columns=decision_cols),
            pd.DataFrame(components, columns=component_cols))


def reformulate_is(
    facts: pd.DataFrame, overrides: dict, tax_rate: float = DEFAULT_TAX_RATE
) -> pd.DataFrame:
    """Reformulated income statement per (ts_code, end_date, period_kind)."""
    inc = facts[
        (facts.statement == "income")
        & (facts.report_type == "1")
        & (facts.period_kind == "cumulative")
        & (~facts.concept.isin(IS_MEMO_CONCEPTS))
    ]
    rows = []
    for (ts_code, end_date), g in inc.groupby(["ts_code", "end_date"]):
        ocode = overrides.get(ts_code, {})
        vals = dict(zip(g.concept, g.value))
        cls = {r.concept: effective_class(r, ocode) for r in g.itertuples()}
        sign_rules = ocode.get("income_sign_by_period", {}).get(end_date, {})
        impairment = impairment_signs(vals, end_date)
        terms = {k: [] for k in ("oi_core_pretax", "unusual_pretax", "nfe_pretax")}

        def operand(metric, key, sign=1):
            terms[metric].append(f"{'-' if sign < 0 else ''}raw:{key}")

        op_income = op_expense = unusual = nfe_pretax = 0.0
        for concept, v in vals.items():
            c = cls[concept]
            if concept == "associate_investment_income":
                continue  # memo within investment_income
            if (concept == "investment_income" and c == "financing"
                    and cls.get("associate_investment_income") == "operating_income"):
                associate = vals["associate_investment_income"]
                op_income += associate
                v -= associate
                operand("oi_core_pretax", "associate_investment_income")
                operand("nfe_pretax", "associate_investment_income", -NFE_SIGNS[concept])
            if c == "financing":
                sign = NFE_SIGNS.get(concept, +1)
                nfe_pretax += sign * v
                operand("nfe_pretax", concept, sign)
            elif concept in UNUSUAL_CONCEPTS:
                sign = sign_rules.get(concept, {}).get(
                    "sign", impairment.get(concept) or unusual_sign(concept, end_date))
                unusual += sign * v
                operand("unusual_pretax", concept, sign)
            elif c == "operating_income":
                op_income += v
                operand("oi_core_pretax", concept)
            elif c == "operating_expense":
                op_expense += v
                operand("oi_core_pretax", concept, -1)

        oi_core_pretax = op_income - op_expense
        oi_pretax = oi_core_pretax + unusual
        pretax_reported = vals.get("pretax_profit", np.nan)
        tax_reported = vals.get("income_tax_expense", np.nan)
        ni_total = vals.get("net_income_total", np.nan)
        # R4: classification completeness against reported pretax profit
        r4 = (pretax_reported - (oi_pretax - nfe_pretax)
              if not pd.isna(pretax_reported) else np.nan)
        # Penman tax allocation at the assumed statutory rate
        nfe_after_tax = nfe_pretax * (1.0 - tax_rate)
        oi_after_tax = (ni_total + nfe_after_tax
                        if not pd.isna(ni_total) else np.nan)
        unusual_after_tax = unusual * (1.0 - tax_rate)
        rows.append(dict(
            ts_code=ts_code, end_date=end_date, period_kind="cumulative",
            revenue=vals.get("revenue", np.nan),
            total_revenue=vals.get("total_revenue", np.nan),
            oi_core_pretax=oi_core_pretax, unusual_pretax=unusual,
            unusual_after_tax=unusual_after_tax,
            oi_pretax=oi_pretax, nfe_pretax=nfe_pretax,
            tax_reported=tax_reported, tax_rate_assumed=tax_rate,
            nfe_after_tax=nfe_after_tax, oi_after_tax=oi_after_tax,
            oi_core_after_tax=(oi_after_tax - unusual_after_tax
                               if not pd.isna(oi_after_tax) else np.nan),
            ni_total=ni_total,
            ni_parent=vals.get("net_income_parent", np.nan),
            minority_income=vals.get("minority_income", np.nan),
            comprehensive_income_total=vals.get("total_comprehensive_income", np.nan),
            comprehensive_income_parent=vals.get("comprehensive_income_parent", np.nan),
            is_terms=json.dumps(terms),
            r4_pretax_residual=r4,
        ))

    # Derive classified flows from adjacent YTD results. A raw line missing in
    # one period still stays missing in std_facts; aggregate quarter values use
    # both actual cumulative reconstructions.
    quarters = []
    by_period = {(r["ts_code"], r["end_date"]): r for r in rows}
    base_fields = {"ts_code", "end_date", "period_kind", "tax_rate_assumed", "is_terms"}
    for row in rows:
        ed = row["end_date"]
        if ed[4:] not in QUARTER_ORDER:
            continue
        pos = QUARTER_ORDER.index(ed[4:])
        quarter = {**row, "period_kind": "single_quarter", "is_terms": None}
        if pos:
            earlier = by_period.get((row["ts_code"], ed[:4] + QUARTER_ORDER[pos - 1]))
            if earlier is None:
                continue
            for field in row.keys() - base_fields:
                quarter[field] -= earlier[field]
        quarters.append(quarter)
    return pd.DataFrame(rows + quarters).sort_values(["period_kind", "end_date"]).reset_index(drop=True)


def build_reformulated(
    store: Store, ts_code: str,
    overrides_path: Path | str = DEFAULT_OVERRIDES_PATH,
    tax_rate: float = DEFAULT_TAX_RATE,
) -> dict:
    """Rebuild reformulated_bs / reformulated_is / reclass_decisions tables."""
    facts = store.con.execute(
        "SELECT * FROM std_facts WHERE ts_code = ?", [ts_code]
    ).df()
    if facts.empty:
        raise RuntimeError(f"No std_facts for {ts_code}; run `map` first.")
    overrides = load_overrides(overrides_path)
    bs, decisions, components = reformulate_bs(facts, overrides)
    is_ = reformulate_is(facts, overrides, tax_rate)
    for table, df in [("reformulated_bs", bs), ("reformulated_is", is_),
                      ("reclass_decisions", decisions),
                      ("reformulated_bs_components", components)]:
        store.con.register("_df", df)
        exists = store.con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
            [table]).fetchall()[0][0]
        if exists:
            if table == "reformulated_is":
                for column, sql_type in [
                    ("comprehensive_income_parent", "DOUBLE"),
                    ("unusual_after_tax", "DOUBLE"),
                    ("is_terms", "VARCHAR"),
                ]:
                    store.con.execute(
                        f"ALTER TABLE reformulated_is ADD COLUMN IF NOT EXISTS {column} {sql_type}")
            store.con.execute(f"DELETE FROM {table} WHERE ts_code = ?", [ts_code])
            store.con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM _df")
        else:
            store.con.execute(f"CREATE TABLE {table} AS SELECT * FROM _df")
        store.con.unregister("_df")
    return {"bs": bs, "is": is_, "decisions": decisions}
