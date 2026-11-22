"""Offline tests for the Capital Investment Bridge (Module 10)."""
import numpy as np
import pandas as pd
import pytest

from pipeline.capital_bridge import compute_capital_bridge


def bs_row(year, oa, ol, fa, fo, mi=0.0):
    noa, nfo = oa - ol, fo - fa
    return dict(ts_code="T", end_date=f"{year}1231", oa=oa, ol=ol, fa=fa,
                fo=fo, noa=noa, nfo=nfo, minority_interests=mi,
                cse_calc=noa - nfo - mi)


def is_row(year, revenue, oi):
    return dict(ts_code="T", end_date=f"{year}1231", period_kind="cumulative",
                total_revenue=revenue, oi_after_tax=oi)


def comp_rows(year, items):
    """items: (concept, effective_class, value)"""
    return [dict(ts_code="T", end_date=f"{year}1231", concept=c,
                 effective_class=k, value=v) for c, k, v in items]


def cf_fact(year, concept, value):
    return dict(ts_code="T", end_date=f"{year}1231", statement="cashflow",
                report_type="1", period_kind="cumulative",
                value_type="reported", concept=concept, value=value)


def base_inputs():
    """Two consistent years. 2023: OA 1000 (inv 600, ar 100, ppe 200,
    other 100), OL 400 (ap 150, contract 100, other 150).
    2024: OA 1180 (inv 700, ar 110, ppe 240, other 130), OL 470
    (ap 170, contract 120, other 180). ΔNOA = 710 − 600 = 110."""
    bs = pd.DataFrame([bs_row(2023, 1000, 400, 300, 50),
                       bs_row(2024, 1180, 470, 380, 60)])
    is_ = pd.DataFrame([is_row(2023, 900, 180), is_row(2024, 1000, 200)])
    comp = pd.DataFrame(
        comp_rows(2023, [("inventory", "operating_asset", 600),
                         ("accounts_receivable", "operating_asset", 100),
                         ("ppe", "operating_asset", 200),
                         ("accounts_payable", "operating_liability", 150),
                         ("contract_liabilities", "operating_liability", 100)])
        + comp_rows(2024, [("inventory", "operating_asset", 700),
                           ("accounts_receivable", "operating_asset", 110),
                           ("ppe", "operating_asset", 240),
                           ("accounts_payable", "operating_liability", 170),
                           ("contract_liabilities", "operating_liability", 120)]))
    cf = pd.DataFrame([cf_fact(2024, "capex_paid", 50),
                       cf_fact(2024, "supp_depreciation", 20),
                       cf_fact(2024, "supp_intangible_amortization", 5)])
    cash = pd.DataFrame([dict(ts_code="T", end_date="20241231",
                              fcf_simple=70.0)])
    return bs, is_, comp, cf, cash


def test_bridge_steps_sum_exactly_and_checks_zero():
    bridge, summary, checks = compute_capital_bridge(*base_inputs())
    b24 = bridge[bridge.end_date == "20241231"].sort_values("step_order")
    assert b24.iloc[0].step_kind == "start"
    assert b24.iloc[0].value == 600  # NOA begin
    assert b24.iloc[-1].step_kind == "total"
    assert b24.iloc[-1].value == 710
    adj = b24[b24.step_kind == "adjustment"]
    assert 600 + adj.value.sum() == pytest.approx(710, abs=1e-9)
    assert checks.residual.abs().max() < 1e-9
    assert set(checks.check) == {"B1_bridge_additive",
                                 "B2_delta_noa_vs_oa_ol",
                                 "B3_funding_identity"}


def test_group_deltas_and_liability_sign():
    bridge, _, _ = compute_capital_bridge(*base_inputs())
    b = bridge[bridge.end_date == "20241231"].set_index("concept")
    assert b.loc["inventory"].value == 100
    assert b.loc["ppe_cip"].value == 40
    # other OA: (1180 − 1050) − (1000 − 900) = 30
    assert b.loc["other_operating_assets"].value == pytest.approx(30)
    # supplier credit grew 20 -> reduces NOA by 20
    assert b.loc["supplier_credit"].value == -20
    assert b.loc["customer_advances"].value == -20
    # other OL: Δ(150→180)=30 -> −30
    assert b.loc["other_operating_liabilities"].value == pytest.approx(-30)


def test_residual_absorbs_undisclosed_component():
    bs, is_, comp, cf, cash = base_inputs()
    comp = comp[comp.concept != "ppe"]  # PP&E undisclosed both years
    bridge, _, checks = compute_capital_bridge(bs, is_, comp, cf, cash)
    b = bridge[bridge.end_date == "20241231"].set_index("concept")
    assert b.loc["ppe_cip"].value == 0
    assert b.loc["other_operating_assets"].value == pytest.approx(70)
    assert checks.residual.abs().max() < 1e-9


def test_misclassified_component_excluded_by_class_filter():
    bs, is_, comp, cf, cash = base_inputs()
    # a financial-class row with an operating-set concept must not be summed
    extra = pd.DataFrame(comp_rows(2024, [("inventory", "financial_asset", 999)]))
    bridge, _, checks = compute_capital_bridge(
        bs, is_, pd.concat([comp, extra]), cf, cash)
    b = bridge[bridge.end_date == "20241231"].set_index("concept")
    assert b.loc["inventory"].value == 100
    assert checks.residual.abs().max() < 1e-9


def test_funding_identity_columns():
    _, summary, checks = compute_capital_bridge(*base_inputs())
    s = summary[summary.end_date == "20241231"].iloc[0]
    # ΔNFO: (50−300) → (60−380) = −250 → −320 = −70
    assert s.delta_nfo == pytest.approx(-70)
    assert s.delta_noa == pytest.approx(s.delta_cse + s.delta_mi + s.delta_nfo)
    b3 = checks[checks.check == "B3_funding_identity"]
    assert b3.residual.abs().max() < 1e-9


def test_reinvestment_and_growth_metrics():
    _, summary, _ = compute_capital_bridge(*base_inputs())
    s = summary[summary.end_date == "20241231"].iloc[0]
    assert s.revenue_growth == pytest.approx(1000 / 900 - 1)
    assert s.noa_growth == pytest.approx(110 / 600)
    assert s.reinvestment_rate == pytest.approx(110 / 200)
    assert s.da_total == 25
    assert s.capex_to_da == pytest.approx(2.0)
    assert s.fcf_from_oi == pytest.approx(200 - 110)
    assert s.fcf_simple == 70
    assert s.fcf_articulation_diff == pytest.approx(20)
    assert s.cap_flags == ""


def test_first_year_no_bridge_flagged():
    bridge, summary, checks = compute_capital_bridge(*base_inputs())
    assert (bridge.end_date == "20231231").sum() == 0
    s23 = summary[summary.end_date == "20231231"].iloc[0]
    assert "no_opening_balance" in s23.cap_flags
    assert pd.isna(s23.delta_noa) and pd.isna(s23.reinvestment_rate)
    assert s23.noa_end == 600  # level still reported
    assert (checks.end_date == "20231231").sum() == 0


def test_guards_suppress_misleading_ratios():
    bs, is_, comp, cf, cash = base_inputs()
    # OI near zero (< 5% of revenue) -> reinvestment rate suppressed
    is_oi0 = pd.DataFrame([is_row(2023, 900, 180), is_row(2024, 1000, 10)])
    _, s, _ = compute_capital_bridge(bs, is_oi0, comp, cf, cash)
    r = s[s.end_date == "20241231"].iloc[0]
    assert pd.isna(r.reinvestment_rate)
    assert "oi_near_zero_suppressed" in r.cap_flags
    # negative NOA base -> growth suppressed
    bs_neg = pd.DataFrame([bs_row(2023, 300, 400, 300, 50),
                           bs_row(2024, 1180, 470, 380, 60)])
    _, s2, _ = compute_capital_bridge(bs_neg, is_, comp, cf, cash)
    r2 = s2[s2.end_date == "20241231"].iloc[0]
    assert pd.isna(r2.noa_growth)
    assert "negative_noa_base" in r2.cap_flags


def test_da_not_disclosed_flagged():
    bs, is_, comp, cf, cash = base_inputs()
    cf_only_capex = cf[cf.concept == "capex_paid"]
    _, s, _ = compute_capital_bridge(bs, is_, comp, cf_only_capex, cash)
    r = s[s.end_date == "20241231"].iloc[0]
    assert pd.isna(r.da_total) and pd.isna(r.capex_to_da)
    assert "da_not_disclosed" in r.cap_flags
    assert r.capex_paid == 50  # capex itself still reported


def test_missing_fcf_simple_gives_nan_diff():
    bs, is_, comp, cf, _ = base_inputs()
    empty_cash = pd.DataFrame(columns=["ts_code", "end_date", "fcf_simple"])
    _, s, _ = compute_capital_bridge(bs, is_, comp, cf, empty_cash)
    r = s[s.end_date == "20241231"].iloc[0]
    assert r.fcf_from_oi == pytest.approx(90)
    assert pd.isna(r.fcf_simple) and pd.isna(r.fcf_articulation_diff)
