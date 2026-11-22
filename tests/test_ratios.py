"""Offline tests for the ratio & decomposition engine (Module 4)."""
import numpy as np
import pandas as pd
import pytest

from pipeline.ratios import compute_ratios


def bs_row(end_date, noa, nfo, ol=0.0, mi=0.0):
    return dict(ts_code="T", end_date=end_date, oa=noa + ol, fa=0.0, ol=ol,
                fo=nfo, noa=noa, nfo=nfo, minority_interests=mi,
                cse_calc=noa - nfo - mi,
                total_assets_reported=np.nan, total_liabilities_reported=np.nan,
                parent_equity_reported=np.nan, r1_assets_residual=0.0,
                r2_liab_residual=0.0, r3_cse_residual=0.0)


def is_row(end_date, oi, nfe, rev, ni_parent=None, cogs=400.0):
    ni = oi - nfe
    return dict(ts_code="T", end_date=end_date, period_kind="cumulative",
                revenue=rev, total_revenue=rev, oi_core_pretax=np.nan,
                unusual_pretax=0.0, oi_pretax=np.nan, nfe_pretax=np.nan,
                tax_reported=np.nan, tax_rate_assumed=0.25,
                nfe_after_tax=nfe, oi_after_tax=oi, oi_core_after_tax=oi,
                ni_total=ni, ni_parent=ni if ni_parent is None else ni_parent,
                minority_income=0.0, comprehensive_income_total=np.nan,
                r4_pretax_residual=0.0, cogs=cogs)


def components(end_date, inventory=200.0, ppe=300.0):
    return [dict(ts_code="T", end_date=end_date, concept="inventory",
                 effective_class="operating_asset", value=inventory),
            dict(ts_code="T", end_date=end_date, concept="ppe",
                 effective_class="operating_asset", value=ppe)]


def two_year_inputs(noa0=1000.0, noa1=1200.0, nfo0=400.0, nfo1=400.0,
                    oi=150.0, nfe=12.0, rev=1000.0):
    bs = pd.DataFrame([bs_row("20221231", noa0, nfo0), bs_row("20231231", noa1, nfo1)])
    is_ = pd.DataFrame([is_row("20221231", 100.0, 10.0, 900.0),
                        is_row("20231231", oi, nfe, rev)])
    comp = pd.DataFrame(components("20221231") + components("20231231"))
    return bs, is_, comp


def get(df, year, basis):
    return df[(df.end_date == f"{year}1231") & (df.basis == basis)].iloc[0]


def test_rnoa_decomposition_and_leverage_identity():
    ratios = compute_ratios(*two_year_inputs())
    r = get(ratios, 2023, "average")
    assert abs(r.noa_capital - 1100.0) < 1e-9          # (1000+1200)/2
    assert abs(r.rnoa - 150.0 / 1100.0) < 1e-12
    assert abs(r.rnoa - r.opm * r.ato) < 1e-12          # K1
    assert abs(r.nbc - 12.0 / 400.0) < 1e-12
    assert abs(r.rotce - r.rotce_direct) < 1e-12        # K2 exact
    o = get(ratios, 2023, "opening")
    assert abs(o.noa_capital - 1000.0) < 1e-9
    assert abs(o.rnoa - 0.15) < 1e-12
    assert abs(o.rotce - o.rotce_direct) < 1e-12


def test_first_year_flagged_not_imputed():
    ratios = compute_ratios(*two_year_inputs())
    r = get(ratios, 2022, "average")
    assert r.ratio_flags == "no_opening_balance"
    assert "rnoa" not in r or pd.isna(r.get("rnoa"))


def test_negative_nfo_net_financial_assets_identity_still_exact():
    # Moutai shape: NFO < 0, NBC becomes return on net financial assets
    ratios = compute_ratios(*two_year_inputs(nfo0=-500.0, nfo1=-700.0,
                                             nfe=-20.0))
    r = get(ratios, 2023, "average")
    assert "net_financial_assets" in r.ratio_flags
    assert r.flev < 0
    assert abs(r.rotce - r.rotce_direct) < 1e-12
    assert r.rotce_direct < r.rnoa  # cash drag: ROTCE below RNOA


def test_near_zero_nfo_suppresses_nbc_not_rotce():
    ratios = compute_ratios(*two_year_inputs(nfo0=10.0, nfo1=-10.0, nfe=1.0))
    r = get(ratios, 2023, "average")  # avg NFO = 0, |0| < 5% of revenue
    assert "nfo_near_zero_suppressed" in r.ratio_flags
    assert pd.isna(r.nbc) and pd.isna(r.spread) and pd.isna(r.rotce)
    assert not pd.isna(r.rotce_direct)  # direct computation still reported


def test_near_zero_noa_suppresses_percentage_returns():
    ratios = compute_ratios(*two_year_inputs(noa0=30.0, noa1=-30.0))
    r = get(ratios, 2023, "average")
    assert "noa_near_zero_suppressed" in r.ratio_flags
    assert pd.isna(r.rnoa) and pd.isna(r.ato)


def test_parent_roce_separate_from_identity():
    bs, is_, comp = two_year_inputs()
    # minority: parent gets less than total income; CSE < TE
    bs.loc[:, "minority_interests"] = 100.0
    bs.loc[:, "cse_calc"] = bs.noa - bs.nfo - 100.0
    is_.loc[is_.end_date == "20231231", "ni_parent"] = 120.0
    ratios = compute_ratios(bs, is_, comp)
    r = get(ratios, 2023, "average")
    cse_avg = ((1000 - 400 - 100) + (1200 - 400 - 100)) / 2
    assert abs(r.roce_parent - 120.0 / cse_avg) < 1e-12
    assert abs(r.rotce - r.rotce_direct) < 1e-12  # total-level identity unaffected


def test_component_to_sales_decomposition():
    ratios = compute_ratios(*two_year_inputs())
    r = get(ratios, 2023, "average")
    assert abs(r.inventory_to_sales - 200.0 / 1000.0) < 1e-12
    assert abs(r.ppe_to_sales - 300.0 / 1000.0) < 1e-12
    assert abs(r.gross_margin - 0.6) < 1e-12  # (1000-400)/1000
