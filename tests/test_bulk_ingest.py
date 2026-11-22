"""Offline tests for all-A-share ingestion (Module 15): coverage planning,
resume / incremental windows, pagination, typed columns, bulk validation."""
import threading
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from pipeline.bulk_ingest import (
    covered_until,
    fetch_paged,
    ingest_all,
    plan_statement_tasks,
    year_end_trade_dates,
)
from pipeline.bulk_validate import latest_completed_fy, validate_store
from pipeline.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "bulk.duckdb")
    yield s
    s.close()


def bs(code, end_date, ann_date, total_assets=100.0, **over):
    row = dict(ts_code=code, ann_date=ann_date, f_ann_date=ann_date,
               end_date=end_date, report_type="1", comp_type="1",
               end_type="4", update_flag="0", total_assets=total_assets,
               total_liab=40.0, total_hldr_eqy_inc_min_int=60.0,
               total_hldr_eqy_exc_min_int=55.0, minority_int=5.0,
               goodwill=None)
    row.update(over)
    return row


class FakeClient:
    """Answers like the gateway: statements filtered by ann_date window,
    bulk calls paginated by limit/offset."""

    def __init__(self, statements, universe, daily=None, cal=None,
                 fail_codes=()):
        self.settings = SimpleNamespace(http_url="https://gw.test")
        self.statements = statements      # api -> DataFrame
        self.universe = universe
        self.daily = daily if daily is not None else pd.DataFrame()
        self.cal = cal if cal is not None else pd.DataFrame(columns=["cal_date"])
        self.fail_codes = set(fail_codes)
        self.calls = []
        self._lock = threading.Lock()

    def query(self, api, **p):
        with self._lock:
            self.calls.append((api, p))
        if api == "stock_basic":
            return self.universe[self.universe.list_status == p["list_status"]]
        if api == "trade_cal":
            return self.cal
        if api == "daily_basic":
            df = self.daily[self.daily.trade_date == p["trade_date"]]
            return df.iloc[p["offset"]:p["offset"] + p["limit"]].reset_index(drop=True)
        if p["ts_code"] in self.fail_codes:
            raise RuntimeError("Tushare API failed after retries: boom")
        df = self.statements.get(api, pd.DataFrame())
        if df.empty:
            return df
        m = ((df.ts_code == p["ts_code"]) & (df.ann_date >= p["start_date"])
             & (df.ann_date <= p["end_date"]))
        return df[m].reset_index(drop=True)


def universe(*codes, status="L"):
    return pd.DataFrame([dict(ts_code=c, name=c, market="主板",
                              list_status=status, list_date="20100101",
                              delist_date=None) for c in codes])


def test_covered_until_merges_contiguous_windows():
    assert covered_until([], "20150101") is None
    assert covered_until([("20150101", "20261119")], "20150101") == "20261119"
    # incremental window overlapping the full one extends coverage
    w = [("20150101", "20261119"), ("20251119", "20261201")]
    assert covered_until(w, "20150101") == "20261201"
    # a window starting after the requested start never covers it
    assert covered_until([("20200101", "20261119")], "20150101") is None
    # disjoint later window does not extend coverage
    w = [("20150101", "20200101"), ("20220101", "20261119")]
    assert covered_until(w, "20150101") == "20200101"


def test_plan_skips_covered_and_narrows_incremental_windows():
    log = pd.DataFrame([
        dict(ts_code="A", api="income", report_type="1",
             start_date="20150101", end_date="20261120", error=None),
        dict(ts_code="A", api="balancesheet", report_type="1",
             start_date="20150101", end_date="20260101", error=None),
        dict(ts_code="A", api="cashflow", report_type="1",
             start_date="20150101", end_date="20261120", error="boom"),
    ])
    tasks, skipped = plan_statement_tasks(["A"], log, "20150101", "20261120",
                                          lookback_days=365)
    assert skipped == 1                       # income already covered
    by_api = {t.api: t for t in tasks}
    assert set(by_api) == {"balancesheet", "cashflow"}
    assert by_api["balancesheet"].start_date == "20250101"   # 20260101 − 365d
    assert by_api["cashflow"].start_date == "20150101"       # failed → full
    assert by_api["balancesheet"].params["start_date"] == "20250101"
    assert "fields" in by_api["balancesheet"].params          # Module 1 fields
    forced, skipped = plan_statement_tasks(["A"], log, "20150101", "20261120",
                                           force=True)
    assert len(forced) == 3 and skipped == 0


def test_fetch_paged_reads_every_page():
    daily = pd.DataFrame([dict(ts_code=f"{i:06d}.SZ", trade_date="20241231",
                               close=1.0) for i in range(7)])
    c = FakeClient({}, universe(), daily=daily)
    df, pages = fetch_paged(c, "daily_basic", page_size=3,
                            trade_date="20241231")
    assert len(df) == 7 and pages == 3
    assert df.ts_code.is_unique


def test_year_end_dates_exclude_unfinished_year():
    cal = pd.DataFrame({"cal_date": ["20231228", "20231229", "20240102",
                                     "20241230", "20241231", "20251230"]})
    c = FakeClient({}, universe(), cal=cal)
    assert year_end_trade_dates(c, 2023, "20251120") == {
        2023: "20231229", 2024: "20241231"}


def test_ingest_all_resumes_and_is_idempotent(store):
    stmts = {"balancesheet": pd.DataFrame([
        bs("A", "20231231", "20240330"), bs("A", "20241231", "20250330"),
        bs("B", "20241231", "20250401", comp_type="2", goodwill=7.6e9)])}
    c = FakeClient(stmts, universe("A", "B"), fail_codes={"B"})
    r1 = ingest_all(c, store, "20150101", "20261120", market=False)
    assert r1["planned"] == 6
    assert r1["statements"]["errors"] == 3            # B failed on all three
    assert r1["statements"]["inserted"] == 2
    # resume: A fully covered, only B's failed requests are replanned
    c.fail_codes = set()
    n_calls = len(c.calls)
    r2 = ingest_all(c, store, "20150101", "20261120", market=False)
    assert r2["skipped"] == 3 and r2["planned"] == 3
    stmt_calls = [a for a, p in c.calls[n_calls:] if a != "stock_basic"]
    assert len(stmt_calls) == 3
    raw = store.load_raw("balancesheet")
    assert len(raw) == 3
    # a value in a column that was all-null in the first rows stored
    assert raw.set_index("ts_code").loc["B", "goodwill"] == 7.6e9
    # full refetch inserts nothing new
    r3 = ingest_all(c, store, "20150101", "20261120", market=False, force=True)
    assert r3["statements"]["inserted"] == 0
    assert store.con.execute(
        "SELECT count(*) FROM raw_stock_basic").fetchall()[0][0] == 2


def test_universe_revision_kept_as_new_row(store):
    c = FakeClient({}, universe("A"))
    ingest_all(c, store, "20150101", "20261120", market=False)
    c.universe = c.universe.assign(name="A 新名")
    ingest_all(c, store, "20150101", "20261120", market=False)
    rows = store.load_raw("stock_basic", "A")
    assert sorted(rows.name) == ["A", "A 新名"]


def test_year_end_market_skip_and_zero_rows_retry(store):
    daily = pd.DataFrame([dict(ts_code="A", trade_date="20241231",
                               close=10.0, total_share=100.0,
                               total_mv=1000.0)])
    cal = pd.DataFrame({"cal_date": ["20231229", "20241231"]})
    c = FakeClient({}, universe("A"), daily=daily, cal=cal)
    r = ingest_all(c, store, "20240101", "20261120")
    assert r["market"][2024]["fetched"] == 1 and r["market"][2024]["error"] is None
    assert r["market"][2023]["error"] == "no rows returned"   # retried later
    r = ingest_all(c, store, "20240101", "20261120")
    assert r["market"][2024].get("skipped") is True
    assert r["market"][2023].get("skipped") is None


def test_validate_store_reports_coverage_and_failures(store):
    stmts = {"balancesheet": pd.DataFrame([
        bs("A", "20251231", "20260330"),
        bs("B", "20241231", "20250401", total_assets=6100.0)])}  # V1 FAIL
    # (diff ¥6,000 exceeds V1's ¥1,000 absolute tolerance)
    c = FakeClient(stmts, universe("A", "B"))
    ingest_all(c, store, "20150101", "20261120", market=False)
    # income / cashflow tables never created: reported as zero rows
    r = validate_store(store, as_of="20261120")
    assert r["fy"] == 2025
    cov = r["coverage"].set_index("ts_code")
    assert bool(cov.loc["A", "bs_has_fy2025"]) is True
    assert bool(cov.loc["B", "bs_has_fy2025"]) is False
    assert cov.loc["A", "is_rows"] == 0
    fails = r["identity_failures"]
    assert list(fails.check) == ["V1_bs_identity"]
    assert fails.ts_code.iloc[0] == "B"
    assert fails["diff"].iloc[0] == pytest.approx(6000.0)
    assert fails.comp_type.iloc[0] == "1"


def test_latest_completed_fy_respects_april_deadline():
    assert latest_completed_fy("20260430") == 2024
    assert latest_completed_fy("20260501") == 2025


def test_store_types_columns_explicitly_and_repairs_null_columns(store):
    # an older store typed an all-null first column as DuckDB "NULL"
    store.con.execute('CREATE TABLE raw_balancesheet (ts_code VARCHAR, '
                      'goodwill "NULL", oth_eq_invest VARCHAR, '
                      '_row_hash VARCHAR, _fetched_at VARCHAR, '
                      '_source_url VARCHAR, _api_params VARCHAR)')
    df = pd.DataFrame([dict(ts_code="B", goodwill=1.5e9, oth_eq_invest=2.0)])
    assert store.insert_raw("balancesheet", df, "u", {}) == 1
    types = dict(store.con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'raw_balancesheet'").fetchall())
    assert types["goodwill"] == "DOUBLE" and types["oth_eq_invest"] == "DOUBLE"
    out = store.load_raw("balancesheet")
    assert out.goodwill.iloc[0] == 1.5e9 and out.oth_eq_invest.iloc[0] == 2.0


def test_new_table_types_all_null_numeric_as_double(store):
    df = pd.DataFrame([dict(ts_code="A", end_date="20241231",
                            update_flag="0", goodwill=None,
                            total_assets=np.nan)])
    store.insert_raw("balancesheet", df, "u", {})
    types = dict(store.con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'raw_balancesheet'").fetchall())
    assert types["goodwill"] == "DOUBLE" and types["update_flag"] == "VARCHAR"


def test_duplicate_rows_within_one_response_insert_once(store):
    row = bs("A", "20241231", "20250330")
    assert store.insert_raw("balancesheet", pd.DataFrame([row, row]), "u", {}) == 1
