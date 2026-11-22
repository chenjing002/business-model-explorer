"""Module 15 — Offline validation of the all-A-share raw store.

Reported, never corrected:
- Coverage per listed company: rows per statement, latest end_date, and
  whether the latest completed fiscal year's annual report (end_date 1231)
  is present for companies listed by that year end.
- Module 1 identity checks (V1–V4, V6 from validate.py, unchanged) run over
  every stored row in chunks; PASS / FAIL / SKIP counted by check and
  comp_type (1 industrial, 2 bank, 3 insurance, 4 securities), FAIL rows kept.
- Year-end market coverage: listed companies present in each bulk
  daily_basic trade date (absent = suspended that day or listed later).
- Request errors left in ingest_log by the latest run.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from .store import Store
from .validate import (
    results_to_frame,
    validate_balancesheet,
    validate_cashflow,
    validate_income,
)

CHECK_COLUMNS = {
    "balancesheet": ["total_assets", "total_liab", "total_hldr_eqy_inc_min_int",
                     "total_hldr_eqy_exc_min_int", "minority_int"],
    "income": ["n_income", "total_profit", "income_tax"],
    "cashflow": ["n_incr_cash_cash_equ", "n_cashflow_act",
                 "n_cashflow_inv_act", "n_cash_flows_fnc_act",
                 "eff_fx_flu_cash", "c_cash_equ_end_period",
                 "c_cash_equ_beg_period"],
}
VALIDATORS = {
    "balancesheet": validate_balancesheet,
    "income": validate_income,
    "cashflow": validate_cashflow,
}
STMT_ABBR = {"balancesheet": "bs", "income": "is", "cashflow": "cf"}


def _exists(store: Store, table: str) -> bool:
    return store.con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
        [table]).fetchall()[0][0] > 0


def latest_completed_fy(as_of: str) -> int:
    """Annual reports are due by 30 April of the following year."""
    y = int(as_of[:4])
    return y - 1 if as_of[4:] > "0430" else y - 2


def latest_universe(store: Store) -> pd.DataFrame:
    """Latest stored stock_basic row per company."""
    return store.con.execute("""
        SELECT * FROM raw_stock_basic
        QUALIFY row_number() OVER (PARTITION BY ts_code
                                   ORDER BY _fetched_at DESC) = 1
    """).df()


def statement_coverage(store: Store, universe: pd.DataFrame,
                       as_of: str) -> pd.DataFrame:
    fy = latest_completed_fy(as_of)
    out = universe[["ts_code", "name", "market", "list_status",
                    "list_date"]].copy()
    for stmt, abbr in STMT_ABBR.items():
        if not _exists(store, f"raw_{stmt}"):
            agg = pd.DataFrame(columns=["ts_code", "n", "latest", "has_fy"])
        else:
            agg = store.con.execute(f"""
                SELECT ts_code, count(*) AS n, max(end_date) AS latest,
                       bool_or(end_date = '{fy}1231') AS has_fy
                FROM raw_{stmt} WHERE report_type = '1' GROUP BY ts_code
            """).df()
        agg = agg.rename(columns={"n": f"{abbr}_rows",
                                  "latest": f"{abbr}_latest_end",
                                  "has_fy": f"{abbr}_has_fy{fy}"})
        out = out.merge(agg, on="ts_code", how="left")
        out[f"{abbr}_rows"] = out[f"{abbr}_rows"].fillna(0).astype(int)
        out[f"{abbr}_has_fy{fy}"] = out[f"{abbr}_has_fy{fy}"].astype(
            "boolean").fillna(False).astype(bool)
    out[f"fy{fy}_expected"] = out.list_date <= f"{fy}1231"
    return out


def identity_checks(store: Store, chunk_rows: int = 50_000
                    ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(summary by check × comp_type × status, FAIL rows)."""
    counts, fails = [], []
    for stmt, cols in CHECK_COLUMNS.items():
        if not _exists(store, f"raw_{stmt}"):
            continue
        df = store.con.execute(
            f"SELECT ts_code, end_date, report_type, comp_type, update_flag, "
            f"f_ann_date, {', '.join(cols)} FROM raw_{stmt}").df()
        for i in range(0, len(df), chunk_rows):
            part = df.iloc[i:i + chunk_rows].reset_index(drop=True)
            res = results_to_frame(VALIDATORS[stmt](part))
            # validators emit one result per row per check, in row order
            n_checks = len(res) // len(part)
            for c in ["comp_type", "update_flag", "f_ann_date"]:
                res[c] = pd.concat([part[c]] * n_checks, ignore_index=True)
            counts.append(res.groupby(["check", "comp_type", "status"])
                          .size().rename("rows").reset_index())
            fails.append(res[res.status == "FAIL"])
    if not counts:
        return (pd.DataFrame(columns=["check", "comp_type", "status", "rows"]),
                pd.DataFrame(columns=["check", "ts_code", "end_date", "status"]))
    summary = (pd.concat(counts).groupby(["check", "comp_type", "status"],
                                         as_index=False).rows.sum())
    return summary, pd.concat(fails, ignore_index=True)


def market_coverage(store: Store, universe: pd.DataFrame,
                    min_codes: int = 1000) -> pd.DataFrame:
    """Per bulk year-end trade date: listed companies with a row there."""
    if not _exists(store, "raw_daily_basic"):
        return pd.DataFrame()
    per_date = store.con.execute("""
        SELECT trade_date, list(DISTINCT ts_code) AS codes
        FROM raw_daily_basic GROUP BY trade_date
        HAVING count(DISTINCT ts_code) >= ?
        ORDER BY trade_date
    """, [min_codes]).fetchall()
    listed = universe[universe.list_status == "L"]
    rows = []
    for d, codes in per_date:
        expected = set(listed[listed.list_date <= d].ts_code)
        present = expected & set(codes)
        rows.append(dict(trade_date=d, rows=len(codes),
                         listed_by_date=len(expected), present=len(present),
                         absent=len(expected - present),
                         absent_sample=",".join(sorted(expected - present)[:10])))
    return pd.DataFrame(rows)


def latest_run_errors(store: Store) -> pd.DataFrame:
    log = store.load_ingest_log()
    if log.empty:
        return log
    latest = log[log.run_id == log.run_id.max()]
    return latest[latest.error.notna()]


def validate_store(store: Store, as_of: str | None = None) -> dict:
    as_of = as_of or date.today().strftime("%Y%m%d")
    universe = latest_universe(store)
    summary, fails = identity_checks(store)
    return dict(
        as_of=as_of, fy=latest_completed_fy(as_of), universe=universe,
        coverage=statement_coverage(store, universe, as_of),
        identity_summary=summary, identity_failures=fails,
        market=market_coverage(store, universe),
        errors=latest_run_errors(store),
    )
