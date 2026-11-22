"""Ingestion: fetch financial statements for a company and store them raw.

Report types requested (Tushare convention, preserved verbatim):
  '1' consolidated (合并报表)        '6' parent company (母公司报表)
  '4' prior-period adjusted (调整上年) '5' restated (调整前合并报表)
A gateway/permission failure on any report type is logged and skipped —
whatever was successfully fetched is stored with its exact request params.
"""
from __future__ import annotations

import logging

from .client import TushareClient
from .fields import API_FIELDS
from .store import Store

log = logging.getLogger(__name__)

STATEMENTS = ("balancesheet", "income", "cashflow")
DEFAULT_REPORT_TYPES = ("1", "6", "4", "5")


def statement_params(stmt: str, ts_code: str, start_date: str,
                     end_date: str, report_type: str) -> dict:
    """Request params for one statement call. start_date/end_date filter on
    ann_date. Shared with bulk ingestion (Module 15) so a re-fetched row
    hashes identically whichever path fetched it."""
    params = dict(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        report_type=report_type,
    )
    if stmt in API_FIELDS:
        params["fields"] = API_FIELDS[stmt]
    return params


def ingest_company(
    client: TushareClient,
    store: Store,
    ts_code: str,
    start_date: str,
    end_date: str,
    report_types: tuple[str, ...] = DEFAULT_REPORT_TYPES,
) -> dict:
    """Fetch all statements for one company over a date range.

    Returns {(statement, report_type): {"fetched": n, "inserted": m, "error": str|None}}.
    """
    results: dict = {}
    for stmt in STATEMENTS:
        for rt in report_types:
            params = statement_params(stmt, ts_code, start_date, end_date, rt)
            key = (stmt, rt)
            try:
                df = client.query(stmt, **params)
            except RuntimeError as e:
                log.warning("Skipping %s report_type=%s: %s", stmt, rt, e)
                results[key] = {"fetched": 0, "inserted": 0, "error": str(e)}
                continue
            inserted = store.insert_raw(stmt, df, client.settings.http_url, params)
            results[key] = {"fetched": len(df), "inserted": inserted, "error": None}
            log.info("%s rt=%s: fetched %d, inserted %d", stmt, rt, len(df), inserted)
    return results
