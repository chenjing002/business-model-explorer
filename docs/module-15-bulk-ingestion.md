# Module 15 — Incremental ingestion for all A-shares

Fetches and stores the **raw** Tushare data of every listed A-share company
through the purchased gateway, with the Module 1 storage rules unchanged:
verbatim rows, provenance columns, append-only, content-hash idempotency.
No analytical layer (mapping, reformulation, exports) is run for the new
companies here; those remain per-company commands.

## Files

```
pipeline/
  bulk_ingest.py     universe → per-company statements → year-end daily_basic;
                     ingest_log planning (resume / incremental windows)
  bulk_validate.py   offline coverage + identity checks over the whole store
  store.py           + raw_stock_basic, ingest_log, explicit column types,
                     anti-join dedupe
  client.py          throttle is now thread-safe (one global per-minute cap)
  ingest.py          statement_params() shared by single and bulk paths
  fields.py          balancesheet / income field lists = explicit ∪ default
tests/test_bulk_ingest.py   offline (fake gateway), 12 tests
```

## Commands

```bash
.venv/bin/python -m pipeline.cli ingest-all              # all listed (L)
.venv/bin/python -m pipeline.cli ingest-all --list-status L,D   # + delisted
.venv/bin/python -m pipeline.cli ingest-all --codes 000001.SZ,600030.SH
.venv/bin/python -m pipeline.cli ingest-all --limit 50 --no-market  # trial
.venv/bin/python -m pipeline.cli validate-all            # writes data/bulk_*.csv
```

Options: `--start` (ann_date, default 20150101 as in Module 1), `--end`
(default today), `--workers 4`, `--cpm 240` (calls/minute across workers),
`--lookback-days 365`, `--force` (ignore the log, refetch full windows).

## What is stored

| Table | Source call | Notes |
|---|---|---|
| `raw_stock_basic` | `stock_basic(list_status=L)` | universe; a renamed company is a new row |
| `raw_balancesheet` / `raw_income` / `raw_cashflow` | per company, `report_type=1`, ann_date window | same params as Module 1 `ingest` |
| `raw_daily_basic` | `daily_basic(trade_date=<last SSE trading day of December>)`, paginated | every stock that traded that day; Module 12's `market_snapshot_annual` reads it unchanged |
| `ingest_log` | — | one row per request: window, fetched, inserted, error |

Units are as Tushare returns them: statements in 元; `daily_basic`
`total_mv` in 万元 and `total_share` in 万股 (converted only in
`market_snapshot_annual`, never in the raw table).

## Design decisions (from gateway probes, 2026-11-20)

- **Per company, not the bulk `*_vip` endpoints.** `balancesheet_vip`
  omitted ~590 listed companies in every period checked (000002.SZ among
  them) while the per-company call returns them; unpaginated
  `cashflow_vip` was silently cut at 6,400 rows (8,695 paginated); `*_vip`
  ignores `ts_code`. Per company costs ~16.7k calls but each response is
  complete on its own.
- **Throughput.** Sequential ≈ 67 calls/min (latency ≈ 0.9 s); 4 threads
  ≈ 260 calls/min with no errors. Default 4 workers capped at 240/min.
- **Date filter is ann_date.** `start_date/end_date` select rows by
  announcement date (verified on 000001.SZ). Incremental windows rely on it.
- **Bulk market calls are paginated** (`limit=3000` / `offset`) and a
  trading day with zero rows is logged as an error so it is retried.

## Incremental / resume semantics

Per key (ts_code, api, report_type), successful `ingest_log` windows are
merged into the contiguous ann_date coverage that starts on or before
`--start`:

- covered through `--end` → skipped (resume after interruption, same-day rerun);
- covered through an earlier date D → refetch `[D − lookback, end]`
  (late vendor loads, restatements near the edge; overlap costs nothing
  because identical rows hash the same);
- never covered, or only failed attempts → full window.

Year-end `daily_basic` dates already fetched successfully are skipped.

## Store fixes required by the all-company data

1. **Column types.** Tables were created from the first frame stored
   (600519.SH), so 141 columns that were all-null for Moutai (e.g.
   `goodwill`, `lt_borr`, `bond_payable`, every bank/insurer line) were typed
   DuckDB `"NULL"`, which rejects any later value
   (`Conversion Error: Unimplemented type for cast (DOUBLE -> "NULL")`), and
   5 numeric columns were VARCHAR. Now identifier/date/flag fields are
   VARCHAR, every other statement/market field DOUBLE; a wrongly typed
   column is repaired on first use only when it holds no values (lossless;
   verified value-for-value on a copy of the store).
2. **Dedupe in SQL.** `insert_raw` previously loaded every stored hash into
   Python on each insert; it now anti-joins in DuckDB. Exact duplicates
   within one response are inserted once.
3. **Field lists.** Module 1's explicit lists dropped financial-industry
   lines that only the gateway default returns: bank deposits `depos`,
   `cash_reser_cb`, insurance reserves, securities `client_depos`, and
   `deriv_liab` (also reported by industrials, e.g. 000002.SZ). Lists are now
   the union (balancesheet 158, income 93 fields; the gateway returns all in
   one call). Cash flow keeps the default response, which already contains
   the newer lines (`credit_impa_loss`, `use_right_asset_dep`, ...).

Effect on 600519.SH: the wider field set changes the content hash, so one
more copy of its 68 balance sheets and 65 income statements was stored
(cash flow: 0 new). Moutai has no values in the added fields; rebuilding
`std_facts` from the new rows gives the same 8,677 facts, max value
difference 0. `map 600519.SH` now lists `total_opcost` (营业总成本(二), a
subtotal) as populated-but-unmapped — informational; the mapping layer is
unchanged in this module.

## Validation (`validate-all`)

- Coverage per listed company: rows per statement, latest end_date, and the
  latest completed fiscal year's annual report (due 30 April) for companies
  listed by that year end → `bulk_coverage_by_company.csv`.
- Module 1 identities V1–V4, V6 (`validate.py`, unchanged) over every stored
  row, counted by check × comp_type × status → `bulk_validation_summary.csv`;
  FAIL rows → `bulk_validation_failures.csv`. Reported, never corrected.
- Year-end market coverage of listed companies → `bulk_market_coverage.csv`.
- Request errors in the latest run.

## Results — first full run, 2026-11-20 (run 20261121T022442Z)

- Universe: 5,580 listed companies (SZSE 2,905 / SSE 2,319 / BSE 356).
- Statements: 16,725 requests in 72 min (4 workers, 240/min cap),
  **0 errors**, 919,734 new rows; 15 keys already covered by the trial run
  were skipped. Stored totals: balancesheet 309,299 / income 303,745 /
  cashflow 307,946 rows; end_date 2008-12-31 (prospectus periods announced
  after 2015) to 2026-09-30. DuckDB file 343 MB.
- 12 empty responses = 4 companies × 3 statements, all IPOs of
  2026-11-03…17 (688827.SH, 920309.BJ, 920085.BJ, 001381.SZ) with no report
  on the gateway yet. All other 5,576 have rows in every statement.
- **FY2025 annual report present for 5,444 / 5,444** companies listed by
  2025-12-31, in all three statements.
- Identity checks over all stored rows (FAIL rate < 0.03%):

  | Check | PASS | FAIL | SKIP |
  |---|---:|---:|---:|
  | V1 assets = liabilities + equity | 308,722 | 28 | 549 |
  | V2 equity = parent + minority | 233,786 | 10 | 75,503 |
  | V3 Δcash = CFO + CFI + CFF + FX | 230,629 | 39 | 77,278 |
  | V4 end cash = begin + Δcash | 307,459 | 75 | 412 |
  | V6 NI = total profit − tax | 298,477 | 15 | 5,253 |

  167 FAIL rows across 94 companies, spread over 2014–2026, mostly comp_type
  1; they are vendor rows that do not tie (largest: 601628.SH 2023Q3 NI
  ¥17.3B vs total profit − tax ¥−5.4B). Reported in
  `bulk_validation_failures.csv`, never corrected. SKIPs are null source
  fields (e.g. `minority_int` / `eff_fx_flu_cash` not disclosed), never imputed.
- Year-end `daily_basic`: 12 dates (2014-12-31 … 2025-12-31), 2–5k rows
  each; 2025-12-31 covers 5,432 / 5,444 listed companies. Absent companies
  were suspended that day (verified: 000002.SZ last traded 2015-12-18,
  000006.SZ no December 2017 trade); 2014–2017 have 170–230 absent, later
  years 4–45.
- Idempotency on live data: forced full refetch of 000001.SZ + 300750.SZ
  (395 rows) inserted 0; an immediate normal rerun planned 0 requests.
- 600519.SH: 0 new cash-flow rows, one wider-field copy of BS/IS (see above).
- Tests: 125/125 (`pytest tests/ -q`), 12 new in `test_bulk_ingest.py`.

## Known limitations

- Default universe is currently listed companies (`L`); delisted companies
  (`D`, 345 on 2026-11-20) need `--list-status L,D`. Without them any
  cross-sectional history has survivorship bias.
- Beijing Stock Exchange companies were renumbered to 920xxx; the gateway's
  bulk endpoints still carry ~580 old 43xxxx/83xxxx/87xxxx codes for past
  periods. The per-company call under the current code returns the full
  history (920682.BJ: FY2013–2026 Q3, all rows under 920682.BJ).
- Only consolidated statements (report_type 1) — unchanged gateway limit.
- Year-end market rows exist only for stocks that traded on the last
  December trading day. `market_snapshot_annual` for a company suspended
  then needs `market <ts_code>` (Module 12's per-company December window),
  which picks up its last December trade.
- `mapping_tushare.yml` was written for an industrial company; banks,
  insurers and brokers (comp_type 2/3/4) need their own mapping before
  Modules 2–12 can analyse them.
