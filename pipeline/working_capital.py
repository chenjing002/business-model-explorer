"""Module 5 — Working capital & cash conversion metrics and simulations.

Metrics use AVERAGE balances and a 365-day year. Inputs are the RESOLVED
balance-sheet components (reformulated_bs_components, post-coalesce — no
double counting) plus income facts from std_facts.

DPO caveat: purchases are not disclosed, so DPO uses
purchases ≈ COGS + ΔInventory (method disclosed per row in `dpo_method`);
a COGS-only variant (`dpo_cogs`) is also reported for comparability.

CCC = DIO + DSO − DPO. Customer advances (预收款项 + 合同负债) are reported
as `advance_days` separately — netting them into CCC would hide the
distinction between supplier financing and customer financing. The netted
variant `ccc_net_advances` = CCC − advance_days is exported alongside, never
in place of CCC; it is NaN when either operand is.

Missing component-years yield NaN and a flag; nothing is imputed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .store import Store

DAYS = 365.0
NEAR_ZERO_FRAC = 0.05  # guard for incremental ratios

# Resolved concept -> working-capital group. Trade-specific: other_receivables
# is NOT trade; employee/tax payables are op liabilities but not trade payables.
WC_GROUPS = {
    "inventory": "inventory",
    "notes_receivable": "trade_receivables",
    "accounts_receivable": "trade_receivables",
    "receivables_combined": "trade_receivables",
    "receivables_financing": "trade_receivables",
    "contract_assets": "trade_receivables",
    "prepayments": "prepayments",
    "accounts_payable": "trade_payables",
    "payables_combined": "trade_payables",
    "notes_payable": "trade_payables",
    "advances_from_customers": "customer_advances",
    "contract_liabilities": "customer_advances",
    "employee_benefits_payable": "other_op_payables",
    "taxes_payable": "other_op_payables",
    "other_payables": "other_op_payables",
    "other_payables_combined": "other_op_payables",
    "accrued_expenses": "other_op_payables",
}
OWC_SIGNS = {"inventory": +1, "trade_receivables": +1, "prepayments": +1,
             "trade_payables": -1, "customer_advances": -1,
             "other_op_payables": -1}


def _group_balances(components: pd.DataFrame) -> dict[str, pd.Series]:
    """{year: Series(group -> balance)} from annual resolved components."""
    ann = components[components.end_date.str.endswith("1231")
                     & components.effective_class.isin(["operating_asset", "operating_liability"])]
    return {
        y: g.groupby(g.concept.map(WC_GROUPS))["value"].sum()
        for y, g in ann.groupby(ann.end_date.str[:4])
    }


def compute_wc_metrics(components: pd.DataFrame, income: pd.DataFrame) -> pd.DataFrame:
    """income: std_facts income rows (cumulative, reported).

    Returns one row per fiscal year with days metrics, OWC and increments.
    """
    bal = _group_balances(components)
    inc_ann = income[
        (income.statement == "income") & (income.report_type == "1")
        & (income.period_kind == "cumulative")
        & (income.value_type == "reported")
        & income.end_date.str.endswith("1231")
    ]
    inc_by_year: dict[str, dict] = {
        y: dict(zip(g.concept, g.value))
        for y, g in inc_ann.groupby(inc_ann.end_date.str[:4])
    }
    rows = []
    for year in sorted(inc_by_year):
        prev = str(int(year) - 1)
        iv = inc_by_year[year]
        revenue, cogs = iv.get("revenue", np.nan), iv.get("cost_of_goods_sold", np.nan)
        flags = []
        if prev not in bal or year not in bal:
            rows.append(dict(end_date=f"{year}1231", revenue=revenue,
                             wc_flags="no_opening_balance"))
            continue
        b0, b1 = bal[prev], bal[year]

        def avg(group):
            x, y_ = b0.get(group, np.nan), b1.get(group, np.nan)
            return (x + y_) / 2

        inv_avg = avg("inventory")
        tr_avg = avg("trade_receivables")
        tp_avg = avg("trade_payables")
        adv_avg = avg("customer_advances")

        d_inventory = b1.get("inventory", np.nan) - b0.get("inventory", np.nan)
        purchases = cogs + d_inventory if not pd.isna(cogs) else np.nan

        dio = DAYS * inv_avg / cogs if cogs > 0 else np.nan
        dso = DAYS * tr_avg / revenue if revenue > 0 else np.nan
        if pd.isna(tr_avg):
            flags.append("receivables_not_disclosed")
        dpo = DAYS * tp_avg / purchases if purchases > 0 else np.nan
        dpo_cogs = DAYS * tp_avg / cogs if cogs > 0 else np.nan
        adv_days = DAYS * adv_avg / revenue if revenue > 0 else np.nan
        ccc = dio + dso - dpo
        ccc_net_advances = ccc - adv_days

        disclosed_groups = set(b0.index) | set(b1.index)

        def owc_of(s):
            return sum(OWC_SIGNS[g] * s.get(g, np.nan)
                       for g in OWC_SIGNS if g in disclosed_groups)

        owc0, owc1 = owc_of(b0), owc_of(b1)
        owc_avg = (owc0 + owc1) / 2
        if pd.isna(owc_avg):
            flags.append("owc_components_incomplete")
        d_owc = owc1 - owc0
        rev_prev = inc_by_year.get(prev, {}).get("revenue", np.nan)
        d_rev = revenue - rev_prev if not pd.isna(rev_prev) else np.nan
        if pd.isna(d_rev) or d_rev == 0 or abs(d_rev) < NEAR_ZERO_FRAC * abs(revenue):
            incr_owc_ratio = np.nan
            if not pd.isna(d_rev):
                flags.append("delta_revenue_near_zero_suppressed")
        else:
            incr_owc_ratio = d_owc / d_rev

        rows.append(dict(
            end_date=f"{year}1231", revenue=revenue, cogs=cogs,
            purchases_est=purchases, dpo_method="purchases=COGS+dInventory",
            dio=dio, dso=dso, dpo=dpo, dpo_cogs=dpo_cogs, ccc=ccc,
            advance_days=adv_days, ccc_net_advances=ccc_net_advances,
            inventory_avg=inv_avg, trade_receivables_avg=tr_avg,
            trade_payables_avg=tp_avg, customer_advances_avg=adv_avg,
            owc_begin=owc0, owc_end=owc1, owc_avg=owc_avg,
            owc_pct_sales=owc_avg / revenue if revenue > 0 else np.nan,
            d_owc=d_owc, d_revenue=d_rev, incr_owc_per_incr_revenue=incr_owc_ratio,
            wc_flags=",".join(flags),
        ))
    return pd.DataFrame(rows)


# ----- simulations (pure functions; UI wires to these later) -----

def required_owc(revenue: float, cogs: float, dio: float, dso: float,
                 dpo: float, advance_days: float = 0.0,
                 prepay_days: float = 0.0, other_op_payable_days: float = 0.0,
                 ) -> dict:
    """Balance-sheet working capital implied by days parameters.

    Days definitions mirror compute_wc_metrics: DIO & DPO on COGS-scale
    (purchases ≈ COGS in steady state), DSO & advance days on revenue.
    Operating income is NOT an output: changing turns moves capital, not
    accounting profit — the Amazon 2004 lesson.
    """
    inventory = dio * cogs / DAYS
    receivables = dso * revenue / DAYS
    payables = dpo * cogs / DAYS
    advances = advance_days * revenue / DAYS
    prepaid = prepay_days * cogs / DAYS
    other_pay = other_op_payable_days * revenue / DAYS
    owc = inventory + receivables + prepaid - payables - advances - other_pay
    return dict(inventory=inventory, receivables=receivables,
                prepayments=prepaid, payables=payables, advances=advances,
                other_op_payables=other_pay, owc=owc)


def simulate_efficiency_change(revenue: float, cogs: float,
                               base: dict, new: dict) -> dict:
    """Mode (a): same sales & cost structure, different days parameters.

    base/new: kwargs for required_owc (dio/dso/dpo/advance_days/...).
    capital_released > 0 means the change frees cash.
    """
    owc_base = required_owc(revenue, cogs, **base)
    owc_new = required_owc(revenue, cogs, **new)
    return dict(base=owc_base, new=owc_new,
                capital_released=owc_base["owc"] - owc_new["owc"])


def simulate_growth(revenue0: float, cogs_ratio: float, growth: float,
                    years: int, days: dict) -> pd.DataFrame:
    """Mode (b): constant efficiency (days fixed), revenue grows at `growth`.

    Shows the OWC investment (cash absorbed) required each year just to
    support growth, before any change in operating profitability.
    """
    rows, prev_owc = [], None
    for t in range(years + 1):
        rev = revenue0 * (1 + growth) ** t
        owc = required_owc(rev, rev * cogs_ratio, **days)["owc"]
        rows.append(dict(year=t, revenue=rev, owc_required=owc,
                         wc_investment=np.nan if prev_owc is None
                         else owc - prev_owc))
        prev_owc = owc
    return pd.DataFrame(rows)


def build_working_capital(store: Store, ts_code: str) -> pd.DataFrame:
    components = store.con.execute(
        "SELECT * FROM reformulated_bs_components WHERE ts_code = ?", [ts_code]).df()
    income = store.con.execute(
        "SELECT * FROM std_facts WHERE ts_code = ? AND statement='income'",
        [ts_code]).df()
    if components.empty:
        raise RuntimeError(f"No components for {ts_code}; run `reformulate` first.")
    wc = compute_wc_metrics(components, income)
    wc.insert(0, "ts_code", ts_code)
    store.con.register("_wc", wc)
    exists = store.con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name='working_capital_annual'"
    ).fetchall()[0][0]
    if exists:
        for column in ("owc_begin", "ccc_net_advances"):
            store.con.execute(
                f"ALTER TABLE working_capital_annual ADD COLUMN IF NOT EXISTS {column} DOUBLE")
        store.con.execute("DELETE FROM working_capital_annual WHERE ts_code = ?", [ts_code])
        store.con.execute("INSERT INTO working_capital_annual BY NAME SELECT * FROM _wc")
    else:
        store.con.execute("CREATE TABLE working_capital_annual AS SELECT * FROM _wc")
    store.con.unregister("_wc")
    return wc
