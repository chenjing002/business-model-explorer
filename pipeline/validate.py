"""Accounting-identity validation for raw Tushare statements.

Every check yields PASS / FAIL / SKIP per statement row:
- PASS: identity holds within tolerance
- FAIL: identity violated (reported with the exact difference; never corrected)
- SKIP: required fields missing — flagged, never imputed

Tolerance: reported statements should satisfy identities essentially exactly;
we allow max(ABS_TOL yuan, REL_TOL of magnitude) for vendor rounding.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

ABS_TOL = 1000.0      # yuan — vendor unit-conversion rounding
REL_TOL = 1e-6        # identities in reported statements hold essentially exactly


@dataclass
class CheckResult:
    check: str
    ts_code: str
    end_date: str
    report_type: str
    status: str          # PASS / FAIL / SKIP
    lhs: float | None
    rhs: float | None
    diff: float | None
    note: str = ""


def _tol(lhs: float, rhs: float) -> float:
    return max(ABS_TOL, REL_TOL * max(abs(lhs), abs(rhs)))


def _check_identity(
    df: pd.DataFrame,
    check: str,
    lhs_cols: list[str],
    rhs_cols: list[str],
    note: str = "",
) -> list[CheckResult]:
    """Check sum(lhs_cols) == sum(rhs_cols) per row. NaN in a required column
    on either side -> SKIP for that row (missing data is flagged, not imputed).
    Columns absent from the frame entirely are treated as NaN.
    """
    results: list[CheckResult] = []
    for _, row in df.iterrows():
        def side(cols: list[str]) -> float | None:
            vals = [row.get(c, np.nan) for c in cols]
            if any(pd.isna(v) for v in vals):
                return None
            return float(sum(vals))

        lhs, rhs = side(lhs_cols), side(rhs_cols)
        meta = dict(
            check=check,
            ts_code=str(row.get("ts_code", "")),
            end_date=str(row.get("end_date", "")),
            report_type=str(row.get("report_type", "")),
            note=note,
        )
        if lhs is None or rhs is None:
            results.append(CheckResult(**meta, status="SKIP", lhs=lhs, rhs=rhs, diff=None))
            continue
        diff = lhs - rhs
        status = "PASS" if abs(diff) <= _tol(lhs, rhs) else "FAIL"
        results.append(CheckResult(**meta, status=status, lhs=lhs, rhs=rhs, diff=diff))
    return results


def validate_balancesheet(df: pd.DataFrame) -> list[CheckResult]:
    out: list[CheckResult] = []
    out += _check_identity(
        df, "V1_bs_identity",
        ["total_assets"], ["total_liab", "total_hldr_eqy_inc_min_int"],
        note="Assets = Liabilities + Total equity (incl. minority)",
    )
    out += _check_identity(
        df, "V2_equity_composition",
        ["total_hldr_eqy_inc_min_int"],
        ["total_hldr_eqy_exc_min_int", "minority_int"],
        note="Total equity = parent equity + minority interests",
    )
    return out


def validate_cashflow(df: pd.DataFrame) -> list[CheckResult]:
    out: list[CheckResult] = []
    out += _check_identity(
        df, "V3_cf_identity",
        ["n_incr_cash_cash_equ"],
        ["n_cashflow_act", "n_cashflow_inv_act", "n_cash_flows_fnc_act", "eff_fx_flu_cash"],
        note="Net cash increase = CFO + CFI + CFF + FX effect",
    )
    out += _check_identity(
        df, "V4_cash_rollforward",
        ["c_cash_equ_end_period"],
        ["c_cash_equ_beg_period", "n_incr_cash_cash_equ"],
        note="End cash = beginning cash + net increase",
    )
    return out


def validate_income(df: pd.DataFrame) -> list[CheckResult]:
    d = df.copy()
    if "income_tax" in d.columns:
        d["_neg_tax"] = -d["income_tax"]
    # If income_tax is absent, rows SKIP (missing data flagged, not imputed).
    return _check_identity(
        d, "V6_net_income",
        ["n_income"], ["total_profit", "_neg_tax"],
        note="Net income = total profit - income tax expense",
    )


def coverage_report(df: pd.DataFrame, statement: str) -> pd.DataFrame:
    """V5: per (ts_code, year) which period-ends are present (consolidated,
    report_type == '1'). The annual report (1231) missing for a completed
    fiscal year is a FAIL; partial quarterly coverage is informational.
    """
    if df.empty:
        return pd.DataFrame(
            columns=["statement", "ts_code", "year", "periods_present", "status"]
        )
    cons = df[df.get("report_type", pd.Series(dtype=str)).astype(str) == "1"]
    rows = []
    for (code, year), g in cons.groupby(
        [cons["ts_code"], cons["end_date"].astype(str).str[:4]]
    ):
        periods = sorted(set(g["end_date"].astype(str).str[4:]))
        latest_complete_year = pd.Timestamp.now().year - 1
        has_annual = "1231" in periods
        status = "PASS" if has_annual or int(year) > latest_complete_year else "FAIL"
        rows.append((statement, code, year, ",".join(periods), status))
    return pd.DataFrame(
        rows, columns=["statement", "ts_code", "year", "periods_present", "status"]
    )


def results_to_frame(results: list[CheckResult]) -> pd.DataFrame:
    return pd.DataFrame([r.__dict__ for r in results])


def validate_all(
    bs: pd.DataFrame, inc: pd.DataFrame, cf: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run all row-level checks plus coverage. Returns (checks, coverage)."""
    results = validate_balancesheet(bs) + validate_income(inc) + validate_cashflow(cf)
    checks = results_to_frame(results)
    coverage = pd.concat(
        [
            coverage_report(bs, "balancesheet"),
            coverage_report(inc, "income"),
            coverage_report(cf, "cashflow"),
        ],
        ignore_index=True,
    )
    return checks, coverage
