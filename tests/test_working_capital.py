"""Offline tests for working capital metrics and simulations (Module 5)."""
import numpy as np
import pandas as pd
import pytest

from pipeline.working_capital import (
    compute_wc_metrics,
    required_owc,
    simulate_efficiency_change,
    simulate_growth,
)


def comp(end_date, concept, value, cls="operating_asset"):
    return dict(ts_code="T", end_date=end_date, concept=concept,
                effective_class=cls, value=float(value))


def inc(end_date, concept, value):
    return dict(ts_code="T", end_date=end_date, report_type="1",
                statement="income", concept=concept, raw_field=concept,
                label_zh="", penman_class="x", note="", value=float(value),
                value_type="reported", period_kind="cumulative",
                basis="consolidated", unit="CNY_yuan", f_ann_date="",
                update_flag="0", source_row_hash="h", mapping_version="1")


def two_year_data():
    components = pd.DataFrame(
        [comp("20221231", "inventory", 100), comp("20221231", "accounts_receivable", 50),
         comp("20221231", "accounts_payable", 40, "operating_liability"),
         comp("20221231", "contract_liabilities", 20, "operating_liability"),
         comp("20231231", "inventory", 140), comp("20231231", "accounts_receivable", 70),
         comp("20231231", "accounts_payable", 60, "operating_liability"),
         comp("20231231", "contract_liabilities", 40, "operating_liability")])
    income = pd.DataFrame(
        [inc("20221231", "revenue", 900), inc("20221231", "cost_of_goods_sold", 350),
         inc("20231231", "revenue", 1000), inc("20231231", "cost_of_goods_sold", 400)])
    return components, income


def test_days_metrics_cross_check():
    wc = compute_wc_metrics(*two_year_data())
    r = wc[wc.end_date == "20231231"].iloc[0]
    assert abs(r.dio - 365 * 120 / 400) < 1e-9          # avg inv 120
    assert abs(r.dso - 365 * 60 / 1000) < 1e-9          # avg AR 60
    purchases = 400 + 40                                 # COGS + dInventory
    assert abs(r.purchases_est - purchases) < 1e-9
    assert abs(r.dpo - 365 * 50 / purchases) < 1e-9     # avg AP 50
    assert abs(r.dpo_cogs - 365 * 50 / 400) < 1e-9
    assert abs(r.ccc - (r.dio + r.dso - r.dpo)) < 1e-9
    assert abs(r.advance_days - 365 * 30 / 1000) < 1e-9
    assert abs(r.ccc_net_advances - (r.ccc - r.advance_days)) < 1e-9
    assert r.dpo_method == "purchases=COGS+dInventory"  # approximation disclosed


def test_owc_and_increments():
    wc = compute_wc_metrics(*two_year_data())
    r = wc[wc.end_date == "20231231"].iloc[0]
    assert abs(r.owc_end - (140 + 70 - 60 - 40)) < 1e-9     # 110
    assert abs(r.d_owc - (110 - 90)) < 1e-9                 # +20
    assert abs(r.d_revenue - 100) < 1e-9
    assert abs(r.incr_owc_per_incr_revenue - 0.2) < 1e-9


def test_first_year_flagged():
    wc = compute_wc_metrics(*two_year_data())
    assert wc[wc.end_date == "20221231"].iloc[0].wc_flags == "no_opening_balance"


def test_missing_receivables_is_nan_and_flagged():
    components, income = two_year_data()
    components = components[components.concept != "accounts_receivable"]
    wc = compute_wc_metrics(components, income)
    r = wc[wc.end_date == "20231231"].iloc[0]
    assert pd.isna(r.dso)
    assert pd.isna(r.ccc) and pd.isna(r.ccc_net_advances)  # missing stays missing
    assert "receivables_not_disclosed" in r.wc_flags
    assert not pd.isna(r.dio)  # other metrics unaffected


def test_no_customer_advances_leaves_netted_ccc_missing():
    components, income = two_year_data()
    components = components[components.concept != "contract_liabilities"]
    r = compute_wc_metrics(components, income).query("end_date == '20231231'").iloc[0]
    assert not pd.isna(r.ccc)
    assert pd.isna(r.advance_days) and pd.isna(r.ccc_net_advances)  # never netted as zero


def test_small_revenue_change_suppresses_incremental_ratio():
    components, income = two_year_data()
    income.loc[income.end_date == "20231231", "value"] = \
        income.loc[income.end_date == "20231231", "concept"].map(
            {"revenue": 901.0, "cost_of_goods_sold": 400.0})
    wc = compute_wc_metrics(components, income)
    r = wc[wc.end_date == "20231231"].iloc[0]
    assert pd.isna(r.incr_owc_per_incr_revenue)
    assert "delta_revenue_near_zero_suppressed" in r.wc_flags


def test_efficiency_simulation_releases_capital_without_touching_income():
    # Amazon lesson: doubling inventory turns frees cash, income unchanged.
    sim = simulate_efficiency_change(
        revenue=1000, cogs=600,
        base=dict(dio=60, dso=30, dpo=30),
        new=dict(dio=30, dso=30, dpo=30))
    released = 30 * 600 / 365  # half the inventory
    assert abs(sim["capital_released"] - released) < 1e-9
    assert "operating_income" not in sim["base"]  # income is not an output


def test_supplier_vs_customer_financing_separated():
    r = required_owc(1000, 600, dio=60, dso=0, dpo=30, advance_days=36.5)
    assert abs(r["advances"] - 100) < 1e-9
    assert abs(r["owc"] - (60 * 600 / 365 - 30 * 600 / 365 - 100)) < 1e-9


def test_growth_simulation_absorbs_cash_at_constant_efficiency():
    df = simulate_growth(revenue0=1000, cogs_ratio=0.6, growth=0.2, years=3,
                         days=dict(dio=60, dso=30, dpo=30))
    assert pd.isna(df.loc[0, "wc_investment"])
    # positive OWC and constant days -> every growth year absorbs cash
    assert (df.wc_investment.dropna() > 0).all()
    # investment itself grows with the base
    assert df.wc_investment.iloc[3] > df.wc_investment.iloc[1]
    # zero growth -> zero investment
    flat = simulate_growth(1000, 0.6, 0.0, 3, dict(dio=60, dso=30, dpo=30))
    assert (flat.wc_investment.dropna().abs() < 1e-9).all()
