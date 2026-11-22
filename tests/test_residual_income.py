"""Offline tests for residual income & the Value Creation Bridge (Module 11)."""
import numpy as np
import pandas as pd
import pytest

from pipeline.residual_income import compute_residual_income

R = 0.10


def bs_row(year, noa, nfo, mi=0.0):
    return dict(ts_code="T", end_date=f"{year}1231", noa=noa, nfo=nfo,
                minority_interests=mi, cse_calc=noa - nfo - mi)


def is_row(year, rev, oi, oi_core, ni_parent, ci=np.nan):
    return dict(ts_code="T", end_date=f"{year}1231", period_kind="cumulative",
                total_revenue=rev, oi_after_tax=oi, oi_core_after_tax=oi_core,
                ni_total=ni_parent, ni_parent=ni_parent,
                comprehensive_income_total=ci,
                comprehensive_income_parent=ci)


def ratio_row(year, rnoa, roce):
    return dict(ts_code="T", end_date=f"{year}1231", basis="opening",
                rnoa=rnoa, roce_parent=roce)


def base_inputs():
    """2022: ReOI = 200 − 0.1×500 = 150; 2023: ReOI = 250 − 0.1×600 = 190.
    Bridge 2023: sales 200×0.2 = 40, core margin 1200×(245/1200 − 0.19) = 17,
    unusual 5 − 12 = −7, capital charge −0.1×100 = −10 → Δ = 40.
    Drivers: ATO 2 → 2, margin (250/1200 − 0.2)×2×600 = 10, turnover 0,
    growth 0.3×100 = 30."""
    bs = pd.DataFrame([bs_row(2021, 500, -100), bs_row(2022, 600, -150),
                       bs_row(2023, 800, -200)])
    is_ = pd.DataFrame([is_row(2021, 900, 150, 150, 150),
                        is_row(2022, 1000, 200, 190, 205, ci=210),
                        is_row(2023, 1200, 250, 245, 260)])
    ratios = pd.DataFrame([ratio_row(2022, 200 / 500, 205 / 600),
                           ratio_row(2023, 250 / 600, 260 / 750)])
    return bs, is_, ratios


def run(*inputs):
    return compute_residual_income(*inputs, r_op=R, r_e=R)


def test_reoi_and_equity_re_levels():
    s, _, _ = run(*base_inputs())
    s = s.set_index("end_date")
    assert s.loc["20221231", "reoi"] == pytest.approx(150)
    assert s.loc["20231231", "reoi"] == pytest.approx(190)
    assert s.loc["20231231", "reoi_core"] == pytest.approx(245 - 60)
    assert s.loc["20221231", "re_common"] == pytest.approx(210 - 60)
    assert pd.isna(s.loc["20231231", "re_common"])
    assert s.loc["20231231", "spread_op"] == pytest.approx(250 / 600 - R)
    assert s.loc["20221231", "oci_total"] == pytest.approx(5)
    assert pd.isna(s.loc["20231231", "oci_total"])  # undisclosed stays null
    assert (s.r_op_assumed == R).all() and (s.r_e_assumed == R).all()


def test_value_bridge_steps_exact():
    s, b, checks = run(*base_inputs())
    b23 = b[b.end_date == "20231231"].set_index("concept")
    assert b23.loc["reoi_prev", "value"] == pytest.approx(150)
    assert b23.loc["sales_effect", "value"] == pytest.approx(40)
    assert b23.loc["core_margin_effect", "value"] == pytest.approx(17)
    assert b23.loc["unusual_effect", "value"] == pytest.approx(-7)
    assert b23.loc["capital_charge_effect", "value"] == pytest.approx(-10)
    assert b23.loc["reoi", "value"] == pytest.approx(190)
    kinds = b23.sort_values("step_order").step_kind.tolist()
    assert kinds == ["start"] + ["adjustment"] * 4 + ["total"]
    ri1 = checks[checks.check == "RI1_bridge_additive"]
    assert len(ri1) == 1 and ri1.residual.abs().max() < 1e-9


def test_penman_driver_split_exact():
    s, _, checks = run(*base_inputs())
    r = s.set_index("end_date").loc["20231231"]
    assert r.drivers_available
    assert r.margin_effect == pytest.approx(10)
    assert r.turnover_effect == pytest.approx(0, abs=1e-9)
    assert r.growth_effect == pytest.approx(30)
    assert r.delta_reoi == pytest.approx(40)
    ri2 = checks[checks.check == "RI2_driver_split_additive"]
    assert ri2.residual.abs().max() < 1e-9


def test_cross_checks_against_module4():
    _, _, checks = run(*base_inputs())
    for c in ["RI3_rnoa_vs_module4", "RI4_roce_vs_module4"]:
        sub = checks[checks.check == c]
        assert len(sub) == 2 and sub.residual.abs().max() < 1e-12
    bs, is_, ratios = base_inputs()
    ratios.loc[1, "rnoa"] += 0.01  # Module-4 disagreement must surface
    _, _, bad = run(bs, is_, ratios)
    ri3 = bad[(bad.check == "RI3_rnoa_vs_module4")
              & (bad.end_date == "20231231")]
    assert ri3.residual.iloc[0] == pytest.approx(-0.01)


def test_first_year_and_no_prior_reoi_flagged():
    s, b, _ = run(*base_inputs())
    s = s.set_index("end_date")
    r21 = s.loc["20211231"]
    assert "no_opening_balance" in r21.ri_flags and pd.isna(r21.reoi)
    r22 = s.loc["20221231"]  # has ReOI, but no prior ReOI → no bridge
    assert "no_prior_reoi" in r22.ri_flags and not r22.bridge_available
    assert set(b.end_date) == {"20231231"}


def test_negative_noa_base_keeps_reoi_and_bridge_but_suppresses_drivers():
    bs, is_, ratios = base_inputs()
    bs = pd.DataFrame([bs_row(2021, 500, -100), bs_row(2022, -50, -900),
                       bs_row(2023, 800, -200)])
    s, b, checks = run(bs, is_, ratios)
    r = s.set_index("end_date").loc["20231231"]
    assert r.reoi == pytest.approx(250 + 5)  # charge on negative NOA is a credit
    assert pd.isna(r.rnoa_open) and "negative_noa_base" in r.ri_flags
    assert r.bridge_available and not r.drivers_available
    assert "drivers_suppressed" in r.ri_flags
    assert checks[checks.check == "RI1_bridge_additive"].residual.abs().max() < 1e-9
    assert "RI2_driver_split_additive" not in set(checks.check)


def test_reoi_growth_suppressed_on_non_positive_base():
    bs, _, ratios = base_inputs()
    is_ = pd.DataFrame([is_row(2021, 900, 150, 150, 150),
                        # ReOI = 70 − 50 = 20 > 0 but < 5% of revenue (60)
                        is_row(2022, 1000, 70, 70, 70),
                        is_row(2023, 1200, 250, 245, 260)])
    s, _, _ = run(bs, is_, ratios)
    r = s.set_index("end_date").loc["20231231"]
    assert pd.isna(r.reoi_growth)
    assert "reoi_base_not_positive_suppressed" in r.ri_flags
    assert r.delta_reoi == pytest.approx(190 - 20)  # level change still reported
    assert r.oi_growth == pytest.approx(250 / 70 - 1)  # OI base 70 ≥ floor
    # negative prior ReOI is suppressed the same way
    is_neg = is_.copy()
    is_neg.loc[1, ["oi_after_tax", "oi_core_after_tax"]] = 40  # ReOI −10
    s2, _, _ = run(bs, is_neg, ratios)
    r2 = s2.set_index("end_date").loc["20231231"]
    assert pd.isna(r2.reoi_growth) and r2.delta_reoi == pytest.approx(200)


def test_capital_charge_scales_with_assumed_rate():
    bs, is_, ratios = base_inputs()
    lo, _, _ = compute_residual_income(bs, is_, ratios, r_op=0.05, r_e=0.05)
    hi, _, _ = compute_residual_income(bs, is_, ratios, r_op=0.15, r_e=0.15)
    d = (lo.set_index("end_date").reoi - hi.set_index("end_date").reoi).dropna()
    # ReOI difference = Δr × NOA_begin, exactly
    assert d.loc["20231231"] == pytest.approx(0.10 * 600)
