"""Module 12 — Valuation & reverse analysis (annual, Penman simple schemes).

Every model here is a FORECASTING ASSUMPTION applied to the current
reformulated statements, not a forecast. Inputs per fiscal year t (year-end
balance sheet = valuation date; see market.py for the hindsight caveat):

    NOA_0, NFO_0, MI_0, CSE_0      year-end stocks (Module 3)
    OI_0, NI_0                      year flows (Module 3)
    ReOI_0 = OI_0 − r × NOA_{−1}    (Module 11 definition, at THIS module's r)
    RE_0   = CI_0 − r_e × CSE_{−1}    (parent comprehensive income)
    RNOA_0 = OI_0 / NOA_{−1}        (opening; suppressed as in Module 4)

Enterprise models (V_NOA; equity value V_E = V_NOA − NFO_0 − MI_0, both at
BOOK value — a stated assumption):

    book       V = NOA_0                                    (SF1)
    reoi_flat  V = NOA_0 + ReOI_0 / r                       (SF2)
    reoi_g     V = NOA_0 + ReOI_0 (1+g) / (r − g)           (primary)
    rnoa_g     V = NOA_0 + (RNOA_0 − r) NOA_0 / (r − g)     (Penman SF3)

reoi_g grows the CURRENT residual income; rnoa_g earns last year's opening
RNOA on the whole year-end NOA, so it is the more aggressive whenever NOA
grew faster than OI (Moutai since 2019). Both shown; reoi_g drives the
bridge, the sensitivity grid and the headline V/P.

Equity level: RI  V_E = CSE_0 + RE_0 (1+g) / (r_e − g); AEG with the
SAME forecast (Earn_1 = r_e CSE_0 + RE_1, AEG_2 = g RE_1):
    V_E = [Earn_1 + AEG_2 / (r_e − g)] / r_e
The two are algebraically identical (check V1) — AEG adds the P/E reading:
normal forward P/E = 1 / r_e; a market forward P/E above it prices AEG > 0.
Historical AEG = CI_t + r_e d_{t−1} − (1+r_e) CI_{t−1} with
d = CI − ΔCSE (implied net payout including other direct equity movements)
≡ RE_t − RE_{t−1} (check V9).

Reverse engineering — closed forms, P_NOA = market cap + NFO_0 + MI_0
(enterprise market value), X = P_NOA − NOA_0:
    implied g (reoi_g)  = (r X − ReOI_0) / (X + ReOI_0)
    implied g (rnoa_g)  = r − (RNOA_0 − r) NOA_0 / X
    implied g (FCF)     = (r P_NOA − FCF_0) / (P_NOA + FCF_0)
                          FCF_0 = OI − ΔNOA (Module 10's fcf_from_oi)
    implied g (equity)  = (r_e Y − RE_0) / (Y + RE_0),  Y = mcap − CSE_0
    implied r_op at g   = [OI_0 (1+g) + g X] / [X + (1+g) NOA_{−1}]
    implied r_e at g    = [CI_0 (1+g) + g Y] / [Y + (1+g) CSE_{−1}]
Each is plugged back into its model (round-trip checks V3–V8). A solution
that is not below r (or a non-positive anchor) is meaningless for a
perpetuity → NaN + flag.

Not claimed: no analyst forecasts, no beta, no terminal-year judgement; a
single perpetual growth rate is the crudest scheme. The market cap may embed
expectations (or mispricing) no simple scheme captures — the 'market
premium' bar is what the assumptions leave unexplained, not an error.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .ratios import NEAR_ZERO_FRAC
from .store import Store

DEFAULT_R_OP = 0.08
DEFAULT_R_E = 0.08
DEFAULT_G = 0.03
PRIMARY_MODEL = "reoi_g"
MODELS = ["book", "reoi_flat", "reoi_g", "rnoa_g"]

R_GRID = [0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12]
G_GRID = [-0.02, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05]
CURVE_R = [round(0.05 + 0.005 * i, 4) for i in range(15)]  # 5% … 12%

VALUATION_NOTE = (
    "Simple perpetuity schemes on current reformulated statements; r_op, r_e "
    "and g are ASSUMPTIONS stored per row. NFO and minority interests enter "
    "at book value. Year-end price vs year-end book is a hindsight anchor "
    "(statements published months later).")
FCF_NOTE = ("Reverse DCF uses FCF = OI − ΔNOA (Module 10 fcf_from_oi), "
            "which swings with working capital; one year is a noisy anchor.")

BRIDGE_STEPS = [
    # (concept, short label, kind)
    ("noa", "NOA (book)", "start"),
    ("reoi_flat_value", "ReOI flat / r", "adjustment"),
    ("growth_value", "Growth at g", "adjustment"),
    ("net_financial_assets", "Net fin. assets", "adjustment"),
    ("minority_interests", "Minority int.", "adjustment"),
    ("v_equity", "Model equity", "total"),
    ("market_premium", "Market premium", "adjustment"),
    ("market_cap", "Market cap", "total"),
]


def _nan(v) -> bool:
    return v is None or pd.isna(v)


def _perp(anchor: float, r: float, g: float, grow_anchor: bool) -> float:
    """PV of a growing perpetuity whose first term is anchor×(1+g) (or
    anchor itself when grow_anchor is False). NaN unless g < r."""
    if _nan(anchor) or not g < r:
        return np.nan
    return anchor * ((1 + g) if grow_anchor else 1.0) / (r - g)


def v_noa_reoi_g(noa0, noa_b, oi0, r, g):
    """reoi_g enterprise value at (r, g); ReOI_0 recomputed at r."""
    if _nan(noa0) or _nan(noa_b) or _nan(oi0):
        return np.nan
    return noa0 + _perp(oi0 - r * noa_b, r, g, True)


def _implied_g(r: float, x: float, anchor: float) -> float:
    """g with x = anchor (1+g)/(r − g); meaningful only if anchor > 0 and
    x + anchor > 0 (then g < r automatically)."""
    if _nan(x) or _nan(anchor) or anchor <= 0 or x + anchor <= 0:
        return np.nan
    return (r * x - anchor) / (x + anchor)


def _implied_g_flat_first(r: float, x: float, first: float) -> float:
    """g with x = first / (r − g); meaningful only if first > 0, x > 0."""
    if _nan(x) or _nan(first) or first <= 0 or x <= 0:
        return np.nan
    return r - first / x


def _implied_r(g: float, x: float, flow0: float, base_b: float) -> float:
    """r with x = (flow0 − r·base_b)(1+g)/(r − g); requires r > g."""
    if _nan(x) or _nan(flow0) or _nan(base_b):
        return np.nan
    den = x + (1 + g) * base_b
    if den <= 0:
        return np.nan
    r = (flow0 * (1 + g) + g * x) / den
    return r if r > g else np.nan


def compute_valuation(
    bs: pd.DataFrame, is_: pd.DataFrame, cap: pd.DataFrame,
    mkt: pd.DataFrame, ri: pd.DataFrame | None = None,
    r_op: float = DEFAULT_R_OP, r_e: float = DEFAULT_R_E,
    g: float = DEFAULT_G,
) -> dict[str, pd.DataFrame]:
    """Inputs: Module-3 BS/IS, Module-10 capital summary, market snapshot,
    optional Module-11 summary (cross-check only). Returns summary, bridge,
    grid, curve, checks."""
    if not all(np.isfinite(rate) and rate > 0 for rate in (r_op, r_e)):
        raise ValueError("Required returns must be finite and positive.")
    if not np.isfinite(g) or g <= -1:
        raise ValueError("Perpetual growth must be finite and above -100%.")
    bs = bs[bs.end_date.str.endswith("1231")]
    isa = is_[(is_.period_kind == "cumulative")
              & is_.end_date.str.endswith("1231")].sort_values("end_date")
    by = {r.end_date[:4]: r for r in bs.itertuples()}
    cap_by = {r.end_date[:4]: r for r in cap.itertuples()}
    mkt_by = {r.end_date[:4]: r for r in mkt.itertuples()}
    is_by = {r.end_date[:4]: r for r in isa.itertuples()}
    ri_by = ({r.end_date[:4]: r for r in ri.itertuples()}
             if ri is not None and not ri.empty else {})

    summary, bridge, grid, curve, checks = [], [], [], [], []

    def chk(ts, ed, name, residual):
        checks.append(dict(ts_code=ts, end_date=ed, check=name,
                           residual=residual))

    for y in sorted(is_by):
        r_ = is_by[y]
        ts, ed = r_.ts_code, r_.end_date
        cur, prev = by.get(y), by.get(str(int(y) - 1))
        prev2 = by.get(str(int(y) - 2))
        flags: list[str] = []
        d = dict(ts_code=ts, end_date=ed, r_op_assumed=r_op,
                 r_e_assumed=r_e, g_assumed=g,
                 revenue=r_.total_revenue, oi_after_tax=r_.oi_after_tax,
                 ni_parent=r_.ni_parent,
                 comprehensive_income_parent=getattr(r_, "comprehensive_income_parent", np.nan))
        nan_cols = [
            "noa", "nfo", "minority_interests", "cse", "noa_begin",
            "cse_begin", "reoi_0", "re_0", "rnoa_0", "reoi_1_rnoa", "fcf_0",
            *[f"v_noa_{m}" for m in MODELS], *[f"v_equity_{m}" for m in MODELS],
            "v_equity_ri", "v_equity_aeg", "earn_1", "aeg_2",
            "trade_date", "price", "shares", "market_cap", "market_ev",
            "v_per_share", "v_to_p", "forward_pe_market", "forward_pe_model",
            "normal_pe", "trailing_pe", "implied_g_reoi", "implied_g_rnoa",
            "implied_g_fcf", "implied_g_equity", "implied_r_op",
            "implied_r_e", "net_payout_implied", "aeg_actual",
            "cum_div_growth"]
        for c in nan_cols:
            d[c] = np.nan
        d["trade_date"] = None

        if cur is None:
            flags.append("no_balance_sheet")
        else:
            d.update(noa=cur.noa, nfo=cur.nfo,
                     minority_interests=cur.minority_interests,
                     cse=cur.cse_calc)
            d["v_noa_book"] = cur.noa
            d["v_equity_book"] = cur.cse_calc
        have_open = cur is not None and prev is not None
        if not have_open:
            flags.append("no_opening_balance")
        floor = (NEAR_ZERO_FRAC * abs(r_.total_revenue)
                 if not _nan(r_.total_revenue) else np.inf)

        if have_open:
            noa0, noa_b = cur.noa, prev.noa
            cse0, cse_b = cur.cse_calc, prev.cse_calc
            oi0, ci0 = r_.oi_after_tax, d["comprehensive_income_parent"]
            reoi0 = oi0 - r_op * noa_b
            re0 = ci0 - r_e * cse_b
            if _nan(ci0):
                flags.append("comprehensive_income_parent_missing")
            d.update(noa_begin=noa_b, cse_begin=cse_b, reoi_0=reoi0, re_0=re0,
                     normal_pe=1.0 / r_e)
            if noa_b > 0 and noa_b >= floor:
                d["rnoa_0"] = oi0 / noa_b
            else:
                flags.append("rnoa_anchor_suppressed")
            if not g < r_op or not g < r_e:
                flags.append("growth_not_below_rate")

            d["v_noa_reoi_flat"] = noa0 + reoi0 / r_op
            d["v_noa_reoi_g"] = noa0 + _perp(reoi0, r_op, g, True)
            if not _nan(d["rnoa_0"]) and noa0 > 0:
                d["reoi_1_rnoa"] = (d["rnoa_0"] - r_op) * noa0
                d["v_noa_rnoa_g"] = noa0 + _perp(d["reoi_1_rnoa"], r_op, g, False)
            elif not _nan(d["rnoa_0"]):
                flags.append("rnoa_anchor_suppressed")
            for m in MODELS:
                d[f"v_equity_{m}"] = (d[f"v_noa_{m}"] - cur.nfo
                                      - cur.minority_interests)

            # equity level: RI and AEG on the same forecast
            if g < r_e and not _nan(re0):
                re1 = re0 * (1 + g)
                d["v_equity_ri"] = cse0 + re1 / (r_e - g)
                d["earn_1"] = r_e * cse0 + re1
                d["aeg_2"] = g * re1
                d["v_equity_aeg"] = (d["earn_1"] + d["aeg_2"] / (r_e - g)) / r_e
                chk(ts, ed, "V1_aeg_vs_ri_equity",
                    d["v_equity_aeg"] - d["v_equity_ri"])
                if d["earn_1"] > 0:
                    d["forward_pe_model"] = d["v_equity_aeg"] / d["earn_1"]

            # historical AEG needs CSE_{t−2}
            pi = is_by.get(str(int(y) - 1))
            ci_prev = getattr(pi, "comprehensive_income_parent", np.nan)
            if prev2 is not None and not _nan(ci0) and not _nan(ci_prev):
                d_prev = ci_prev - (prev.cse_calc - prev2.cse_calc)
                d["aeg_actual"] = ci0 + r_e * d_prev - (1 + r_e) * ci_prev
                if ci_prev > 0:
                    d["cum_div_growth"] = (ci0 + r_e * d_prev) / ci_prev - 1.0
                re_prev = ci_prev - r_e * prev2.cse_calc
                chk(ts, ed, "V9_aeg_actual_vs_delta_re",
                    d["aeg_actual"] - (re0 - re_prev))
            d["net_payout_implied"] = ci0 - (cse0 - cse_b)

            cs = cap_by.get(y)
            if cs is not None and not _nan(cs.fcf_from_oi):
                d["fcf_0"] = cs.fcf_from_oi

            m11 = ri_by.get(y)
            if (m11 is not None and not _nan(m11.reoi)
                    and m11.r_op_assumed == r_op):
                chk(ts, ed, "V10_reoi_vs_module11", reoi0 - m11.reoi)

        m = mkt_by.get(y)
        if m is None:
            flags.append("no_market_data")
        else:
            d.update(trade_date=m.trade_date, price=m.close, shares=m.shares,
                     market_cap=m.market_cap)
            chk(ts, ed, "M1_mcap_vs_price_x_shares_rel", m.m1_mcap_residual_rel)
            if not _nan(r_.ni_parent) and r_.ni_parent > 0:
                d["trailing_pe"] = m.market_cap / r_.ni_parent
            # Tushare's year-end pe uses the latest PUBLISHED annual NI,
            # i.e. the prior year's: independent check of units and timing
            pi_ = is_by.get(str(int(y) - 1))
            if (pi_ is not None and not _nan(m.pe_reported)
                    and m.pe_reported > 0 and pi_.ni_parent > 0):
                chk(ts, ed, "M2_pe_reported_vs_prior_year_ni_rel",
                    m.market_cap / pi_.ni_parent / m.pe_reported - 1.0)

        if have_open and m is not None:
            mcap = m.market_cap
            p_noa = mcap + cur.nfo + cur.minority_interests
            x = p_noa - noa0
            yv = mcap - cse0
            d["market_ev"] = p_noa
            if x <= 0:
                flags.append("market_ev_at_or_below_noa")
            v_e = d[f"v_equity_{PRIMARY_MODEL}"]
            if not _nan(v_e) and mcap > 0:
                d["v_to_p"] = v_e / mcap
            if not _nan(v_e) and m.shares > 0:
                d["v_per_share"] = v_e / m.shares
            if not _nan(d["earn_1"]) and d["earn_1"] > 0:
                d["forward_pe_market"] = mcap / d["earn_1"]

            gi = _implied_g(r_op, x, reoi0)
            d["implied_g_reoi"] = gi
            if _nan(gi):
                flags.append("implied_g_reoi_undefined")
            else:
                chk(ts, ed, "V3_implied_g_roundtrip_reoi",
                    noa0 + _perp(reoi0, r_op, gi, True) - p_noa)
            if not _nan(d["reoi_1_rnoa"]):
                gr = _implied_g_flat_first(r_op, x, d["reoi_1_rnoa"])
                d["implied_g_rnoa"] = gr
                if _nan(gr):
                    flags.append("implied_g_rnoa_undefined")
                else:
                    chk(ts, ed, "V4_implied_g_roundtrip_rnoa",
                        noa0 + _perp(d["reoi_1_rnoa"], r_op, gr, False) - p_noa)
            if not _nan(d["fcf_0"]):
                gf = _implied_g(r_op, p_noa, d["fcf_0"])
                d["implied_g_fcf"] = gf
                if _nan(gf):
                    flags.append("implied_g_fcf_undefined")
                else:
                    chk(ts, ed, "V5_implied_g_roundtrip_fcf",
                        _perp(d["fcf_0"], r_op, gf, True) - p_noa)
            ge = _implied_g(r_e, yv, re0)
            d["implied_g_equity"] = ge
            if _nan(ge):
                flags.append("implied_g_equity_undefined")
            else:
                chk(ts, ed, "V6_implied_g_roundtrip_equity",
                    cse0 + _perp(re0, r_e, ge, True) - mcap)
            ir = _implied_r(g, x, oi0, noa_b)
            d["implied_r_op"] = ir
            if not _nan(ir):
                chk(ts, ed, "V7_implied_r_roundtrip_op",
                    noa0 + _perp(oi0 - ir * noa_b, ir, g, True) - p_noa)
            ire = _implied_r(g, yv, ci0, cse_b)
            d["implied_r_e"] = ire
            if not _nan(ire):
                chk(ts, ed, "V8_implied_r_roundtrip_e",
                    cse0 + _perp(ci0 - ire * cse_b, ire, g, True) - mcap)

            # valuation bridge (primary model)
            if not _nan(v_e):
                vals = {
                    "noa": noa0,
                    "reoi_flat_value": reoi0 / r_op,
                    "growth_value": d["v_noa_reoi_g"] - d["v_noa_reoi_flat"],
                    "net_financial_assets": -cur.nfo,
                    "minority_interests": -cur.minority_interests,
                    "v_equity": v_e,
                    "market_premium": mcap - v_e,
                    "market_cap": mcap,
                }
                running = 0.0
                for i, (cid, label, kind) in enumerate(BRIDGE_STEPS):
                    bridge.append(dict(ts_code=ts, end_date=ed, step_order=i,
                                       concept=cid, label=label,
                                       value=vals[cid], step_kind=kind))
                    if kind != "total":
                        running = vals[cid] if kind == "start" else running + vals[cid]
                chk(ts, ed, "V2_bridge_additive", running - mcap)

            # sensitivity grid (primary model) and reverse curve
            for rr in R_GRID:
                for gg in G_GRID:
                    vn = v_noa_reoi_g(noa0, noa_b, oi0, rr, gg)
                    ve = vn - cur.nfo - cur.minority_interests
                    grid.append(dict(ts_code=ts, end_date=ed,
                                     model=PRIMARY_MODEL, r=rr, g=gg,
                                     v_noa=vn, v_equity=ve,
                                     v_per_share=ve / m.shares if m.shares > 0 else np.nan,
                                     v_to_p=ve / mcap if mcap > 0 else np.nan))
            for rr in CURVE_R:
                curve.append(dict(
                    ts_code=ts, end_date=ed, r=rr,
                    implied_g_reoi=_implied_g(rr, x, oi0 - rr * noa_b),
                    implied_g_rnoa=(_implied_g_flat_first(
                        rr, x, (d["rnoa_0"] - rr) * noa0)
                        if not _nan(d["rnoa_0"]) and noa0 > 0 else np.nan),
                    implied_g_fcf=_implied_g(rr, p_noa, d["fcf_0"]),
                    implied_g_equity=_implied_g(rr, yv, ci0 - rr * cse_b)))

        d["valuation_note"] = VALUATION_NOTE
        d["fcf_note"] = FCF_NOTE
        d["val_flags"] = ",".join(dict.fromkeys(flags))
        summary.append(d)

    def frame(rows, cols=None):
        return pd.DataFrame(rows, columns=cols)

    return {
        "summary": frame(summary).sort_values("end_date").reset_index(drop=True),
        "bridge": frame(bridge, ["ts_code", "end_date", "step_order", "concept",
                                 "label", "value", "step_kind"]),
        "grid": frame(grid, ["ts_code", "end_date", "model", "r", "g", "v_noa",
                             "v_equity", "v_per_share", "v_to_p"]),
        "curve": frame(curve, ["ts_code", "end_date", "r", "implied_g_reoi",
                               "implied_g_rnoa", "implied_g_fcf",
                               "implied_g_equity"]),
        "checks": frame(checks, ["ts_code", "end_date", "check", "residual"]),
    }


OUTPUT_TABLES = {
    "summary": "valuation_annual",
    "bridge": "valuation_bridge_annual",
    "grid": "valuation_grid",
    "curve": "valuation_reverse_curve",
    "checks": "valuation_checks",
}


def _table_exists(store: Store, name: str) -> bool:
    return store.con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name=?",
        [name]).fetchall()[0][0] > 0


def build_valuation(store: Store, ts_code: str, r_op: float = DEFAULT_R_OP,
                    r_e: float = DEFAULT_R_E, g: float = DEFAULT_G) -> dict:
    need = ["reformulated_bs", "reformulated_is", "capital_summary_annual",
            "market_snapshot_annual"]
    missing = [t for t in need if not _table_exists(store, t)]
    if missing:
        raise RuntimeError(
            f"Missing inputs for {ts_code}: {missing}; run `reformulate`, "
            "`capital` and `market` first.")
    q = lambda t: store.con.execute(  # noqa: E731
        f"SELECT * FROM {t} WHERE ts_code = ?", [ts_code]).df()
    bs, is_, cap, mkt = (q(t) for t in need)
    # No year-end price at all (e.g. listed after the latest year end): model
    # values are still computed; market columns stay null, val_flags says
    # no_market_data, and the bridge/grid/curve tables are empty.
    if bs.empty or is_.empty:
        raise RuntimeError(f"Empty inputs for {ts_code}.")
    ri = q("residual_income_annual") if _table_exists(
        store, "residual_income_annual") else None
    out = compute_valuation(bs, is_, cap, mkt, ri, r_op, r_e, g)
    for key, table in OUTPUT_TABLES.items():
        df = out[key]
        store.con.register("_df", df)
        if _table_exists(store, table):
            if key == "summary":
                store.con.execute(
                    "ALTER TABLE valuation_annual ADD COLUMN IF NOT EXISTS "
                    "comprehensive_income_parent DOUBLE")
            store.con.execute(f"DELETE FROM {table} WHERE ts_code = ?", [ts_code])
            store.con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM _df")
        else:
            store.con.execute(f"CREATE TABLE {table} AS SELECT * FROM _df")
        store.con.unregister("_df")
    return out
