"""Offline unit tests for accounting-identity validation (no token needed)."""
import numpy as np
import pandas as pd

from pipeline.validate import (
    coverage_report,
    results_to_frame,
    validate_balancesheet,
    validate_cashflow,
    validate_income,
)


def bs_row(**over):
    base = dict(
        ts_code="600519.SH", end_date="20231231", report_type="1",
        total_assets=272_658_000_000.0,
        total_liab=46_000_000_000.0,
        total_hldr_eqy_inc_min_int=226_658_000_000.0,
        total_hldr_eqy_exc_min_int=219_000_000_000.0,
        minority_int=7_658_000_000.0,
    )
    base.update(over)
    return base


def test_bs_identity_pass():
    df = pd.DataFrame([bs_row()])
    res = results_to_frame(validate_balancesheet(df))
    assert (res.status == "PASS").all()


def test_bs_identity_fail_reports_diff_without_correction():
    # Assets overstated by 5 million yuan -> must FAIL with exact diff.
    df = pd.DataFrame([bs_row(total_assets=272_663_000_000.0)])
    res = results_to_frame(validate_balancesheet(df))
    v1 = res[res.check == "V1_bs_identity"].iloc[0]
    assert v1.status == "FAIL"
    assert abs(v1["diff"] - 5_000_000.0) < 1.0


def test_bs_small_rounding_within_tolerance_passes():
    df = pd.DataFrame([bs_row(total_assets=272_658_000_000.0 + 500.0)])
    res = results_to_frame(validate_balancesheet(df))
    assert (res[res.check == "V1_bs_identity"].status == "PASS").all()


def test_missing_field_is_skip_not_imputed():
    df = pd.DataFrame([bs_row(minority_int=np.nan)])
    res = results_to_frame(validate_balancesheet(df))
    v2 = res[res.check == "V2_equity_composition"].iloc[0]
    assert v2.status == "SKIP"
    assert pd.isna(v2["diff"])


def test_income_identity():
    df = pd.DataFrame([dict(
        ts_code="600519.SH", end_date="20231231", report_type="1",
        n_income=77_521_000_000.0,
        total_profit=103_663_000_000.0,
        income_tax=26_142_000_000.0,
    )])
    res = results_to_frame(validate_income(df))
    assert (res.status == "PASS").all()
    # Tax misstated -> FAIL
    df.loc[0, "income_tax"] = 26_000_000_000.0
    res = results_to_frame(validate_income(df))
    assert (res.status == "FAIL").all()


def test_income_missing_tax_column_skips():
    df = pd.DataFrame([dict(
        ts_code="600519.SH", end_date="20231231", report_type="1",
        n_income=1.0, total_profit=2.0,
    )])
    res = results_to_frame(validate_income(df))
    assert (res.status == "SKIP").all()


def test_cashflow_identities():
    df = pd.DataFrame([dict(
        ts_code="600519.SH", end_date="20231231", report_type="1",
        n_cashflow_act=66_593_000_000.0,
        n_cashflow_inv_act=-4_706_000_000.0,
        n_cash_flows_fnc_act=-63_496_000_000.0,
        eff_fx_flu_cash=-9_000_000.0,
        n_incr_cash_cash_equ=-1_618_000_000.0,
        c_cash_equ_beg_period=60_000_000_000.0,
        c_cash_equ_end_period=58_382_000_000.0,
    )])
    res = results_to_frame(validate_cashflow(df))
    assert (res.status == "PASS").all()


def test_coverage_missing_annual_fails():
    df = pd.DataFrame([
        dict(ts_code="000001.SZ", end_date="20220331", report_type="1"),
        dict(ts_code="000001.SZ", end_date="20220630", report_type="1"),
        # 20221231 annual report missing for a completed year
        dict(ts_code="000001.SZ", end_date="20231231", report_type="1"),
    ])
    cov = coverage_report(df, "balancesheet")
    y2022 = cov[cov.year == "2022"].iloc[0]
    y2023 = cov[cov.year == "2023"].iloc[0]
    assert y2022.status == "FAIL"
    assert y2023.status == "PASS"


def test_coverage_ignores_parent_statements():
    df = pd.DataFrame([dict(ts_code="000001.SZ", end_date="20221231", report_type="6")])
    cov = coverage_report(df, "balancesheet")
    assert cov.empty
