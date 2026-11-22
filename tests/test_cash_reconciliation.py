"""Offline tests for the earnings-to-cash reconciliation (Module 6)."""
import numpy as np
import pandas as pd

from pipeline.cash_reconciliation import build_bridge


def fact(statement, concept, value, end_date="20231231"):
    return dict(ts_code="T", end_date=end_date, report_type="1",
                statement=statement, concept=concept, raw_field=concept,
                label_zh="", penman_class="x", note="", value=float(value),
                value_type="reported", period_kind="cumulative",
                basis="consolidated", unit="CNY_yuan", f_ann_date="",
                update_flag="0", source_row_hash="h", mapping_version="1")


def full_year(end_date="20231231", ni=400.0, cfo=500.0):
    """Consistent year: bridge sums exactly to CFO."""
    return [
        fact("income", "net_income_total", ni, end_date),
        fact("cashflow", "supp_net_profit", ni, end_date),
        fact("cashflow", "supp_depreciation", 80.0, end_date),
        fact("cashflow", "supp_intangible_amortization", 10.0, end_date),
        fact("cashflow", "supp_investment_loss", -5.0, end_date),   # income
        fact("cashflow", "supp_inventory_decrease", -40.0, end_date),  # build
        fact("cashflow", "supp_operating_payables_increase", 55.0, end_date),
        fact("cashflow", "supp_cfo_indirect", cfo, end_date),
        fact("cashflow", "cfo", cfo, end_date),
        fact("cashflow", "capex_paid", 120.0, end_date),
        fact("cashflow", "cash_from_asset_disposals", 3.0, end_date),
    ]


def test_bridge_sums_and_residual_zero():
    bridge, summary = build_bridge(pd.DataFrame(full_year()))
    s = summary.iloc[0]
    assert abs(s.c1_bridge_residual) < 1e-9     # 400+80+10-5-40+55 = 500
    assert abs(s.c2_indirect_vs_direct) < 1e-9
    assert abs(s.c0_supp_vs_is_ni) < 1e-9
    # ordered steps: start, adjustments, total; undisclosed items absent
    assert list(bridge.step_kind)[:1] == ["start"]
    assert bridge.step_kind.iloc[-1] == "total"
    assert bridge.step_order.is_monotonic_increasing
    assert "supp_fair_value_loss" not in set(bridge.concept)  # not disclosed


def test_residual_reported_not_forced():
    rows = full_year()
    # reported indirect CFO disagrees with the sum of its own components
    rows = [r for r in rows if r["concept"] != "supp_cfo_indirect"]
    rows.append(fact("cashflow", "supp_cfo_indirect", 510.0))
    _, summary = build_bridge(pd.DataFrame(rows))
    assert abs(summary.iloc[0].c1_bridge_residual - (-10.0)) < 1e-9
    assert abs(summary.iloc[0].c2_indirect_vs_direct - 10.0) < 1e-9


def test_fcf_variants_and_definitions():
    _, summary = build_bridge(pd.DataFrame(full_year()))
    s = summary.iloc[0]
    assert abs(s.fcf_simple - (500.0 - 120.0)) < 1e-9
    assert abs(s.fcf_after_disposals - (380.0 + 3.0)) < 1e-9
    assert "CFO − cash capex" in s.fcf_simple_def
    assert abs(s.cash_conversion - 500.0 / 400.0) < 1e-9
    assert abs(s.accruals - (400.0 - 500.0)) < 1e-9


def test_missing_supplemental_flagged_no_bridge():
    rows = [fact("income", "net_income_total", 400.0),
            fact("cashflow", "cfo", 500.0),
            fact("cashflow", "capex_paid", 120.0)]
    bridge, summary = build_bridge(pd.DataFrame(rows))
    s = summary.iloc[0]
    assert "supplemental_not_disclosed" in s.cf_flags
    assert bridge.empty                       # no invented bars
    assert abs(s.fcf_simple - 380.0) < 1e-9   # FCF still computable


def test_ni_near_zero_suppresses_conversion_ratio():
    rows = full_year(ni=1.0)   # |NI| tiny vs CFO 500
    _, summary = build_bridge(pd.DataFrame(rows))
    s = summary.iloc[0]
    assert pd.isna(s.cash_conversion)
    assert "ni_near_zero_suppressed" in s.cf_flags


def test_multi_year_output():
    rows = full_year("20221231", ni=300.0, cfo=390.0) + full_year("20231231")
    # make 2022 consistent: adjust payables step so the bridge sums
    rows = [r for r in rows
            if not (r["end_date"] == "20221231"
                    and r["concept"] == "supp_operating_payables_increase")]
    rows.append(fact("cashflow", "supp_operating_payables_increase", 45.0,
                     "20221231"))
    bridge, summary = build_bridge(pd.DataFrame(rows))
    assert len(summary) == 2
    assert summary.c1_bridge_residual.abs().max() < 1e-9
    assert set(bridge.end_date) == {"20221231", "20231231"}
