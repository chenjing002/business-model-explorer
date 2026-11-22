# Module 16 — Batch analysis for all A-shares

Runs the analysis layer (Modules 2–12) and the bundle export for every
company stored by Module 15, so the company picker can open them. Each
company runs on its own; a failure is logged with the step and the error
message, and the batch moves on. Identity checks are summarised per company
and reported in the picker and the company bar, never forced to zero.

## Files

```
pipeline/
  bulk_analyze.py    eligibility → per-company steps → check summary →
                     analysis_log / analysis_checks → company index + CSVs
  export.py          bundles gzipped ({ts_code}.json.gz); market-dependent
                     tables may be empty; index gains unavailable / check_failures
  valuation.py       no year-end price → model values only, val_flags no_market_data
  reformulate.py     impairment sign follows the statement format (see below)
config/mapping_tushare.yml   + deriv_liab; oth_eq_ppbond moved to equity (memo)
app/src/
  data.ts            loadBundle: gzip bytes or server-decoded JSON (magic bytes)
  companies.ts       unavailable reasons, step / check-family labels (Chinese)
  CompanyPicker.tsx  reason tags (金融类 / 无年报 / 分析失败 / 未分析)
  App.tsx            reason-specific notice; company-bar check warning
tests/test_bulk_analyze.py   eligibility, failure capture, incremental, tolerances
```

## Commands

```bash
.venv/bin/python -m pipeline.cli analyze-all                    # everything stored
.venv/bin/python -m pipeline.cli analyze-all --industry 白酒
.venv/bin/python -m pipeline.cli analyze-all --codes 600519.SH,000858.SZ --force
.venv/bin/python -m pipeline.cli companies                      # index only
```

Options: `--limit N` (trial), `--force`, `--out app/public/data`,
`--tax-rate 0.25`, `--r-op 0.08`, `--r-e 0.08`, `--g 0.03` (assumptions, as
the single-company commands). Reports go next to the database:
`data/analysis_summary.csv`, `analysis_failures.csv`,
`analysis_check_summary.csv`, `analysis_check_failures.csv`.

## Eligibility (from stored raw statements, never guessed)

| Status | Reason | Rule |
|---|---|---|
| skipped | `financial` | latest annual report's `comp_type` ≠ 1 (bank 2, insurer 3, broker 4, other 7). Their statement layout needs its own mapping — not built. |
| skipped | `no_annual_report` | no consolidated `****1231` balance sheet yet (new listings). |
| failed | `error` + step | an exception in any step; the stale bundle is deleted. |
| ok | — | bundle exported; failed check families recorded. |

## Incremental runs

A company is skipped when its input fingerprint is unchanged since its last
logged run (and, for a success, its bundle file still exists). The
fingerprint covers the company's raw rows (count and latest `_fetched_at`
across the three statements and `daily_basic`) plus a hash of the mapping /
override / disclosure configs and the analysis module sources. Editing any
of those modules therefore reruns every company (~1.7 h).

## Identity checks

Per company and family, annual rows only, with the tolerances printed by the
single-company CLI: R1–R3 and L > ¥1M, R4 > ¥1M on cumulative annual rows,
E3 > ¥0.001, E1–E2 > ¥1M (they difference the totals L1/L2 check at ¥1M; with
the CLI's ¥0.001 the first full run failed 1,060 companies on sub-¥1M R1
residuals, median ¥1,150, that pass everywhere else), T > 1e-12, B > ¥1, RI1–RI2 > ¥1 / RI3–RI4 > 1e-12, V > ¥1 /
M1 > 1e-4 relative. Null residuals (not computable) are not counted. E4 and M2
are informational (as in the CLI). **L4** — the company's own indirect-method
bridge (net income + noncash items + ΔOWC vs CFO) — is counted as a
*diagnostic* family: a residual there means the supplementary disclosure does
not add up, not that the reformulation broke, so it does not reach the
picker's warning. Downstream checks inherit upstream failures: on a 200-company
sample every L1/L2 failure coincided with an R1–R3 failure, every L3 with R4,
and E1/E2 are year-on-year deltas of the same totals.

## Fixes found by running beyond 600519.SH

Moutai's results are unchanged by all of them (17 tables compared against a
pre-run backup: every number identical; only two notes reworded).

1. **Impairment sign by statement format** (`reformulate.unusual_sign`). Old
   CAS layout (to FY2018): 资产减值损失 / 信用减值损失 sit inside 营业总成本,
   + = loss. 财会〔2019〕6号 layout (from the 2019 interim): below operating
   costs, "损失以'-'号填列". All-A-share annual rows: 2009–2018 资产减值损失
   reconciles operating profit only as an expense line (≈23k rows, none in the
   new layout); FY2019+ is 96% negative; 信用减值损失 was 81% positive in FY2018
   (early adopters, old layout). The pipeline had hard-coded the expense sign
   for 资产减值损失 (Moutai has none after 2019) — 五粮液 R4 was exactly 2 × the
   line every year from 2019. Remaining exceptions (~0.4% of company-years)
   show in R4; per-company `income_sign_by_period` overrides still win.
2. **其他权益工具-永续债** (`oth_eq_ppbond`) was mapped as a financial asset;
   it is the issuer's perpetual bond inside equity (a memo of 其他权益工具).
   000860.SZ 2016–2018 had R1 = R3 = −¥1.0bn.
3. **衍生金融负债** (`deriv_liab`, 659 companies) was stored but unmapped →
   R2/R3 residuals; now a financial obligation, mirroring 衍生金融资产.
4. **No year-end price** (136 companies listed after the latest year end, or
   suspended on every year-end trading day): valuation used to fail the whole
   company; now model values are kept, market columns stay null and
   `val_flags = no_market_data`; the valuation page says so.
5. Moutai-specific notes (inventory "基酒", FLEV "Moutai case") made generic.

Found on the first full run (5,477 companies) and fixed before the second:

6. **Impairment sign read from 营业总成本** (`reformulate.impairment_signs`).
   224 R4 cells were exactly 2 × 资产减值损失, all FY2016–2018 and mostly
   negative values whose 营业总成本 includes the loss as +|v| (213 of 224) —
   restated comparatives stored with the new display sign. Where impairments
   sit inside 营业总成本, `营业总成本 − other cost lines = Σ(−sign × value)`
   decides the sign when exactly one combination matches (¥1,000 / 1e-6
   tolerance as the other reported identities); otherwise the period default.
7. **Finance / insurance-subsidiary lines in comp_type-1 groups** mapped
   where an all-A-share check showed the field alone explained the residual
   wherever populated (rows that passed held only sub-¥1M amounts):
   代理买卖证券款 (financial obligation — the client cash is in 货币资金),
   保险合同准备金 / 应付分保账款 (operating liabilities), 现金及存放中央银行款项 /
   存出保证金 / 以摊余成本计量的金融资产 (financial assets), 应收保费 / 应收分保账款 /
   应收分保合同准备金 (operating assets), 提取保险合同准备金净额 (operating
   expense, part of 营业总成本). Left unmapped because they overlap mapped
   lines where populated: `depos`, `payables`, `acc_receivable`,
   `invest_as_receiv`.
8. **Pre-revenue companies** (688759.SH, 688837.SH): the value-creation bridge
   needs revenue in consecutive years, so `value_bridge_annual` is empty and
   export used to fail; it is now exported as [] like the market tables (the
   page already says the bridge is unavailable).

On 43 affected companies these took R4 failures from 25 companies / 89 rows
to 13 / 34 and L from 23 to 13; 600519.SH stayed identical across 23 tables.

Found on the second full run and fixed before the third:

9. **年度演化 structural zeros** (`econ_evolution.COMPONENT_GROUPS`). A group
   summed from line items (供应商信用, 预收款项, 存货, …) with no lines in one
   year was `NaN` for that year, although `_balances` already counted it as 0
   inside that year's "other" group — so its whole closing balance dropped out
   of the E1/E2 delta (215 company-years with R1 = 0 in both years, e.g.
   920799.BJ 2015). One-sided absence now opens/closes at 0 with
   `group_absent_begin` / `group_absent_end`; absent in both years stays
   undisclosed. Missing *totals* are never zeroed.
10. **Chinese labels for 12 flag codes** first produced by non-Moutai companies
    (`reoi_base_not_positive_suppressed` ×32,630, `oi_near_zero_suppressed`,
    `no_revenue`, `supplemental_not_disclosed`, …) — they were printed as
    English codes. An app test now scans every `flags.append("…")` in
    `pipeline/*.py` and fails on a code without a Chinese label.

Still unmapped on purpose: `total_opcost` (营业总成本(二), a subtotal) and
`amodcost_fin_assets` (a 其中 memo of 投资收益) — summing either would double
count; finance-subsidiary lines in ≤ 15 companies each (insurance reserves,
deposits, agency securities) need case-by-case classification and stay
visible as R residuals. Vendor rows missing granular lines (e.g. 002127.SZ
2015: 流动资产合计 ¥1,292.5M vs ¥1,212.9M of disclosed lines) remain honest
R1 residuals.

## Bundle size

The Moutai bundle is ~2.4 MB of JSON (half of it `calculation_details`);
gzipped ~0.35 MB. Bundles are written gzipped (`mtime=0`, so identical content
gives identical bytes) and the old plain `{ts_code}.json` is removed on
export. Vite dev/preview serve `.gz` with `Content-Encoding: gzip`, so the
browser decodes it; `parseBundleBytes` checks the gzip magic bytes and
decompresses with `DecompressionStream` only when needed.

## Results (2026-11-21, third full run, final code)

5,580 stored companies in 96.6 min (~1 s each, one process):

| Status | Companies |
|---|---|
| ok — bundle exported | 5,479 |
| skipped: financial statements (comp_type 2/3/4/7) | 97 |
| skipped: no annual report yet | 4 |
| failed | 0 |

Identity checks (annual rows; companies with ≥1 failing row):

| Family | Run 1 | Run 2 | Run 3 | Rows failed / checked (run 3) |
|---|---|---|---|---|
| R1 assets | 371 | 365 | 365 | 1,087 / 61,751 |
| R2 liabilities | 316 | 305 | 305 | 798 / 61,665 |
| R3 equity | 305 | 296 | 296 | 1,088 / 61,526 |
| R4 pretax classification | 310 | 142 | 142 | 363 / 61,805 |
| L map (L1–L3, L5) | 557 | 411 | 411 | 2,516 / 231,614 |
| E evolution (E1–E3) | 1,060 | 622 | 331 | 2,242 / 617,316 |
| T driver tree, B capital bridge, RI residual income, V valuation | 0 | 0 | 0 | 0 / 1,288,919 |
| L4 disclosed indirect bridge (diagnostic) | 4,531 | 4,533 | 4,533 | 23,988 / 60,121 |

457 analysed companies (8.3%) carry at least one failing identity family and
show it in the company bar; 5,022 are clean. Every L1/L2 failure coincides
with an R1–R3 failure and every L3 with R4; E3 never fails. Of the
remaining R1–R3 residual cells, ~80% match no single raw field — vendor rows
missing several granular lines (002127.SZ 2015 type) — and are left as
reported residuals. The 142 R4 companies are mostly the remaining
impairment-layout exceptions and rows with unmapped insurance cost lines.

Verification: pipeline tests 134/134, app tests 37/37, `npm run build`
clean; 600519.SH identical to the pre-module backup across 24 tables;
headless Chrome over 30 random + 8 edge-case companies × 6 pages (negative
NOA/equity, losses, no year-end price, pre-revenue, structural-zero groups,
vendor gaps) — no exceptions, console errors, NaN or blank pages; picker
with all 5,580 companies opens in ~0.2 s, ↑/↓ ~24 ms per step.

Sizes: bundles 1.6 GB (5,479 × ~0.3 MB gzipped) in `app/public/data`, copied
to `dist/` by `vite build` (1.8 GB); `data/bme.duckdb` 1.7 GB.

## Follow-ups

- Financial-statement mapping (banks, insurers, brokers: 97 companies).
- Remaining unmapped finance-subsidiary lines that overlap mapped ones where
  populated (`depos`, `payables`, `acc_receivable`, `invest_as_receiv`).
- Delisted companies (Module 15 follow-up) for survivorship-free coverage.
- A full rerun after any analysis-module edit takes ~1.6 h; a cheaper
  re-export path (export.py changes only) would need a finer fingerprint.
