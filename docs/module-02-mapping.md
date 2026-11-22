# Module 2 — Standardized Mapping Layer

## Architecture

```
config/mapping_tushare.yml    Editable mapping: raw field -> concept, 中文 label,
                              default Penman class, judgmental-item notes
pipeline/mapping.py           load_mapping (validates), select_preferred,
                              build_facts (wide->long), derive_single_quarters,
                              mapping_coverage, build_std_facts
CLI: .venv/bin/python -m pipeline.cli map 600519.SH
```

## `std_facts` table (DuckDB)

One row per fact. Columns: ts_code, end_date, report_type, statement, concept,
raw_field, label_zh, penman_class, note, value, value_type, period_kind, basis,
unit, f_ann_date, update_flag, source_row_hash, mapping_version.

- **value_type**: `reported` (verbatim from preferred raw row) or `calculated`
  (derived single quarters). Estimates/assumptions will be further types later.
- **period_kind**: `point` (balance sheet), `cumulative` (income/CF as
  reported, YTD), `single_quarter` (derived: Qn = cum Qn − cum Qn−1).
- Preferred row per (ts_code, end_date, report_type): update_flag desc,
  f_ann_date desc, fetch time desc. Superseded rows stay in raw_*.
- Nulls emit no fact (missing stays missing). Per-share fields never differenced.
- Deterministic rebuild from raw + config (delete company's facts, re-insert).
- `source_row_hash` links every fact back to its exact raw row.

## Default Penman classes (Module 3 consumes; EDITABLE defaults, not truth)

BS: operating_asset / financial_asset / operating_liability /
financial_obligation / equity / minority_interest / subtotal /
**presentation_combined** (Tushare combined display fields like
accounts_receiv_bill that overlap granular fields — never sum with them).
IS: operating_income / operating_expense / financing / tax / subtotal /
per_share / other_comprehensive / minority.
CF: operating / investing / financing / fx / subtotal / supplemental.

Judgmental classifications carry `note` in the YAML. For 600519.SH the key
ones are the **finance-subsidiary items**: deposits taken (吸收存款及同业存放,
default financial_obligation), interbank lending, loans issued, interest
income/expense inside the income statement. Also money_cap (operating cash
portion), invest_income, other_current_assets (wealth-management products).
Module 3 must expose these as per-company overrides.

Beware Tushare misnomers: `decr_oper_payable` is actually *decrease in
operating receivables* (经营性应收项目的减少); labels in the YAML follow the
true meaning. `free_cashflow`, `ebit`, `ebitda` are vendor-calculated with
opaque definitions — tagged, not for analytical use.

## Validation results — 600519.SH (2026-11-19)

- 8,451 facts (5,685 reported + 2,766 calculated single-quarter)
- Coverage: **all populated raw fields mapped** (unmapped fields would be listed)
- M1 round-trip: 0 mismatches between reported facts and raw source values
  (checked every mapped field in all three statements)
- M2: single-quarter sums equal FY cumulative for every complete year
  2015–2025, diff 0.0; derived Q4-2023 revenue ¥44.43B matches reported Q4
- M3: 0 duplicate reported facts (preferred-row selection unique)
- M4: assets = liabilities + equity holds on std_facts for every period
- Unit tests: 23/23 passing

## Open issues

- Classification overrides per company (e.g., Moutai finance subsidiary as a
  separate segment) deferred to Module 3's reformulation layer.
- `end_type` (period type flag) not yet used; revisit for odd fiscal periods.
