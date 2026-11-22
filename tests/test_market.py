"""Offline tests for year-end market snapshots (Module 12 input)."""
import pandas as pd
import pytest

from pipeline.market import compute_market_snapshot
from pipeline.store import Store


def raw_row(trade_date, close, total_share=100.0, fetched="2026-01-01",
            pe=20.0):
    # Tushare units: total_share 万股, total_mv 万元
    return dict(ts_code="T", trade_date=trade_date, close=close,
                total_share=total_share, total_mv=close * total_share,
                pe=pe, pb=5.0, dv_ttm=1.0, _fetched_at=fetched)


def test_last_december_trading_day_and_units():
    raw = pd.DataFrame([raw_row("20231228", 10.0), raw_row("20231229", 11.0),
                        raw_row("20221230", 9.0), raw_row("20221115", 1.0)])
    s = compute_market_snapshot(raw).set_index("end_date")
    assert list(s.index) == ["20221231", "20231231"]
    r = s.loc["20231231"]
    assert r.trade_date == "20231229" and r.close == 11.0
    assert r.shares == pytest.approx(100.0 * 1e4)
    assert r.market_cap == pytest.approx(11.0 * 100.0 * 1e4)
    assert r.m1_mcap_residual_rel == pytest.approx(0.0, abs=1e-12)


def test_latest_fetch_wins_and_m1_surfaces_mismatch():
    bad = raw_row("20231229", 11.0, fetched="2026-02-01")
    bad["total_mv"] = 1200.0  # ≠ 11 × 100
    raw = pd.DataFrame([raw_row("20231229", 11.0), bad])
    s = compute_market_snapshot(raw)
    assert len(s) == 1
    assert s.market_cap.iloc[0] == pytest.approx(1200.0 * 1e4)
    assert s.m1_mcap_residual_rel.iloc[0] == pytest.approx((1200 - 1100) / 1200)


def test_daily_basic_raw_store_idempotent(tmp_path):
    st = Store(tmp_path / "m.duckdb")
    try:
        df = pd.DataFrame([{k: v for k, v in raw_row("20231229", 11.0).items()
                            if k != "_fetched_at"}])
        assert st.insert_raw("daily_basic", df, "u", {"p": 1}) == 1
        assert st.insert_raw("daily_basic", df, "u", {"p": 1}) == 0
        assert len(st.load_raw("daily_basic", "T")) == 1
        # statements summary unaffected by the market table
        assert set(st.summary().statement) == {"balancesheet", "income", "cashflow"}
    finally:
        st.close()
