"""Offline tests for the economics-map annual evolution (Module 8 extension)."""
import numpy as np
import pandas as pd
import pytest

from pipeline.econ_evolution import GROUPS, compute_econ_evolution


def _bs(ed, **kw):
    return dict(ts_code="T", end_date=ed, **kw)


@pytest.fixture
def frames():
    bs = pd.DataFrame([
        # 2022: OA=800 (inv 250, AR 90, ppe 340, intang 40, other 80), FA=180
        #       OL=140 (AP 80, contract 40, taxes 20), FO=240, MI=40, CSE=560
        _bs("20221231", oa=800.0, fa=180.0, ol=140.0, fo=240.0,
            minority_interests=40.0, cse_calc=560.0,
            total_assets_reported=980.0),
        # 2023: OA=900 (inv 300, AR 100, ppe 350, intang 50, other 100), FA=200
        #       OL=150 (AP 90, contract 40, taxes 20), FO=250, MI=50, CSE=650
        _bs("20231231", oa=900.0, fa=200.0, ol=150.0, fo=250.0,
            minority_interests=50.0, cse_calc=650.0,
            total_assets_reported=1100.0),
    ])
    is_ = pd.DataFrame([
        dict(ts_code="T", end_date="20231231", period_kind="cumulative",
             ni_parent=100.0, ni_total=112.0),
    ])
    comp_rows = []
    for ed, vals in [
        ("20221231", [("inventory", "operating_asset", 250.0),
                      ("accounts_receivable", "operating_asset", 90.0),
                      ("ppe", "operating_asset", 340.0),
                      ("intangible_assets", "operating_asset", 40.0),
                      ("deferred_tax_assets", "operating_asset", 80.0),
                      ("cash_and_equivalents", "financial_asset", 180.0),
                      ("accounts_payable", "operating_liability", 80.0),
                      ("contract_liabilities", "operating_liability", 40.0),
                      ("taxes_payable", "operating_liability", 20.0)]),
        ("20231231", [("inventory", "operating_asset", 300.0),
                      ("accounts_receivable", "operating_asset", 100.0),
                      ("ppe", "operating_asset", 350.0),
                      ("intangible_assets", "operating_asset", 50.0),
                      ("deferred_tax_assets", "operating_asset", 100.0),
                      ("cash_and_equivalents", "financial_asset", 200.0),
                      ("accounts_payable", "operating_liability", 90.0),
                      ("contract_liabilities", "operating_liability", 40.0),
                      ("taxes_payable", "operating_liability", 20.0)]),
    ]:
        comp_rows += [dict(ts_code="T", end_date=ed, concept=c,
                           effective_class=cl, value=v) for c, cl, v in vals]
    comp = pd.DataFrame(comp_rows)
    cf = pd.DataFrame([
        dict(ts_code="T", end_date="20231231", statement="cashflow",
             report_type="1", period_kind="cumulative", value_type="reported",
             concept=c, value=v)
        for c, v in [
            ("supp_inventory_decrease", -50.0),           # inventory grew 50
            ("supp_operating_receivables_decrease", -8.0),  # recv grew 8
            ("supp_operating_payables_increase", 9.0),
            ("capex_paid", 35.0),
            ("supp_depreciation", 20.0),
            ("supp_rou_asset_depreciation", 2.0),
            ("supp_intangible_amortization", 3.0),
            ("supp_lt_deferred_amortization", 1.0),
            ("cash_from_asset_disposals", 1.0),
            ("net_increase_in_cash", 15.0),
            ("minority_equity_contributions", 1.0),
            ("dividends_paid_to_minority", 4.0),
            ("cash_from_borrowings", 30.0),
            ("debt_repayments", 25.0),
            # net_increase_deposits_taken intentionally NOT disclosed
            ("cash_beginning", 60.0),
            ("cash_ending", 75.0),
        ]])
    return bs, is_, comp, cf


@pytest.fixture
def result(frames):
    return compute_econ_evolution(*frames)


def steps(flows, panel):
    return flows[(flows.panel_id == panel)
                 & (flows.end_date == "20231231")].sort_values("step_order")


def item(flows, panel, concept):
    rows = steps(flows, panel)
    sel = rows[rows.concept == concept]
    return sel.iloc[0] if not sel.empty else None


def test_first_year_has_no_opening_and_no_flows(result):
    groups, flows, checks = result
    y1 = groups[groups.end_date == "20221231"]
    assert len(y1) == len(GROUPS)
    assert y1.begin_value.isna().all() and y1.delta.isna().all()
    assert (y1.evo_flags == "no_opening_balance").all()
    assert flows[flows.end_date == "20221231"].empty
    assert checks[checks.end_date == "20221231"].empty


def test_side_deltas_match_reported_total_assets(result):
    _, _, checks = result
    for chk in ["E1_sources_delta_vs_reported_assets",
                "E2_employment_delta_vs_reported_assets"]:
        assert abs(checks[checks.check == chk].iloc[0].residual) < 1e-9


def test_every_panel_bridge_is_additive(result):
    groups, flows, checks = result
    e3 = checks[checks.check.str.startswith("E3_panel_additive_")]
    assert len(e3) == 9
    assert e3.residual.abs().max() < 1e-9
    # panel members cover every group exactly once
    covered = groups[groups.end_date == "20231231"].group_id.tolist()
    assert sorted(covered) == sorted(g for _, g, _, _ in GROUPS)


def test_disclosed_vs_inferred_split(result):
    _, flows, _ = result
    # inventory: BS delta +50 fully matches the supplemental line → residual 0
    assert item(flows, "inventory", "inventory_change_supp").value == 50.0
    assert item(flows, "inventory", "inferred_residual").value == 0.0
    # receivables: BS delta +10 vs disclosed +8 → inferred +2, left visible
    assert item(flows, "receivables_prepaid",
                "operating_receivables_change_supp").value == 8.0
    assert item(flows, "receivables_prepaid", "inferred_residual").value == 2.0
    # long-term operating: Δ20 = capex 35 − dep 22 − amort 4 − disposals 1 + 12
    lt = steps(flows, "long_term_operating")
    assert item(flows, "long_term_operating", "capex_paid").value == 35.0
    assert item(flows, "long_term_operating",
                "depreciation_disclosed").value == -22.0
    assert item(flows, "long_term_operating",
                "amortization_disclosed").value == -4.0
    assert item(flows, "long_term_operating",
                "inferred_residual").value == pytest.approx(12.0)
    assert lt.iloc[0].step_kind == "start" and lt.iloc[-1].step_kind == "total"
    assert lt.iloc[0].value == 380.0 and lt.iloc[-1].value == 400.0


def test_missing_disclosure_is_skipped_never_zero(result):
    _, flows, _ = result
    # net_increase_deposits_taken was not disclosed → no row, residual absorbs
    assert item(flows, "financial_debt", "net_increase_deposits_taken") is None
    assert item(flows, "financial_debt", "cash_from_borrowings").value == 30.0
    assert item(flows, "financial_debt", "debt_repayments").value == -25.0
    # ΔFO 10 = +30 − 25 + inferred 5
    assert item(flows, "financial_debt",
                "inferred_residual").value == pytest.approx(5.0)


def test_equity_residual_is_inferred_net_payout(result):
    _, flows, _ = result
    # ΔCSE 90 = NI 100 + inferred −10 (dividends/OCI, not separable)
    assert item(flows, "common_equity", "ni_parent").value == 100.0
    res = item(flows, "common_equity", "inferred_residual")
    assert res.value == pytest.approx(-10.0)
    assert "dividends" in res.note
    assert res.basis == "inferred_residual"
    # minority: Δ10 = NI 12 + contributions 1 − dividends 4 + inferred 1
    assert item(flows, "minority_interests", "ni_minority").value == 12.0
    assert item(flows, "minority_interests",
                "inferred_residual").value == pytest.approx(1.0)


def test_bases_are_declared_and_residual_notes_honest(result):
    _, flows, _ = result
    assert set(flows.basis) <= {"balance", "disclosed_cashflow",
                                "disclosed_supplemental", "disclosed_income",
                                "inferred_residual"}
    generic = item(flows, "other_operating_assets", "inferred_residual")
    assert "NOT a direct conversion" in generic.note
    # every panel carries exactly one residual row
    y2 = flows[flows.end_date == "20231231"]
    assert (y2[y2.concept == "inferred_residual"]
            .groupby("panel_id").size() == 1).all()


def test_delta_share_and_cash_rollforward(result):
    groups, _, checks = result
    inv = groups[(groups.end_date == "20231231")
                 & (groups.group_id == "inventory")].iloc[0]
    assert inv.delta == 50.0
    assert inv.delta_share_of_assets == pytest.approx(50.0 / 980.0)
    e4 = checks[checks.check == "E4_cash_rollforward"].iloc[0]
    assert abs(e4.residual) < 1e-9


def test_group_absent_in_one_year_is_a_structural_zero(frames):
    """2022 has no 合同负债 line at all (complete statement: OL 100 = AP 80 +
    taxes 20); 2023 discloses 40. The group opens at 0, not 'not disclosed'."""
    bs, is_, comp, cf = frames
    bs = bs.copy()
    bs.loc[bs.end_date == "20221231", ["ol", "cse_calc"]] = [100.0, 600.0]
    comp = comp[~((comp.end_date == "20221231") & (comp.concept == "contract_liabilities"))]
    groups, _, checks = compute_econ_evolution(bs, is_, comp, cf)
    adv = groups[(groups.end_date == "20231231") & (groups.group_id == "customer_advances")].iloc[0]
    assert (adv.begin_value, adv.end_value, adv.delta) == (0.0, 40.0, 40.0)
    assert adv.evo_flags == "group_absent_begin"
    e1 = checks[(checks.end_date == "20231231") & (checks.check == "E1_sources_delta_vs_reported_assets")]
    assert abs(e1.iloc[0].residual) < 1e-9
    # a group with no lines in either year stays undisclosed, not 0 → 0
    groups_none, _, _ = compute_econ_evolution(bs, is_, comp[comp.concept != "contract_liabilities"], cf)
    none = groups_none[(groups_none.end_date == "20231231") & (groups_none.group_id == "customer_advances")].iloc[0]
    assert pd.isna(none.delta) and none.evo_flags == "balance_not_disclosed"
