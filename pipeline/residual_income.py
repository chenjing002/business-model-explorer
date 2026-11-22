"""Module 11 — Growth quality & residual income (annual, opening capital).

Residual earnings charge each year's income for the capital in place at the
START of the year (Penman convention), at an explicit required return that
is an ASSUMPTION — stored on every row, never estimated here:

    ReOI_t = OI_t − r_op × NOA_{t−1}          (residual operating income)
    RE_t   = CI_parent_t − r_e × CSE_{t−1}    (common-equity residual earnings)

Value Creation Bridge (waterfall-ready, schema mirrors cash_bridge_annual).
With PM = OI / revenue, ΔReOI = ΔOI − r_op × ΔNOA_begin and the exact split
ΔOI = ΔRev × PM_{t−1} + Rev_t × ΔPM, the margin change itself split into
core and unusual (PM = PM_core + PM_unusual):

    ReOI_{t−1}
      + sales growth at last year's margin     ΔRev × PM_{t−1}
      + core margin change                     Rev_t × ΔPM_core
      + unusual items change                   Rev_t × ΔPM_unusual
      − capital charge on new NOA              r_op × (NOA_{t−1} − NOA_{t−2})
    = ReOI_t

Exact by construction; needs no RNOA, so it also works for negative or tiny
NOA. Sequential splits are order-dependent — the order above (sales first,
at the prior margin) is a stated convention.

Penman drivers (summary columns; only where RNOA is meaningful on both
opening bases — positive and ≥ 5% of revenue, as in Module 4):
    ReOI = (RNOA − r_op) × NOA_begin,  RNOA = PM × ATO,  s = RNOA − r_op
    ΔReOI = (s_t − s_{t−1}) × NOA_{t−1}          profitability effect
              = margin effect   ΔPM × ATO_{t−1} × NOA_{t−1}
              + turnover effect PM_t × ΔATO × NOA_{t−1}
          + s_{t−1} × (NOA_{t−1} − NOA_{t−2})    growth effect
The growth effect values new capital at LAST year's spread; if the new
capital brings no revenue, the turnover effect takes it back. Read them
together.

Checks (reported, never forced): RI1 bridge additive, RI2 driver split
additive, RI3/RI4 opening RNOA / ROCE vs Module 4's ratios_annual.

Required returns are model assumptions. Equity RE uses parent comprehensive
income. Parent ROCE uses net income.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .ratios import NEAR_ZERO_FRAC
from .store import Store

DEFAULT_R_OP = 0.08
DEFAULT_R_E = 0.08

RATE_NOTE = ("Required returns are ASSUMPTIONS (r_op_assumed, r_e_assumed), "
             "not estimates; residual earnings move one-for-one with the "
             "capital charge they imply.")
OCI_NOTE = "剩余权益收益采用归母综合收益。归母净资产收益率仍按归母净利润计算。"

BRIDGE_STEPS = [
    # short labels (waterfall axis); full definitions live in the docstring/UI
    ("sales_effect", "Sales growth"),
    ("core_margin_effect", "Core margin"),
    ("unusual_effect", "Unusual items"),
    ("capital_charge_effect", "Charge on new NOA"),
]


def _nan(v) -> bool:
    return v is None or pd.isna(v)


def compute_residual_income(
    bs: pd.DataFrame, is_: pd.DataFrame, ratios: pd.DataFrame,
    r_op: float = DEFAULT_R_OP, r_e: float = DEFAULT_R_E,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Inputs: Module-3 BS/IS + Module-4 ratios for one company.
    Returns (summary_wide, bridge_long, checks), annual."""
    bs = bs[bs.end_date.str.endswith("1231")].sort_values("end_date")
    isa = is_[(is_.period_kind == "cumulative")
              & is_.end_date.str.endswith("1231")].sort_values("end_date")
    op = ratios[(ratios.basis == "opening")
                & ratios.end_date.str.endswith("1231")]
    bs_by_year = {r.end_date[:4]: r for r in bs.itertuples()}
    m4_by_year = {r.end_date[:4]: r for r in op.itertuples()}

    # pass 1: per-year levels
    lv: dict[str, dict] = {}
    for r in isa.itertuples():
        y = r.end_date[:4]
        cur, prev = bs_by_year.get(y), bs_by_year.get(str(int(y) - 1))
        rev = r.total_revenue
        flags = []
        d = dict(ts_code=r.ts_code, end_date=r.end_date,
                 r_op_assumed=r_op, r_e_assumed=r_e,
                 revenue=rev, oi_after_tax=r.oi_after_tax,
                 oi_core_after_tax=r.oi_core_after_tax,
                 ni_parent=r.ni_parent,
                 oci_total=(r.comprehensive_income_total - r.ni_total
                            if not _nan(r.comprehensive_income_total)
                            else np.nan))
        ok_rev = not _nan(rev) and abs(rev) >= 1.0
        d["pm"] = r.oi_after_tax / rev if ok_rev else np.nan
        d["pm_core"] = r.oi_core_after_tax / rev if ok_rev else np.nan
        d["pm_unusual"] = d["pm"] - d["pm_core"]
        if not ok_rev:
            flags.append("no_revenue")
        if cur is None or prev is None:
            flags.append("no_opening_balance")
            d.update(noa_begin=np.nan, cse_begin=np.nan, capital_charge=np.nan,
                     reoi=np.nan, reoi_core=np.nan, rnoa_open=np.nan,
                     ato_open=np.nan, spread_op=np.nan, equity_charge=np.nan,
                     re_common=np.nan, roce_open=np.nan, spread_e=np.nan)
            d["_flags"] = flags
            lv[y] = d
            continue
        noa_b, cse_b = prev.noa, prev.cse_calc
        floor = NEAR_ZERO_FRAC * abs(rev) if ok_rev else np.inf
        d["noa_begin"] = noa_b
        d["cse_begin"] = cse_b
        d["capital_charge"] = r_op * noa_b
        d["reoi"] = r.oi_after_tax - r_op * noa_b
        d["reoi_core"] = r.oi_core_after_tax - r_op * noa_b
        if noa_b > 0 and abs(noa_b) >= floor:
            d["rnoa_open"] = r.oi_after_tax / noa_b
            d["ato_open"] = rev / noa_b
            d["spread_op"] = d["rnoa_open"] - r_op
        else:
            d["rnoa_open"] = d["ato_open"] = d["spread_op"] = np.nan
            flags.append("negative_noa_base" if noa_b <= 0
                         else "noa_base_near_zero_suppressed")
        d["equity_charge"] = r_e * cse_b
        ci_parent = getattr(r, "comprehensive_income_parent", np.nan)
        d["re_common"] = ci_parent - r_e * cse_b
        if _nan(ci_parent):
            flags.append("comprehensive_income_parent_missing")
        if cse_b > 0:
            d["roce_open"] = r.ni_parent / cse_b
            d["spread_e"] = d["roce_open"] - r_e
        else:
            d["roce_open"] = d["spread_e"] = np.nan
            flags.append("non_positive_cse_base")
        d["_flags"] = flags
        lv[y] = d

    # pass 2: year-on-year bridge, drivers, growth metrics
    summary_rows, bridge_rows, check_rows = [], [], []
    for y in sorted(lv):
        d = lv[y]
        p = lv.get(str(int(y) - 1))
        flags = d.pop("_flags")
        ts, ed = d["ts_code"], d["end_date"]
        out = dict(d)
        for c in ["reoi_prev", "delta_reoi", "reoi_growth", "oi_growth",
                  *[s for s, _ in BRIDGE_STEPS],
                  "margin_effect", "turnover_effect", "profitability_effect",
                  "growth_effect"]:
            out[c] = np.nan
        out["bridge_available"] = False
        out["drivers_available"] = False

        have_prev = p is not None and not _nan(p["reoi"]) and not _nan(d["reoi"])
        if have_prev:
            out["reoi_prev"] = p["reoi"]
            out["delta_reoi"] = d["reoi"] - p["reoi"]
            floor = NEAR_ZERO_FRAC * abs(d["revenue"])
            if p["reoi"] > 0 and p["reoi"] >= floor:
                out["reoi_growth"] = d["reoi"] / p["reoi"] - 1.0
            else:
                flags.append("reoi_base_not_positive_suppressed")
            if p["oi_after_tax"] > 0 and p["oi_after_tax"] >= floor:
                out["oi_growth"] = d["oi_after_tax"] / p["oi_after_tax"] - 1.0
        else:
            flags.append("no_prior_reoi")

        if have_prev and not _nan(d["pm"]) and not _nan(p["pm"]):
            steps = {
                "sales_effect": (d["revenue"] - p["revenue"]) * p["pm"],
                "core_margin_effect": d["revenue"] * (d["pm_core"] - p["pm_core"]),
                "unusual_effect": d["revenue"] * (d["pm_unusual"] - p["pm_unusual"]),
                "capital_charge_effect": -r_op * (d["noa_begin"] - p["noa_begin"]),
            }
            out.update(steps)
            out["bridge_available"] = True
            order = 0
            bridge_rows.append(dict(ts_code=ts, end_date=ed, step_order=order,
                                    concept="reoi_prev",
                                    label=f"ReOI {int(y) - 1}",
                                    value=p["reoi"], step_kind="start"))
            total = p["reoi"]
            for sid, label in BRIDGE_STEPS:
                order += 1
                bridge_rows.append(dict(ts_code=ts, end_date=ed,
                                        step_order=order, concept=sid,
                                        label=label, value=steps[sid],
                                        step_kind="adjustment"))
                total += steps[sid]
            bridge_rows.append(dict(ts_code=ts, end_date=ed,
                                    step_order=order + 1, concept="reoi",
                                    label=f"ReOI {y}", value=d["reoi"],
                                    step_kind="total"))
            check_rows.append(dict(ts_code=ts, end_date=ed,
                                   check="RI1_bridge_additive",
                                   residual=total - d["reoi"]))
        elif have_prev:
            flags.append("bridge_unavailable_no_revenue")

        if have_prev and not _nan(d["spread_op"]) and not _nan(p["spread_op"]):
            n1 = d["noa_begin"]
            margin = (d["pm"] - p["pm"]) * p["ato_open"] * n1
            turnover = d["pm"] * (d["ato_open"] - p["ato_open"]) * n1
            growth = p["spread_op"] * (n1 - p["noa_begin"])
            out.update(margin_effect=margin, turnover_effect=turnover,
                       profitability_effect=margin + turnover,
                       growth_effect=growth, drivers_available=True)
            check_rows.append(dict(
                ts_code=ts, end_date=ed, check="RI2_driver_split_additive",
                residual=p["reoi"] + margin + turnover + growth - d["reoi"]))
        elif have_prev:
            flags.append("drivers_suppressed")

        m4 = m4_by_year.get(y)
        if m4 is not None and not _nan(d["rnoa_open"]) and not _nan(m4.rnoa):
            check_rows.append(dict(ts_code=ts, end_date=ed,
                                   check="RI3_rnoa_vs_module4",
                                   residual=d["rnoa_open"] - m4.rnoa))
        if m4 is not None and not _nan(d["roce_open"]) and not _nan(m4.roce_parent):
            check_rows.append(dict(ts_code=ts, end_date=ed,
                                   check="RI4_roce_vs_module4",
                                   residual=d["roce_open"] - m4.roce_parent))

        out["rate_note"] = RATE_NOTE
        out["oci_note"] = OCI_NOTE
        out["ri_flags"] = ",".join(flags)
        summary_rows.append(out)

    summary = pd.DataFrame(summary_rows).sort_values("end_date").reset_index(drop=True)
    bridge = pd.DataFrame(
        bridge_rows, columns=["ts_code", "end_date", "step_order", "concept",
                              "label", "value", "step_kind"])
    checks = pd.DataFrame(
        check_rows, columns=["ts_code", "end_date", "check", "residual"])
    return summary, bridge, checks


def build_residual_income(store: Store, ts_code: str,
                          r_op: float = DEFAULT_R_OP,
                          r_e: float = DEFAULT_R_E) -> dict:
    bs = store.con.execute(
        "SELECT * FROM reformulated_bs WHERE ts_code = ?", [ts_code]).df()
    is_ = store.con.execute(
        "SELECT * FROM reformulated_is WHERE ts_code = ?", [ts_code]).df()
    exists = store.con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_name='ratios_annual'").fetchall()[0][0]
    if bs.empty or is_.empty or not exists:
        raise RuntimeError(
            f"Missing inputs for {ts_code}; run `reformulate` and `ratios` first.")
    ratios = store.con.execute(
        "SELECT * FROM ratios_annual WHERE ts_code = ?", [ts_code]).df()
    summary, bridge, checks = compute_residual_income(bs, is_, ratios, r_op, r_e)
    for table, df in [("residual_income_annual", summary),
                      ("value_bridge_annual", bridge),
                      ("residual_income_checks", checks)]:
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
    return {"summary": summary, "bridge": bridge, "checks": checks}
