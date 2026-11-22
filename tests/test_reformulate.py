"""Offline tests for the Penman reformulation engine (Module 3).

Fixtures build std_facts-shaped frames directly (the mapping layer's output
contract), so these tests need no token and no database.
"""
import numpy as np
import pandas as pd
import pytest

from pipeline.reformulate import reformulate_bs, reformulate_is


def fact(statement, concept, value, penman_class, end_date="20231231",
         period_kind=None, value_type="reported"):
    default_pk = "point" if statement == "balancesheet" else "cumulative"
    return dict(
        ts_code="TEST.SH", end_date=end_date, report_type="1",
        statement=statement, concept=concept, raw_field=concept,
        label_zh="", penman_class=penman_class, note="", value=float(value),
        value_type=value_type, period_kind=period_kind or default_pk,
        basis="consolidated", unit="CNY_yuan", f_ann_date="", update_flag="0",
        source_row_hash="h", mapping_version="1",
    )


def simple_bs_facts():
    """OA=900 (inv 300, ppe 600); FA=200 cash; OL=150 payables; FO=250 debt;
    MI=50; equity: NOA=750, NFO=50, CSE=650."""
    return [
        fact("balancesheet", "inventory", 300, "operating_asset"),
        fact("balancesheet", "ppe", 600, "operating_asset"),
        fact("balancesheet", "cash_and_equivalents", 200, "financial_asset"),
        fact("balancesheet", "accounts_payable", 150, "operating_liability"),
        fact("balancesheet", "long_term_borrowings", 250, "financial_obligation"),
        fact("balancesheet", "minority_interests", 50, "minority_interest"),
        fact("balancesheet", "total_assets", 1100, "subtotal"),
        fact("balancesheet", "total_liabilities", 400, "subtotal"),
        fact("balancesheet", "parent_equity", 650, "subtotal"),
    ]


def test_bs_reformulation_identities():
    bs, decisions, _ = reformulate_bs(pd.DataFrame(simple_bs_facts()), {})
    r = bs.iloc[0]
    assert r.noa == 750 and r.nfo == 50 and r.cse_calc == 650
    assert r.r1_assets_residual == 0 and r.r2_liab_residual == 0
    assert r.r3_cse_residual == 0
    assert decisions.empty


def test_bs_residual_reported_not_forced():
    facts = simple_bs_facts()
    # 30 of assets exist in the reported total but are not classified anywhere
    facts = [f for f in facts if f["concept"] != "inventory"]
    facts.append(fact("balancesheet", "inventory", 270, "operating_asset"))
    bs, _, _ = reformulate_bs(pd.DataFrame(facts), {})
    assert bs.iloc[0].r1_assets_residual == 30  # reported, never zeroed


def test_negative_nfo_net_financial_assets():
    # The Moutai shape: huge cash, no debt -> NFO < 0
    facts = [
        fact("balancesheet", "ppe", 100, "operating_asset"),
        fact("balancesheet", "cash_and_equivalents", 500, "financial_asset"),
        fact("balancesheet", "accounts_payable", 40, "operating_liability"),
        fact("balancesheet", "parent_equity", 560, "subtotal"),
        fact("balancesheet", "total_equity", 560, "subtotal"),
    ]
    bs, _, _ = reformulate_bs(pd.DataFrame(facts), {})
    r = bs.iloc[0]
    assert r.nfo == -500 and r.noa == 60
    assert r.cse_calc == 560 and r.r3_cse_residual == 0  # implied by the two reported equity totals


def test_override_changes_class_and_is_recorded():
    overrides = {"TEST.SH": {"balancesheet": {"cash_and_equivalents": {
        "class": "operating_asset", "reason": "treat all cash as operating"}}}}
    bs, decisions, _ = reformulate_bs(pd.DataFrame(simple_bs_facts()), overrides)
    r = bs.iloc[0]
    assert r.oa == 1100 and r.fa == 0 and r.nfo == 250
    assert r.cse_calc == 650  # CSE invariant to the split
    d = decisions.iloc[0]
    assert d.kind == "override" and d.concept == "cash_and_equivalents"
    assert "operating" in d.reason


def coalesce_facts(granular_ar, combined):
    facts = [
        fact("balancesheet", "accounts_receivable", granular_ar, "operating_asset"),
        fact("balancesheet", "receivables_combined", combined, "presentation_combined"),
        fact("balancesheet", "parent_equity", 0, "subtotal"),
    ]
    return pd.DataFrame(facts)


def test_coalesce_granular_match_uses_granular_once():
    bs, decisions, _ = reformulate_bs(coalesce_facts(100e6, 100e6), {})
    assert bs.iloc[0].oa == 100e6  # not double counted
    assert (decisions.choice == "granular_match").any()


def test_coalesce_combined_used_when_granular_incomplete():
    # combined 120M > granular 100M (notes_receivable missing this period)
    bs, decisions, _ = reformulate_bs(coalesce_facts(100e6, 120e6), {})
    assert bs.iloc[0].oa == 120e6  # whole combined lump, granular excluded
    d = decisions[decisions.choice == "combined_used"].iloc[0]
    assert "120000000" in d.reason


def simple_is_facts(**over):
    vals = dict(revenue=1000, cost_of_goods_sold=400, selling_expenses=100,
                net_finance_expense=-20,  # net interest income
                non_operating_income=10, income_tax_expense=130,
                pretax_profit=530, net_income_total=400)
    vals.update(over)
    cls = dict(revenue="operating_income", cost_of_goods_sold="operating_expense",
               selling_expenses="operating_expense", net_finance_expense="financing",
               non_operating_income="operating_income",
               income_tax_expense="tax", pretax_profit="subtotal",
               net_income_total="subtotal")
    return pd.DataFrame([fact("income", k, v, cls[k]) for k, v in vals.items()])


def test_is_reformulation_and_tax_allocation():
    is_ = reformulate_is(simple_is_facts(), {}, tax_rate=0.25)
    r = is_.iloc[0]
    assert r.oi_core_pretax == 500            # 1000 - 400 - 100
    assert r.unusual_pretax == 10
    assert r.nfe_pretax == -20                # net financial income
    assert abs(r.r4_pretax_residual) < 1e-9   # 530 = 510 - (-20)
    assert r.nfe_after_tax == -15             # -20 * 0.75
    assert r.oi_after_tax == 385              # NI 400 + (-15)
    assert abs(r.oi_core_after_tax - 377.5) < 1e-9
    assert r.tax_rate_assumed == 0.25


def test_is_r4_residual_reports_unclassified():
    # pretax_profit includes 50 of income from a line we did not classify
    is_ = reformulate_is(simple_is_facts(pretax_profit=580), {}, tax_rate=0.25)
    assert abs(is_.iloc[0].r4_pretax_residual - 50) < 1e-9


def test_is_memo_lines_excluded():
    df = pd.concat([simple_is_facts(),
                    pd.DataFrame([fact("income", "finance_interest_expense",
                                       999, "financing")])])
    is_ = reformulate_is(df, {}, tax_rate=0.25)
    assert abs(is_.iloc[0].r4_pretax_residual) < 1e-9  # memo not summed


def test_single_quarter_uses_classified_cumulative_flows():
    q3 = simple_is_facts().assign(end_date="20230930")
    fy = simple_is_facts(revenue=1400, pretax_profit=900, net_income_total=770)
    # Missing in Q3 raw statements, disclosed in December as a 30 loss
    # year-to-date (post-2019 display sign: loss is negative).
    fy = pd.concat([fy, pd.DataFrame([
        fact("income", "asset_impairment_loss", -30, "operating_expense"),
    ])])
    result = reformulate_is(pd.concat([q3, fy]), {})
    q4 = result[(result.end_date == "20231231") & (result.period_kind == "single_quarter")].iloc[0]
    assert q4.revenue == 400
    assert q4.unusual_pretax == -30
    assert q4.r4_pretax_residual == 0
    assert q4.tax_rate_assumed == 0.25
    assert result[result.end_date == "20230930"].period_kind.tolist() == ["cumulative"]


def test_period_sign_override_preserves_reported_value():
    facts = simple_is_facts(pretax_profit=535)
    facts = pd.concat([facts, pd.DataFrame([
        fact("income", "credit_impairment_loss", -5, "operating_expense"),
    ])])
    rules = {"TEST.SH": {"income_sign_by_period": {
        "20231231": {"credit_impairment_loss": {"sign": -1}},
    }}}
    row = reformulate_is(facts, rules).iloc[0]
    assert row.unusual_pretax == 15
    assert row.r4_pretax_residual == 0
    assert '"-raw:credit_impairment_loss"' in row.is_terms
    assert facts.loc[facts.concept == "credit_impairment_loss", "value"].item() == -5


@pytest.mark.parametrize("concept", ["asset_impairment_loss", "credit_impairment_loss"])
def test_impairment_sign_follows_statement_format(concept):
    """Old CAS layout (to FY2018): a 30 loss is stored as +30 inside 营业总成本.
    财会〔2019〕6号 layout (from the 2019 interim): stored as −30."""
    for end_date, stored in [("20181231", 30), ("20191231", -30)]:
        facts = simple_is_facts(pretax_profit=500).assign(end_date=end_date)
        facts = pd.concat([facts, pd.DataFrame([
            fact("income", concept, stored, "operating_expense", end_date=end_date)])])
        row = reformulate_is(facts, {}).iloc[0]
        assert row.unusual_pretax == 10 - 30, end_date  # non-operating income + impairment
        assert row.r4_pretax_residual == 0, end_date


def test_impairment_sign_read_from_total_operating_costs():
    """FY2017 restated comparative: a 30,000 loss is stored with the new display
    sign (−30,000) while 营业总成本 still includes it as +30,000 — the
    statement's own subtotal decides, not the period default."""
    loss = 30_000  # above the ¥1,000 absolute tolerance; tinier lines stay ambiguous
    def with_total(stored, total):
        facts = simple_is_facts(pretax_profit=530 - loss).assign(end_date="20171231")
        return pd.concat([facts, pd.DataFrame([
            fact("income", "asset_impairment_loss", stored, "operating_expense", end_date="20171231"),
            fact("income", "total_operating_costs", total, "subtotal", end_date="20171231")])])
    # cost_of_goods_sold 400 + selling 100 + net finance expense −20 = 480 besides impairment
    row = reformulate_is(with_total(-loss, 480 + loss), {}).iloc[0]
    assert row.r4_pretax_residual == 0 and row.unusual_pretax == 10 - loss
    assert '"raw:asset_impairment_loss"' in row.is_terms
    # old layout as stored (+loss inside 营业总成本): expense-signed, as the period default
    row = reformulate_is(with_total(loss, 480 + loss), {}).iloc[0]
    assert row.r4_pretax_residual == 0 and '"-raw:asset_impairment_loss"' in row.is_terms
    # 营业总成本 that matches neither sign (unmapped cost lines): period default
    row = reformulate_is(with_total(-loss, 999_999), {}).iloc[0]
    assert '"-raw:asset_impairment_loss"' in row.is_terms and row.r4_pretax_residual == -2 * loss
