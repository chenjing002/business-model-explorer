"""Module 12 (input) — Year-end market snapshots from Tushare `daily_basic`.

Raw rows are stored verbatim in `raw_daily_basic` (same content-hash
idempotency and provenance as the statements). The derived
`market_snapshot_annual` takes, per fiscal year, the LAST trading day on or
before 31 December and converts Tushare's display units:

    total_mv     万元 (1e4 CNY)   → market_cap (CNY)
    total_share  万股 (1e4 shares) → shares

Check M1 (reported, never forced): market_cap vs close × shares, relative.

Not claimed: the snapshot is the valuation date for the same year's balance
sheet, but those statements were published ~3–4 months LATER. Valuing
year-end book at the year-end price is the textbook convention, not a
point-in-time-tradable signal. Tushare's own pe/pb on that date use the
latest *published* report and are kept only as reference columns.
"""
from __future__ import annotations

import logging
from decimal import Decimal

import numpy as np
import pandas as pd

from .store import Store

log = logging.getLogger(__name__)

DAILY_BASIC_FIELDS = ("ts_code,trade_date,close,total_share,float_share,"
                      "total_mv,circ_mv,pe,pe_ttm,pb,dv_ttm")
WAN = 10_000  # Tushare 万 unit

SNAPSHOT_NOTE = ("Last trading day of the fiscal year; the same year's "
                 "statements were published months later (hindsight anchor). "
                 "pe_reported/pb_reported are Tushare's, based on the latest "
                 "report published at that date — reference only.")


def ingest_market(client, store: Store, ts_code: str,
                  years: list[int]) -> dict:
    """Fetch December daily_basic rows for each fiscal year (small windows
    keep every call well under the gateway's row cap)."""
    results = {}
    for y in years:
        params = dict(ts_code=ts_code, start_date=f"{y}1201",
                      end_date=f"{y}1231", fields=DAILY_BASIC_FIELDS)
        try:
            df = client.query("daily_basic", **params)
        except RuntimeError as e:
            log.warning("daily_basic %s: %s", y, e)
            results[y] = {"fetched": 0, "inserted": 0, "error": str(e)}
            continue
        inserted = store.insert_raw("daily_basic", df,
                                    client.settings.http_url, params)
        results[y] = {"fetched": len(df), "inserted": inserted, "error": None}
    return results


def compute_market_snapshot(raw: pd.DataFrame) -> pd.DataFrame:
    """Raw daily_basic rows → one row per fiscal year (last trading day)."""
    cols = ["ts_code", "end_date", "trade_date", "close", "shares",
            "market_cap", "pe_reported", "pb_reported", "dv_ttm_reported",
            "m1_mcap_residual_rel", "snapshot_note"]
    if raw.empty:
        return pd.DataFrame(columns=cols)
    df = raw.copy()
    # revisions: keep the latest fetch per trading day
    df = (df.sort_values("_fetched_at")
            .drop_duplicates(["ts_code", "trade_date"], keep="last"))
    df["fy"] = df.trade_date.str[:4]
    df = df[df.trade_date.str[4:6] == "12"]
    last = (df.sort_values("trade_date")
              .groupby(["ts_code", "fy"], as_index=False).tail(1))
    rows = []
    for r in last.sort_values("trade_date").itertuples():
        shares = float(Decimal(str(r.total_share)) * WAN) if pd.notna(r.total_share) else np.nan
        mcap = float(Decimal(str(r.total_mv)) * WAN) if pd.notna(r.total_mv) else np.nan
        implied = r.close * shares
        rows.append(dict(
            ts_code=r.ts_code, end_date=f"{r.fy}1231", trade_date=r.trade_date,
            close=r.close, shares=shares, market_cap=mcap,
            pe_reported=r.pe, pb_reported=r.pb,
            dv_ttm_reported=getattr(r, "dv_ttm", np.nan),
            m1_mcap_residual_rel=(mcap - implied) / mcap if mcap > 0 else np.nan,
            snapshot_note=SNAPSHOT_NOTE))
    return pd.DataFrame(rows, columns=cols)


def build_market_snapshot(store: Store, ts_code: str) -> pd.DataFrame:
    exists = store.con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_name='raw_daily_basic'").fetchall()[0][0]
    if not exists:
        raise RuntimeError(f"No market data; run `market {ts_code}` first.")
    raw = store.load_raw("daily_basic", ts_code)
    snap = compute_market_snapshot(raw)
    store.con.register("_df", snap)
    exists = store.con.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_name='market_snapshot_annual'").fetchall()[0][0]
    if exists:
        store.con.execute(
            "DELETE FROM market_snapshot_annual WHERE ts_code = ?", [ts_code])
        store.con.execute(
            "INSERT INTO market_snapshot_annual BY NAME SELECT * FROM _df")
    else:
        store.con.execute(
            "CREATE TABLE market_snapshot_annual AS SELECT * FROM _df")
    store.con.unregister("_df")
    return snap
