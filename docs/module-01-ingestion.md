# Module 1 — Tushare Ingestion & Financial Validation

## Architecture

```
.env                      TUSHARE_TOKEN + TUSHARE_HTTP_URL (purchased gateway
                          https://tuaremax.top — overrides official endpoint)
pipeline/
  config.py               Settings from env/.env; rate limit, retry, db path
  client.py               tushare pro_api wrapper: gateway URL override,
                          token-bucket throttle (30 calls/min), retry w/ backoff
  store.py                DuckDB raw store (data/bme.duckdb)
  ingest.py               Fetch balancesheet/income/cashflow per company
  validate.py             Accounting-identity checks
  cli.py                  python -m pipeline.cli {ingest|validate|summary}
tests/                    Offline unit tests (no token needed): 14 passing
```

## Commands

```bash
.venv/bin/python -m pipeline.cli ingest 600519.SH --start 20150101
.venv/bin/python -m pipeline.cli validate 600519.SH   # writes CSVs to data/
.venv/bin/python -m pipeline.cli summary
.venv/bin/python -m pytest tests/ -q
```

## Storage conventions

- Tables `raw_balancesheet`, `raw_income`, `raw_cashflow`: Tushare rows
  verbatim (original column names, values in CNY yuan) plus provenance
  columns `_row_hash`, `_fetched_at`, `_source_url`, `_api_params`.
- Idempotent by content hash: identical re-fetch inserts nothing; revisions
  (changed values / `update_flag` / `f_ann_date`) accumulate as new rows.
  Nothing is updated or deleted; history is append-only.
- Schema evolution: new API columns are added, existing never dropped.
  Column types are explicit (text identifiers VARCHAR, everything else
  DOUBLE); an all-null column typed wrongly by the first frame is retyped
  losslessly (Module 15, docs/module-15-bulk-ingestion.md).
- `report_type`: '1' consolidated, '6' parent, '4'/'5' adjusted/restated —
  requested separately, stored verbatim.
- Income & cash flow values are **cumulative year-to-date** per period.
  Single-quarter figures are a derived layer (Module 2+), never stored raw.
- `update_flag`: '0' original disclosure, '1' revised — both kept.

## Validation (pipeline/validate.py)

Tolerance: max(¥1,000 absolute, 1e-6 relative). PASS / FAIL / SKIP per row;
failures report the exact difference and are never auto-corrected; missing
fields SKIP and are never imputed.

| Check | Identity |
|---|---|
| V1 | total_assets = total_liab + total_hldr_eqy_inc_min_int |
| V2 | total equity incl. minority = excl. minority + minority_int |
| V3 | n_incr_cash_cash_equ = CFO + CFI + CFF + FX effect |
| V4 | end cash = beginning cash + net increase |
| V5 | coverage: annual report present per completed fiscal year |
| V6 | n_income = total_profit − income_tax |

## First live run — 600519.SH (Kweichow Moutai), 2026-11-19

- 68 balance sheets, 65 income statements, 63 cash flows (consolidated,
  2014 FY–2026 Q3, incl. revisions). Re-run inserted 0 rows (idempotent).
- All identity checks PASS; 0 FAIL. 3 SKIPs on V3: Q1 2017/2018/2019 rows
  have null CFF in source — flagged, not imputed.
- Sanity-checked against reported figures (2023: revenue ¥147.7B, parent
  net income ¥74.7B, total assets ¥272.7B — correct for Moutai).

## Known limitations / open issues

- Gateway returns **no rows for report_type 6/4/5** (parent company,
  adjusted). Only consolidated statements available for now. Revisit if the
  vendor enables them; parent-company analysis blocked until then.
- `ann_date`/`f_ann_date` preserved but publication-date-based point-in-time
  queries not yet built (needed for restatement-aware analysis later).
- Rate limit (30/min) is a guess for the third-party gateway; tune if the
  all-A-share crawl (Module 15) hits limits.
