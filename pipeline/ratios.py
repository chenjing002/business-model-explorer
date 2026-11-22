"""Module 4 — Nissim–Penman profitability decomposition (annual).

Level: TOTAL equity (TE = NOA − NFO = equity incl. minority), where the
leverage identity is exact:
    ROTCE = RNOA + FLEV × (RNOA − NBC)
Parent ROCE (NI_parent / CSE) is reported separately WITHOUT the identity —
minority interests prevent the simplified decomposition.

Capital bases: 'average' ((begin+end)/2) and 'opening' (begin), one row each.
First year has no opening balance → ratios NaN, flagged (never imputed).

Denominator guards (never emit a misleading percentage):
- |NOA capital| < NEAR_ZERO_FRAC × revenue → RNOA/ATO/OLLEV suppressed, flagged
- |NFO capital| < NEAR_ZERO_FRAC × revenue → NBC/spread/FLEV-identity
  suppressed, flagged (ROTCE direct still reported)
- NFO < 0 flagged informational: company holds net financial assets.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .store import Store

NEAR_ZERO_FRAC = 0.05  # capital smaller than 5% of revenue -> ratio suppressed

# ATO decomposition components: resolved concept -> short name.
ATO_COMPONENTS = {
    "inventory": "inventory",
    "receivables_combined": "receivables",
    "notes_receivable": "receivables",
    "accounts_receivable": "receivables",
    "receivables_financing": "receivables",
    "prepayments": "prepayments",
    "ppe": "ppe",
    "ppe_combined": "ppe",
    "construction_in_progress": "cip",
    "cip_combined": "cip",
    "intangible_assets": "intangibles",
    "right_of_use_assets": "ppe",
    "accounts_payable": "op_payables",
    "payables_combined": "op_payables",
    "notes_payable": "op_payables",
    "contract_liabilities": "customer_advances",
    "advances_from_customers": "customer_advances",
    "employee_benefits_payable": "op_payables",
    "taxes_payable": "op_payables",
}


def _annual(df: pd.DataFrame, date_col: str = "end_date") -> pd.DataFrame:
    return df[df[date_col].str.endswith("1231")].sort_values(date_col)


def compute_ratios(
    bs: pd.DataFrame, is_: pd.DataFrame, components: pd.DataFrame
) -> pd.DataFrame:
    """bs/is_/components: module-3 outputs for one company. Annual ratios."""
    bs = _annual(bs).reset_index(drop=True)
    isa = _annual(is_[is_.period_kind == "cumulative"]).reset_index(drop=True)
    comp = components[components.end_date.str.endswith("1231")]

    bs_by_year = {r.end_date[:4]: r for r in bs.itertuples()}
    comp_by_year = {
        y: g.groupby(g.concept.map(ATO_COMPONENTS))["value"].sum()
        for y, g in comp.groupby(comp.end_date.str[:4])
    }
    rows = []
    for r in isa.itertuples():
        year = r.end_date[:4]
        cur, prev = bs_by_year.get(year), bs_by_year.get(str(int(year) - 1))
        rev = r.total_revenue
        for basis in ("average", "opening"):
            flags = []
            if cur is None or prev is None:
                rows.append(dict(ts_code=r.ts_code, end_date=r.end_date,
                                 basis=basis, revenue=rev,
                                 ratio_flags="no_opening_balance"))
                continue

            def cap(field):
                b, e = getattr(prev, field), getattr(cur, field)
                return (b + e) / 2 if basis == "average" else b

            noa_c, nfo_c, ol_c = cap("noa"), cap("nfo"), cap("ol")
            te_c = noa_c - nfo_c
            cse_c = cap("cse_calc")
            floor = NEAR_ZERO_FRAC * abs(rev)

            noa_ok = noa_c > 0 and abs(noa_c) >= floor
            nfo_ok = nfo_c != 0 and abs(nfo_c) >= floor
            rev_ok = rev > 0
            if not rev_ok:
                flags.append("non_positive_revenue")
            if not te_c > 0 or not cse_c > 0:
                flags.append("non_positive_equity_capital")
            if not noa_ok:
                flags.append("noa_near_zero_suppressed")
            if not nfo_ok:
                flags.append("nfo_near_zero_suppressed")
            if nfo_c < 0:
                flags.append("net_financial_assets")
            if noa_c < 0:
                flags.append("negative_noa")

            oi, oi_core, nfe = r.oi_after_tax, r.oi_core_after_tax, r.nfe_after_tax
            rnoa = oi / noa_c if noa_ok else np.nan
            opm = oi / rev if rev_ok else np.nan
            opm_core = oi_core / rev if rev_ok else np.nan
            ato = rev / noa_c if noa_ok else np.nan
            ollev = ol_c / noa_c if noa_ok else np.nan
            flev = nfo_c / te_c if te_c > 0 else np.nan
            nbc = nfe / nfo_c if nfo_ok else np.nan
            spread = rnoa - nbc if (noa_ok and nfo_ok) else np.nan
            rotce_direct = r.ni_total / te_c if te_c > 0 else np.nan
            rotce_identity = (rnoa + flev * spread
                              if (noa_ok and nfo_ok) else np.nan)
            roce_parent = r.ni_parent / cse_c if cse_c > 0 else np.nan

            # inverse-turnover decomposition: component capital / revenue
            cprev = comp_by_year.get(str(int(year) - 1), pd.Series(dtype=float))
            ccur = comp_by_year.get(year, pd.Series(dtype=float))
            comp_to_sales = {}
            for name in sorted(set(cprev.index) | set(ccur.index)):
                b, e = cprev.get(name, np.nan), ccur.get(name, np.nan)
                c = (b + e) / 2 if basis == "average" else b
                comp_to_sales[f"{name}_to_sales"] = c / rev if rev_ok else np.nan

            gross_margin = ((r.revenue - r.cogs) / r.revenue
                            if not pd.isna(r.cogs) and r.revenue else np.nan)
            rows.append(dict(
                ts_code=r.ts_code, end_date=r.end_date, basis=basis,
                revenue=rev, oi_after_tax=oi, noa_capital=noa_c,
                nfo_capital=nfo_c, te_capital=te_c,
                rnoa=rnoa, opm=opm, opm_core=opm_core, ato=ato, ollev=ollev,
                flev=flev, nbc=nbc, spread=spread,
                rotce=rotce_identity, rotce_direct=rotce_direct,
                roce_parent=roce_parent, gross_margin=gross_margin,
                **comp_to_sales, ratio_flags=",".join(flags),
            ))
    return pd.DataFrame(rows)


def _attach_is_details(is_: pd.DataFrame, facts: pd.DataFrame) -> pd.DataFrame:
    """Add COGS (for gross margin) from std_facts to the reformulated IS."""
    cogs = facts[
        (facts.statement == "income") & (facts.concept == "cost_of_goods_sold")
        & (facts.report_type == "1")
        & (facts.period_kind == "cumulative") & (facts.value_type == "reported")
    ][["end_date", "value"]].rename(columns={"value": "cogs"})
    return is_.merge(cogs, on="end_date", how="left")


def build_ratios(store: Store, ts_code: str) -> pd.DataFrame:
    bs = store.con.execute(
        "SELECT * FROM reformulated_bs WHERE ts_code = ?", [ts_code]).df()
    is_ = store.con.execute(
        "SELECT * FROM reformulated_is WHERE ts_code = ?", [ts_code]).df()
    components = store.con.execute(
        "SELECT * FROM reformulated_bs_components WHERE ts_code = ?", [ts_code]).df()
    facts = store.con.execute(
        "SELECT * FROM std_facts WHERE ts_code = ?", [ts_code]).df()
    if bs.empty or is_.empty:
        raise RuntimeError(f"No reformulated data for {ts_code}; run `reformulate` first.")
    ratios = compute_ratios(bs, _attach_is_details(is_, facts), components)

    store.con.register("_r", ratios)
    exists = store.con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name='ratios_annual'"
    ).fetchall()[0][0]
    if exists:
        store.con.execute("DELETE FROM ratios_annual WHERE ts_code = ?", [ts_code])
        store.con.execute("INSERT INTO ratios_annual BY NAME SELECT * FROM _r")
    else:
        store.con.execute("CREATE TABLE ratios_annual AS SELECT * FROM _r")
    store.con.unregister("_r")
    return ratios
