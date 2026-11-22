"""Module 15 — Incremental ingestion of raw data for all A-share companies.

Three raw datasets, stored verbatim with the Module 1 provenance columns and
content-hash idempotency:

1. Universe: `stock_basic` (default list_status L = currently listed;
   `--list-status L,D` adds delisted companies) → raw_stock_basic.
2. Statements: per-company `balancesheet` / `income` / `cashflow`,
   report_type 1 (the gateway serves only consolidated). Params are built by
   `ingest.statement_params`, the same as Module 1, so re-fetched 600519.SH
   rows dedupe exactly.
3. Year-end market: `daily_basic` for every stock on the last SSE trading
   day of each December (one paginated call per year) → raw_daily_basic,
   which Module 12's market_snapshot_annual already reads.

Why per company rather than the bulk `*_vip` endpoints (probed 2026-11-20):
balancesheet_vip omitted ~590 listed companies in every period checked
(000002.SZ among them) although the per-company call returns them;
unpaginated cashflow_vip was cut at 6,400 rows (8,695 when paginated); and
the *_vip endpoints ignore ts_code. Per company costs ~16.7k calls, roughly
70 minutes at 4 workers / 240 calls per minute, but each response is complete.

Incremental and resumable: every request outcome is appended to
`ingest_log`. start_date/end_date filter on ann_date (verified on the
gateway). A key (ts_code, api, report_type) whose successful windows already
cover [start, end] is skipped. A key covered only up to an earlier date is
re-fetched from (covered end − lookback_days), so late vendor loads and
restatements near that edge are picked up; the overlap is free because of
hash dedupe. Failed requests leave their window uncovered and are retried on
the next run.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from .ingest import STATEMENTS, statement_params
from .market import DAILY_BASIC_FIELDS
from .store import Store

log = logging.getLogger(__name__)

STOCK_BASIC_FIELDS = ("ts_code,symbol,name,area,industry,fullname,enname,"
                      "cnspell,market,exchange,curr_type,list_status,"
                      "list_date,delist_date,is_hs,act_name,act_ent_type")
PAGE_SIZE = 3000
DEFAULT_LOOKBACK_DAYS = 365


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fetch_paged(client, api: str, page_size: int = PAGE_SIZE,
                **params) -> tuple[pd.DataFrame, int]:
    """All rows of a multi-company call, page by page. Returns (rows, pages).
    Unpaginated bulk calls can be truncated silently by the gateway."""
    parts, offset = [], 0
    while True:
        page = client.query(api, limit=page_size, offset=offset, **params)
        parts.append(page)
        if len(page) < page_size:
            break
        offset += page_size
    frames = [p for p in parts if not p.empty]
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return df, len(parts)


# --- universe --------------------------------------------------------------

def ingest_universe(client, store: Store, run_id: str,
                    list_statuses: tuple[str, ...] = ("L",)) -> pd.DataFrame:
    """Fetch and store stock_basic per list_status; return the combined rows."""
    frames = []
    for status in list_statuses:
        params = dict(list_status=status, fields=STOCK_BASIC_FIELDS)
        df = client.query("stock_basic", **params)
        inserted = store.insert_raw("stock_basic", df,
                                    client.settings.http_url, params)
        store.log_request([dict(run_id=run_id, api="stock_basic",
                                list_status=status, fetched=len(df),
                                inserted=inserted, logged_at=_now())])
        log.info("stock_basic list_status=%s: %d companies, %d new rows",
                 status, len(df), inserted)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


# --- statements --------------------------------------------------------------

@dataclass(frozen=True)
class Task:
    ts_code: str
    api: str
    report_type: str
    start_date: str
    end_date: str
    params: dict = field(hash=False, compare=False)


def covered_until(windows: list[tuple[str, str]], start: str) -> str | None:
    """End of the contiguous ann_date coverage that begins on or before
    `start`, from successful (start_date, end_date) windows; None if no
    successful window reaches back to `start`. Dates are YYYYMMDD strings."""
    end = None
    for s, e in sorted(windows):
        if end is not None and s <= end:
            end = max(end, e)
        elif s <= start:
            end = e
        else:
            break
    return end if end is not None and end >= start else None


def _minus_days(yyyymmdd: str, days: int) -> str:
    d = datetime.strptime(yyyymmdd, "%Y%m%d").date() - timedelta(days=days)
    return d.strftime("%Y%m%d")


def plan_statement_tasks(
    codes: list[str],
    ingest_log: pd.DataFrame,
    start: str,
    end: str,
    report_types: tuple[str, ...] = ("1",),
    statements: tuple[str, ...] = STATEMENTS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    force: bool = False,
) -> tuple[list[Task], int]:
    """Requests still needed to cover [start, end] per key. Returns
    (tasks, n_skipped_up_to_date)."""
    windows: dict[tuple, list] = {}
    if not force and not ingest_log.empty:
        ok = ingest_log[ingest_log.error.isna()
                        & ingest_log.api.isin(statements)
                        & ingest_log.start_date.notna()]
        for r in ok.itertuples():
            windows.setdefault((r.ts_code, r.api, r.report_type), []).append(
                (r.start_date, r.end_date))
    tasks, skipped = [], 0
    for code in codes:
        for stmt in statements:
            for rt in report_types:
                covered = covered_until(windows.get((code, stmt, rt), []), start)
                if covered is not None and covered >= end:
                    skipped += 1
                    continue
                s = start if covered is None else max(
                    start, _minus_days(covered, lookback_days))
                tasks.append(Task(code, stmt, rt, s, end,
                                  statement_params(stmt, code, s, end, rt)))
    return tasks, skipped


def _fetch(client, task: Task):
    try:
        return task, client.query(task.api, **task.params), None
    except RuntimeError as e:  # raised by the client after its retries
        return task, None, str(e)


def ingest_statements(client, store: Store, tasks: list[Task], run_id: str,
                      workers: int = 4, progress_every: int = 250) -> dict:
    """Fetch in worker threads; insert and log on this thread only (DuckDB
    has a single writer). Each outcome is logged as it lands, so an
    interruption loses nothing already stored."""
    totals = dict(requests=len(tasks), done=0, fetched=0, inserted=0,
                  errors=0, empty=0)
    errors: list[tuple] = []
    t0 = time.time()
    ex = ThreadPoolExecutor(max_workers=workers)
    futures = [ex.submit(_fetch, client, t) for t in tasks]
    try:
        for fut in as_completed(futures):
            task, df, err = fut.result()
            fetched = inserted = 0
            if err is None:
                fetched = len(df)
                try:
                    inserted = store.insert_raw(task.api, df,
                                                client.settings.http_url,
                                                task.params)
                except Exception as e:  # keep the run going; reported below
                    err = f"store: {e}"
            store.log_request([dict(
                run_id=run_id, ts_code=task.ts_code, api=task.api,
                report_type=task.report_type, start_date=task.start_date,
                end_date=task.end_date, fetched=fetched, inserted=inserted,
                error=err, logged_at=_now())])
            totals["done"] += 1
            totals["fetched"] += fetched
            totals["inserted"] += inserted
            if err is not None:
                totals["errors"] += 1
                errors.append((task.ts_code, task.api, err))
            elif fetched == 0:
                totals["empty"] += 1
            n = totals["done"]
            if n % progress_every == 0 or n == len(tasks):
                el = time.time() - t0
                eta = el / n * (len(tasks) - n)
                log.info("statements %d/%d  rows fetched %d, new %d, errors %d"
                         "  elapsed %.0fs, ETA %.0fs", n, len(tasks),
                         totals["fetched"], totals["inserted"],
                         totals["errors"], el, eta)
    except KeyboardInterrupt:
        log.warning("Interrupted; outcomes so far are logged — rerun to resume.")
        raise
    finally:
        ex.shutdown(wait=True, cancel_futures=True)
    totals["error_list"] = errors
    return totals


# --- year-end market -------------------------------------------------------

def year_end_trade_dates(client, first_year: int, today: str) -> dict[int, str]:
    """Last SSE trading day of each December from first_year whose date has
    passed (a year still in progress has no year-end snapshot yet)."""
    cal = client.query("trade_cal", exchange="SSE",
                       start_date=f"{first_year}1201",
                       end_date=f"{today[:4]}1231", is_open="1")
    dec = cal[(cal.cal_date.str[4:6] == "12") & (cal.cal_date <= today)]
    last = dec.groupby(dec.cal_date.str[:4]).cal_date.max()
    return {int(y): d for y, d in last.items()}


def ingest_year_end_market(client, store: Store, run_id: str,
                           trade_dates: dict[int, str],
                           ingest_log: pd.DataFrame,
                           force: bool = False) -> dict:
    done = set()
    if not force and not ingest_log.empty:
        ok = ingest_log[(ingest_log.api == "daily_basic")
                        & ingest_log.error.isna()]
        done = set(ok.trade_date.dropna())
    results = {}
    for year, d in sorted(trade_dates.items()):
        if d in done:
            results[year] = dict(trade_date=d, skipped=True)
            continue
        params = dict(trade_date=d, fields=DAILY_BASIC_FIELDS)
        err, fetched, inserted, pages = None, 0, 0, 0
        try:
            df, pages = fetch_paged(client, "daily_basic", **params)
            fetched = len(df)
            inserted = store.insert_raw(
                "daily_basic", df, client.settings.http_url,
                {**params, "limit": PAGE_SIZE, "pages": pages})
            if fetched == 0:  # never legitimate for a trading day: retry later
                err = "no rows returned"
        except RuntimeError as e:
            err = str(e)
        store.log_request([dict(run_id=run_id, api="daily_basic",
                                trade_date=d, fetched=fetched,
                                inserted=inserted, error=err,
                                logged_at=_now())])
        results[year] = dict(trade_date=d, fetched=fetched, inserted=inserted,
                             pages=pages, error=err)
        log.info("daily_basic %s: %d rows (%d pages), %d new%s", d, fetched,
                 pages, inserted, f"  ERROR {err}" if err else "")
    return results


# --- orchestration -----------------------------------------------------------

def ingest_all(client, store: Store, start: str, end: str,
               list_statuses: tuple[str, ...] = ("L",),
               report_types: tuple[str, ...] = ("1",),
               lookback_days: int = DEFAULT_LOOKBACK_DAYS,
               workers: int = 4, codes: list[str] | None = None,
               limit: int | None = None, market: bool = True,
               market_first_year: int | None = None,
               force: bool = False) -> dict:
    run_id = new_run_id()
    universe = ingest_universe(client, store, run_id, list_statuses)
    all_codes = sorted(universe.ts_code.unique())
    if codes:
        unknown = sorted(set(codes) - set(all_codes))
        if unknown:
            log.warning("Not in the fetched universe (fetched anyway): %s",
                        ", ".join(unknown))
        all_codes = sorted(set(codes))
    if limit:
        all_codes = all_codes[:limit]
    ilog = store.load_ingest_log()
    tasks, skipped = plan_statement_tasks(all_codes, ilog, start, end,
                                          report_types,
                                          lookback_days=lookback_days,
                                          force=force)
    incremental = sum(t.start_date != start for t in tasks)
    log.info("run %s: %d companies, %d requests planned (%d incremental), "
             "%d up to date", run_id, len(all_codes), len(tasks),
             incremental, skipped)
    stmt = ingest_statements(client, store, tasks, run_id, workers=workers)
    mkt = {}
    if market:
        first = market_first_year or int(start[:4]) - 1
        dates = year_end_trade_dates(client, first, date.today().strftime("%Y%m%d"))
        mkt = ingest_year_end_market(client, store, run_id, dates,
                                     store.load_ingest_log(), force=force)
    return dict(run_id=run_id, universe=len(universe),
                companies=len(all_codes), planned=len(tasks),
                incremental=incremental, skipped=skipped,
                statements=stmt, market=mkt)
