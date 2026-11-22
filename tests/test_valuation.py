"""Offline tests for valuation & reverse analysis (Module 12)."""
import numpy as np
import pandas as pd
import pytest

from pipeline.valuation import CURVE_R, G_GRID, R_GRID, compute_valuation

R, G = 0.10, 0.02


def bs_row(year, noa, nfo, mi=0.0):
    return dict(ts_code="T", end_date=f"{year}1231", noa=noa, nfo=nfo,
                minority_interests=mi, cse_calc=noa - nfo - mi)


def is_row(year, rev, oi, ni):
    return dict(ts_code="T", end_date=f"{year}1231", period_kind="cumulative",
                total_revenue=rev, oi_after_tax=oi, ni_parent=ni,
                comprehensive_income_parent=ni)


def mkt_row(year, mcap, shares=100.0, pe=np.nan):
    return dict(ts_code="T", end_date=f"{year}1231", trade_date=f"{year}1229",
                close=mcap / shares, shares=shares, market_cap=mcap,
                pe_reported=pe, pb_reported=np.nan, m1_mcap_residual_rel=0.0)


def base_inputs():
    """2023: NOA 800 (begin 600), OI 250 → ReOI_0 = 250 − 60 = 190;
    CSE 980 (begin 740), NI 260 → RE_0 = 186; NFO −200, MI 20.
    Market cap 3000 → P_NOA = 3000 − 200 + 20 = 2820, X = 2020."""
    bs = pd.DataFrame([bs_row(2021, 500, -100), bs_row(2022, 600, -150, 10),
                       bs_row(2023, 800, -200, 20)])
    is_ = pd.DataFrame([is_row(2021, 900, 150, 150),
                        is_row(2022, 1000, 200, 205),
                        is_row(2023, 1200, 250, 260)])
    cap = pd.DataFrame([dict(ts_code="T", end_date="20231231",
                             fcf_from_oi=50.0)])
    mkt = pd.DataFrame([mkt_row(2023, 3000.0, pe=3000 / 205)])
    return bs, is_, cap, mkt


def run(*inputs, ri=None, g=G):
    return compute_valuation(*inputs, ri=ri, r_op=R, r_e=R, g=g)


def row(out, year="2023"):
    return out["summary"].set_index("end_date").loc[f"{year}1231"]


def checks_for(out, year="2023"):
    c = out["checks"]
    return c[c.end_date == f"{year}1231"].set_index("check").residual


def test_model_values_hand_computed():
    r = row(run(*base_inputs()))
    assert r.reoi_0 == pytest.approx(190)
    assert r.v_noa_book == pytest.approx(800)
    assert r.v_noa_reoi_flat == pytest.approx(800 + 190 / R)
    assert r.v_noa_reoi_g == pytest.approx(800 + 190 * 1.02 / 0.08)
    assert r.v_noa_rnoa_g == pytest.approx(800 + (250 / 600 - R) * 800 / 0.08)
    # V_E = V_NOA − NFO − MI = V_NOA + 200 − 20
    assert r.v_equity_reoi_g == pytest.approx(r.v_noa_reoi_g + 180)
    assert r.v_to_p == pytest.approx(r.v_equity_reoi_g / 3000)
    assert r.v_per_share == pytest.approx(r.v_equity_reoi_g / 100)
    assert (r.r_op_assumed, r.r_e_assumed, r.g_assumed) == (R, R, G)


def test_aeg_equals_ri_equity_and_historical_aeg_identity():
    out = run(*base_inputs())
    r = row(out)
    assert r.v_equity_ri == pytest.approx(980 + 186 * 1.02 / 0.08)
    assert r.v_equity_aeg == pytest.approx(r.v_equity_ri)
    assert r.earn_1 == pytest.approx(98 + 186 * 1.02)
    assert r.normal_pe == pytest.approx(1 / R)
    assert r.forward_pe_market == pytest.approx(3000 / r.earn_1)
    # d_2022 = 205 − (740 − 600) = 65; AEG = 260 + 6.5 − 1.1 × 205 = 41
    assert r.aeg_actual == pytest.approx(41)
    assert r.aeg_actual == pytest.approx(186 - (205 - 0.1 * 600))  # ΔRE
    assert r.cum_div_growth == pytest.approx((260 + 6.5) / 205 - 1)
    c = checks_for(out)
    assert abs(c["V1_aeg_vs_ri_equity"]) < 1e-9
    assert abs(c["V9_aeg_actual_vs_delta_re"]) < 1e-9


def test_reverse_engineering_closed_forms_round_trip():
    out = run(*base_inputs())
    r = row(out)
    assert r.market_ev == pytest.approx(2820)
    assert r.implied_g_reoi == pytest.approx((0.1 * 2020 - 190) / (2020 + 190))
    reoi1 = (250 / 600 - R) * 800
    assert r.implied_g_rnoa == pytest.approx(R - reoi1 / 2020)
    assert r.implied_g_fcf == pytest.approx((0.1 * 2820 - 50) / (2820 + 50))
    assert r.implied_g_equity == pytest.approx((0.1 * 2020 - 186) / (2020 + 186))
    assert r.implied_r_op == pytest.approx(
        (250 * 1.02 + 0.02 * 2020) / (2020 + 1.02 * 600))
    c = checks_for(out)
    for name in ["V3_implied_g_roundtrip_reoi", "V4_implied_g_roundtrip_rnoa",
                 "V5_implied_g_roundtrip_fcf", "V6_implied_g_roundtrip_equity",
                 "V7_implied_r_roundtrip_op", "V8_implied_r_roundtrip_e"]:
        assert abs(c[name]) < 1e-6, name


def test_valuation_bridge_steps_and_additivity():
    out = run(*base_inputs())
    b = out["bridge"].set_index("concept")
    r = row(out)
    assert b.loc["noa", "value"] == pytest.approx(800)
    assert b.loc["reoi_flat_value", "value"] == pytest.approx(1900)
    assert b.loc["growth_value", "value"] == pytest.approx(190 * 1.02 / 0.08 - 1900)
    assert b.loc["net_financial_assets", "value"] == pytest.approx(200)
    assert b.loc["minority_interests", "value"] == pytest.approx(-20)
    assert b.loc["v_equity", "value"] == pytest.approx(r.v_equity_reoi_g)
    assert b.loc["market_premium", "value"] == pytest.approx(3000 - r.v_equity_reoi_g)
    kinds = out["bridge"].sort_values("step_order").step_kind.tolist()
    assert kinds == ["start"] + ["adjustment"] * 4 + ["total", "adjustment", "total"]
    v2 = checks_for(out)["V2_bridge_additive"]
    assert abs(v2) < 1e-9


def test_sensitivity_grid_and_reverse_curve_consistent_with_summary():
    out = run(*base_inputs())
    grid, curve, r = out["grid"], out["curve"], row(out)
    assert len(grid) == len(R_GRID) * len(G_GRID)
    cell = grid[(grid.r == R) & (grid.g == G)].iloc[0]
    assert cell.v_equity == pytest.approx(r.v_equity_reoi_g)
    # value falls as r rises, at every g
    for gg in G_GRID:
        col = grid[grid.g == gg].sort_values("r").v_to_p.to_numpy()
        assert (np.diff(col) < 0).all()
    assert len(curve) == len(CURVE_R)
    at_r = curve[np.isclose(curve.r, R)].iloc[0]
    assert at_r.implied_g_reoi == pytest.approx(r.implied_g_reoi)
    assert at_r.implied_g_fcf == pytest.approx(r.implied_g_fcf)


def test_growth_not_below_rate_suppresses_growth_models():
    out = run(*base_inputs(), g=0.10)
    r = row(out)
    assert "growth_not_below_rate" in r.val_flags
    assert pd.isna(r.v_noa_reoi_g) and pd.isna(r.v_noa_rnoa_g)
    assert pd.isna(r.v_equity_ri) and pd.isna(r.v_to_p)
    assert r.v_noa_reoi_flat == pytest.approx(2700)  # no-growth model survives
    assert out["bridge"].empty


def test_missing_market_data_keeps_models_without_reverse():
    bs, is_, cap, _ = base_inputs()
    out = run(bs, is_, cap, pd.DataFrame(columns=mkt_row(2023, 1.0).keys()))
    r = row(out)
    assert "no_market_data" in r.val_flags
    assert r.v_noa_reoi_g == pytest.approx(800 + 190 * 1.02 / 0.08)
    assert pd.isna(r.implied_g_reoi) and pd.isna(r.v_to_p)
    assert out["grid"].empty and out["bridge"].empty
    first = row(out, "2021")
    assert "no_opening_balance" in first.val_flags and pd.isna(first.reoi_0)


def test_negative_noa_base_suppresses_rnoa_anchor_only():
    bs, is_, cap, mkt = base_inputs()
    bs.loc[1, ["noa", "nfo"]] = [-50.0, -800.0]
    out = run(bs, is_, cap, mkt)
    r = row(out)
    assert "rnoa_anchor_suppressed" in r.val_flags
    assert pd.isna(r.rnoa_0) and pd.isna(r.v_noa_rnoa_g)
    assert r.reoi_0 == pytest.approx(250 + 5)  # charge on negative NOA is a credit
    assert not pd.isna(r.v_noa_reoi_g) and not pd.isna(r.implied_g_reoi)


def test_non_positive_anchor_leaves_implied_g_undefined():
    bs, is_, cap, mkt = base_inputs()
    is_.loc[2, "oi_after_tax"] = 50.0  # ReOI_0 = 50 − 60 < 0
    cap.loc[0, "fcf_from_oi"] = -10.0
    r = row(run(bs, is_, cap, mkt))
    assert pd.isna(r.implied_g_reoi) and "implied_g_reoi_undefined" in r.val_flags
    assert pd.isna(r.implied_g_fcf) and "implied_g_fcf_undefined" in r.val_flags


def test_external_pe_and_module11_cross_checks():
    bs, is_, cap, mkt = base_inputs()
    ri = pd.DataFrame([dict(ts_code="T", end_date="20231231", reoi=190.0,
                            r_op_assumed=R)])
    c = checks_for(run(bs, is_, cap, mkt, ri=ri))
    assert abs(c["M2_pe_reported_vs_prior_year_ni_rel"]) < 1e-12
    assert abs(c["V10_reoi_vs_module11"]) < 1e-12
    ri.loc[0, "r_op_assumed"] = 0.08  # different rate → no comparison
    c2 = run(bs, is_, cap, mkt, ri=ri)["checks"]
    assert "V10_reoi_vs_module11" not in set(c2.check)


def test_equity_models_use_comprehensive_income_but_trailing_pe_uses_net_income():
    bs, is_, cap, market = base_inputs()
    is_.loc[is_.end_date == "20231231", "comprehensive_income_parent"] = 272
    result = run(bs, is_, cap, market)
    r = row(result)
    assert r.re_0 == pytest.approx(272 - R * 740)
    assert r.v_equity_ri == pytest.approx(r.v_equity_aeg)
    assert r.aeg_actual == pytest.approx(53)
    assert r.trailing_pe == pytest.approx(3000 / 260)
    assert abs(checks_for(result)["V9_aeg_actual_vs_delta_re"]) < 1e-9
