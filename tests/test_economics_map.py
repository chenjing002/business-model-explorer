"""Offline tests for the Business Economics Map assembly (Module 8)."""
import json

import numpy as np
import pandas as pd
import pytest

from pipeline.economics_map import build_econ_map
from pipeline.store import Store


@pytest.fixture
def seeded(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    ed = "20231231"
    frames = {
        # OA=900 (inv 300, AR 100, ppe 350, intang 50, other 100), FA=200
        # OL=150, FO=250, MI=50, CSE=650, TA=1100
        "reformulated_bs": pd.DataFrame([dict(
            ts_code="T", end_date=ed, oa=900.0, fa=200.0, ol=150.0, fo=250.0,
            noa=750.0, nfo=50.0, minority_interests=50.0, cse_calc=650.0,
            total_assets_reported=1100.0, total_liabilities_reported=400.0,
            parent_equity_reported=650.0, r1_assets_residual=0.0,
            r2_liab_residual=0.0, r3_cse_residual=0.0)]),
        "reformulated_is": pd.DataFrame([dict(
            ts_code="T", end_date=ed, period_kind="cumulative",
            total_revenue=1000.0, oi_core_pretax=500.0, unusual_pretax=10.0,
            oi_after_tax=385.0, r4_pretax_residual=0.0)]),
        "reformulated_bs_components": pd.DataFrame([
            dict(ts_code="T", end_date=ed, concept=c, effective_class=cl, value=v)
            for c, cl, v in [
                ("inventory", "operating_asset", 300.0),
                ("accounts_receivable", "operating_asset", 100.0),
                ("ppe", "operating_asset", 350.0),
                ("intangible_assets", "operating_asset", 50.0),
                ("deferred_tax_assets", "operating_asset", 100.0),
                ("cash_and_equivalents", "financial_asset", 200.0),
                ("accounts_payable", "operating_liability", 90.0),
                ("contract_liabilities", "operating_liability", 40.0),
                ("taxes_payable", "operating_liability", 20.0),
                ("long_term_borrowings", "financial_obligation", 250.0)]]),
        "cash_bridge_annual": pd.DataFrame([
            dict(ts_code="T", end_date=ed, step_order=i, concept=c, label=c,
                 value=v, step_kind=k)
            for i, (c, v, k) in enumerate([
                ("supp_net_profit", 400.0, "start"),
                ("supp_depreciation", 80.0, "adjustment"),
                ("supp_inventory_decrease", -30.0, "adjustment"),
                ("supp_operating_payables_increase", 50.0, "adjustment"),
                ("supp_cfo_indirect", 500.0, "total")])]),
        "cash_summary_annual": pd.DataFrame([dict(
            ts_code="T", end_date=ed, cfo=500.0, capex_paid=120.0,
            fcf_simple=380.0, c1_bridge_residual=0.0)]),
        "std_facts": pd.DataFrame([
            dict(ts_code="T", end_date=ed, report_type="1", statement=st,
                 concept=c, raw_field=c, label_zh="", penman_class="x",
                 note="", value=v, value_type="reported",
                 period_kind="cumulative", basis="consolidated",
                 unit="CNY_yuan", f_ann_date="", update_flag="0",
                 source_row_hash="h", mapping_version="1")
            for st, c, v in [
                ("income", "revenue", 950.0),
                ("income", "cost_of_goods_sold", 380.0),
                ("cashflow", "cfo", 500.0),
                ("cashflow", "cfi", -150.0),
                ("cashflow", "cff", -330.0),
                ("cashflow", "fx_effect_on_cash", -5.0),
                ("cashflow", "net_increase_in_cash", 15.0),
                ("cashflow", "capex_paid", 120.0),
                ("cashflow", "dividends_and_interest_paid", 200.0),
                ("cashflow", "debt_repayments", 100.0),
                ("cashflow", "other_financing_cash_paid", 30.0)]]),
    }
    for table, df in frames.items():
        s.con.register("_df", df)
        s.con.execute(f"CREATE TABLE {table} AS SELECT * FROM _df")
        s.con.unregister("_df")
    yield s
    s.close()


def nv(nodes, node_id):
    return nodes[nodes.node_id == node_id].iloc[0]


def test_layer1_sources_sum_to_total_assets(seeded):
    nodes, checks = build_econ_map(seeded, "T")
    assert nv(nodes, "supplier_credit").value == 90.0
    assert nv(nodes, "customer_advances").value == 40.0
    assert nv(nodes, "other_operating_liabilities").value == 20.0  # OL remainder
    l1 = checks[checks.check == "L1_sources_vs_total_assets"].iloc[0]
    assert abs(l1.residual) < 1e-9


def test_layer2_employment_sums_and_remainder(seeded):
    nodes, checks = build_econ_map(seeded, "T")
    assert nv(nodes, "inventory").value == 300.0
    assert nv(nodes, "other_operating_assets").value == 100.0  # deferred tax
    assert nv(nodes, "financial_assets").value == 200.0
    l2 = checks[checks.check == "L2_employment_vs_total_assets"].iloc[0]
    assert abs(l2.residual) < 1e-9


def test_layer3_gross_profit_and_r4_carried(seeded):
    nodes, checks = build_econ_map(seeded, "T")
    assert nv(nodes, "gross_profit").value == 950.0 - 380.0
    assert abs(checks[checks.check == "L3_pretax_classification_residual"]
               .iloc[0].residual) < 1e-9


def test_layer4_bridge_grouping(seeded):
    nodes, _ = build_econ_map(seeded, "T")
    assert nv(nodes, "net_income").value == 400.0
    assert nv(nodes, "noncash_addbacks").value == 80.0
    assert nv(nodes, "owc_change").value == 20.0  # -30 + 50
    comps = json.loads(nv(nodes, "owc_change").components_json)
    assert {c["concept"] for c in comps} == {
        "supp_inventory_decrease", "supp_operating_payables_increase"}


def test_layer5_identity_and_honest_notes(seeded):
    nodes, checks = build_econ_map(seeded, "T")
    l5 = checks[checks.check == "L5_cash_statement_identity"].iloc[0]
    assert abs(l5.residual) < 1e-9  # 500-150-330-5 = 15
    assert "NOT knowable" in nv(nodes, "capex_alloc").note
    assert "includes interest" in nv(nodes, "dividends_interest").note
    assert "buybacks" in nv(nodes, "other_financing_out").note


def test_related_metrics_declared_not_computed(seeded):
    nodes, _ = build_econ_map(seeded, "T")
    assert json.loads(nv(nodes, "inventory").related_json) == [
        "dio", "inventory_to_sales"]
    assert nv(nodes, "inventory").flow_or_stock == "stock"
    assert nv(nodes, "cfo").flow_or_stock == "flow"
