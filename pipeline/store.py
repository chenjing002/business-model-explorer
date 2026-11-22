"""DuckDB storage layer for raw Tushare financial statements.

Design rules:
- Raw API rows are stored verbatim (all columns, original names/values).
- Every row carries provenance: fetch timestamp, source gateway, API params.
- Idempotent ingestion: a row is identified by the hash of its raw content,
  so re-fetching identical data inserts nothing, while revisions
  (changed values, new update_flag / f_ann_date) are kept as new rows.
- Nothing is ever updated or silently reconciled; history accumulates.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

RAW_TABLES = {
    "balancesheet": "raw_balancesheet",
    "income": "raw_income",
    "cashflow": "raw_cashflow",
}
# Market data (Module 12): same raw/provenance rules, keyed by trade_date.
MARKET_TABLES = {
    "daily_basic": "raw_daily_basic",
}
# Reference data (Module 15): the A-share universe. A renamed or delisted
# company shows up as a new row; earlier snapshots are kept.
REFERENCE_TABLES = {
    "stock_basic": "raw_stock_basic",
}
ALL_RAW_TABLES = {**RAW_TABLES, **MARKET_TABLES, **REFERENCE_TABLES}

META_COLS = ["_row_hash", "_fetched_at", "_source_url", "_api_params"]

# Identifier, date and flag fields Tushare returns as text. Every other
# statement / market field is a number, even when one company's response has
# it all null — typing columns from the first frame stored left 141 columns
# as DuckDB "NULL" (e.g. goodwill, lt_borr), which rejects any later value.
TEXT_COLS = {
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type",
    "comp_type", "end_type", "update_flag", "trade_date", *META_COLS,
}
NULL_TYPE = '"NULL"'


def _column_type(table: str, col: str, values: pd.Series | None = None) -> str:
    if table in REFERENCE_TABLES.values() or col in TEXT_COLS:
        return "VARCHAR"
    if (values is not None and values.notna().any()
            and not pd.api.types.is_numeric_dtype(values)):
        return "VARCHAR"  # unexpected text field: keep it as text, never coerce
    return "DOUBLE"

# One row per API request made by bulk ingestion (Module 15). Successful
# rows define which ann_date windows are already covered, so an interrupted
# or repeated run resumes instead of starting over.
INGEST_LOG_DDL = """
CREATE TABLE IF NOT EXISTS ingest_log (
    run_id VARCHAR, ts_code VARCHAR, api VARCHAR, report_type VARCHAR,
    start_date VARCHAR, end_date VARCHAR, trade_date VARCHAR,
    list_status VARCHAR, fetched INTEGER, inserted INTEGER, error VARCHAR,
    logged_at VARCHAR
)"""


def _row_hash(row: pd.Series, cols: list[str]) -> str:
    payload = json.dumps(
        {c: (None if pd.isna(row[c]) else row[c]) for c in cols},
        sort_keys=True, default=str, ensure_ascii=False,
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


class Store:
    def __init__(self, db_path: Path | str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(db_path))
        self._repaired: set[str] = set()

    def close(self) -> None:
        self.con.close()

    def _repair_types(self, table: str, existing: dict[str, str]) -> None:
        """Retype columns an older store inferred wrongly from an all-null
        first frame: "NULL" columns, and all-null VARCHAR columns that should
        be numbers (DuckDB would otherwise store later numbers as text).
        Only all-null columns are touched, so the cast cannot lose values."""
        for col, dtype in existing.items():
            target = _column_type(table, col)
            if dtype == target:
                continue
            if dtype != NULL_TYPE:
                n = self.con.execute(
                    f'SELECT count("{col}") FROM {table}').fetchall()[0][0]
                if n:
                    continue  # holds text values: leave as stored
            self.con.execute(
                f'ALTER TABLE {table} ALTER "{col}" TYPE {target}')

    def _ensure_table(self, table: str, df: pd.DataFrame) -> None:
        exists = self.con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
            [table],
        ).fetchall()[0][0]
        if not exists:
            cols = ", ".join(f'"{c}" {_column_type(table, c, df[c])}'
                             for c in df.columns)
            self.con.execute(f"CREATE TABLE {table} ({cols})")
            return
        # Schema evolution: add any new columns (never drop existing ones).
        existing = dict(self.con.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = ?",
            [table],
        ).fetchall())
        if table not in self._repaired:
            self._repair_types(table, existing)
            self._repaired.add(table)
        for col in df.columns:
            if col not in existing:
                self.con.execute(f'ALTER TABLE {table} ADD COLUMN "{col}" '
                                 f'{_column_type(table, col, df[col])}')

    def insert_raw(
        self,
        statement: str,
        df: pd.DataFrame,
        source_url: str,
        api_params: dict,
    ) -> int:
        """Insert raw rows, skipping rows whose content hash already exists.

        Returns the number of newly inserted rows.
        """
        if df.empty:
            return 0
        table = ALL_RAW_TABLES[statement]
        raw_cols = [c for c in df.columns if c not in META_COLS]
        df = df.copy()
        df["_row_hash"] = df.apply(lambda r: _row_hash(r, raw_cols), axis=1)
        # An exact duplicate inside one response carries no information.
        df = df.drop_duplicates("_row_hash")
        df["_fetched_at"] = datetime.now(timezone.utc).isoformat()
        df["_source_url"] = source_url
        df["_api_params"] = json.dumps(api_params, ensure_ascii=False, sort_keys=True)

        self._ensure_table(table, df)
        # Anti-join in DuckDB: with every A-share stored, pulling all hashes
        # into Python on each insert would dominate the run time.
        self.con.register("_ins_df", df)
        cols = ", ".join(f'"{c}"' for c in df.columns)
        inserted = self.con.execute(
            f"INSERT INTO {table} ({cols}) SELECT {cols} FROM _ins_df "
            f"WHERE _row_hash NOT IN (SELECT _row_hash FROM {table})"
        ).fetchall()[0][0]
        self.con.unregister("_ins_df")
        return int(inserted)

    def log_request(self, rows: list[dict]) -> None:
        """Append request outcomes to ingest_log (keys as in INGEST_LOG_DDL)."""
        if not rows:
            return
        self.con.execute(INGEST_LOG_DDL)
        cols = ["run_id", "ts_code", "api", "report_type", "start_date",
                "end_date", "trade_date", "list_status", "fetched",
                "inserted", "error", "logged_at"]
        self.con.executemany(
            f"INSERT INTO ingest_log ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})",
            [[r.get(c) for c in cols] for r in rows],
        )

    def load_ingest_log(self) -> pd.DataFrame:
        self.con.execute(INGEST_LOG_DDL)
        return self.con.execute("SELECT * FROM ingest_log").df()

    def load_raw(self, statement: str, ts_code: str | None = None) -> pd.DataFrame:
        table = ALL_RAW_TABLES[statement]
        q = f"SELECT * FROM {table}"
        params: list = []
        if ts_code:
            q += " WHERE ts_code = ?"
            params.append(ts_code)
        return self.con.execute(q, params).df()

    def summary(self) -> pd.DataFrame:
        rows = []
        for stmt, table in RAW_TABLES.items():
            exists = self.con.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
                [table],
            ).fetchall()[0][0]
            if not exists:
                rows.append((stmt, 0, None, None))
                continue
            n, dmin, dmax = self.con.execute(
                f"SELECT count(*), min(end_date), max(end_date) FROM {table}"
            ).fetchall()[0]
            rows.append((stmt, n, dmin, dmax))
        return pd.DataFrame(rows, columns=["statement", "rows", "min_end_date", "max_end_date"])
