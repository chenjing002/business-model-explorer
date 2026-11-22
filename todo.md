# Business Model Explorer — Roadmap & Status

Incremental development: one module per iteration. Each module must be
implemented, tested, and validated before the next begins.

## Module status

| # | Module | Status | Depends on | Notes |
|---|--------|--------|------------|-------|
| 1 | Tushare ingestion & financial validation (one company, 10y) | **done** (2026-11-19) | — | Python pipeline, DuckDB storage; see docs/module-01-ingestion.md |
| 2 | Standardized mapping layer (raw line items → analytical concepts) | **done** (2026-11-19) | 1 | YAML-driven; see docs/module-02-mapping.md |
| 3 | Penman reformulation engine (NOA / NFO / CSE, reformulated IS) | **done** (2026-11-19) | 2 | docs/module-03-reformulation.md |
| 4 | Ratio & decomposition engine (RNOA, ROCE, margins, turnover) | **done** (2026-11-19) | 3 | docs/module-04-ratios.md |
| 5 | Working capital & cash conversion (DIO/DSO/DPO/CCC) | **done** (2026-11-19) | 2,3 | docs/module-05-working-capital.md |
| 6 | Earnings-to-cash reconciliation (waterfall) | **done** (2026-11-19) | 2 | docs/module-06-cash-reconciliation.md |
| 7 | Frontend scaffold (React + TS + ECharts), data export from DuckDB | **done** (2026-11-19) | 3,4 | docs/module-07-frontend.md |
| 8 | Interactive Business Economics Map | **done** (2026-11-19; 可视化重设计 + 年度演化扩展 2026-11-20) | 7 | docs/module-08-economics-map.md |
| 9 | Profitability Driver Tree | **done** (2026-11-19) | 4,7 | docs/module-09-driver-tree.md |
| 10 | Capital employed & reinvestment (Capital Investment Bridge) | **done** (2026-11-19) | 3,4 | docs/module-10-capital-bridge.md |
| 11 | Growth quality & residual income | **done** (2026-11-19) | 4 | docs/module-11-residual-income.md |
| 12 | Valuation & reverse analysis | **done** (2026-11-19) | 11 | docs/module-12-valuation.md |
| 13 | /knowledge page (financial concepts KB) | **done** (2026-11-19) | 7 | 34 Chinese concepts, search, contextual links; docs/module-13-knowledge.md |
| 14 | Reference cases (贵州茅台六步导览) | **done** (2026-11-19) | 7 | 仅保留 600519 六步商业实质导览；docs/module-14-reference-cases.md |
| 15 | Incremental ingestion for all A-shares | **done** (2026-11-20) | 1 | 5,580 listed companies, raw only; docs/module-15-bulk-ingestion.md |
| 16 | Batch analysis for all A-shares (Modules 2–12 + export) | **done** (2026-11-21) | 2–12, 15 | 5,479 analysed, 97 financial + 4 no-annual skipped, 0 failed; docs/module-16-bulk-analysis.md |

## Module 1 — Tushare ingestion & financial validation

**Objective:** Import 10 years of financial statements (balance sheet, income,
cash flow) for one A-share company from Tushare Pro, preserve complete raw
data with provenance metadata, store in DuckDB, and validate against
accounting identities. No silent reconciliation.

**Data requirements:** Tushare Pro `balancesheet`, `income`, `cashflow` APIs
via purchased gateway (`https://tuaremax.top`), token in `.env`.
All original line items, `report_type`, `comp_type`, `ann_date`, `f_ann_date`,
`end_date`, `update_flag` preserved verbatim.

**Key conventions (documented in docs/module-01-ingestion.md):**
- Tushare income & cash flow figures are cumulative year-to-date per period.
  Single-quarter figures are a *derived* layer, never overwrite raw.
- `report_type` 1 = consolidated; 6 = parent company; others preserved as-is.
- All values stored as reported (CNY, units as returned by API).

**Validation checks (see pipeline/validate.py):**
- V1 Balance sheet identity: assets = liabilities + total equity (incl. minority)
- V2 Equity composition: total equity incl. minority = excl. minority + minority
- V3 Cash flow identity: net cash increase = CFO + CFI + CFF + FX effect
- V4 Cash roll-forward: end cash − begin cash = net increase
- V5 Cumulative monotonic periods present (Q1→Q2→Q3→FY coverage per year)
- V6 Income statement: net income vs total profit − income tax (tolerance flag)
- Each check reports PASS / FAIL / SKIP(missing data) per row. Failures are
  reported, never auto-corrected.

**Acceptance criteria:**
- [x] Live fetch of 10y+ statements for 600519.SH stored in DuckDB with provenance
- [x] Re-running ingestion is idempotent (no duplicate rows; revisions kept as new rows keyed by update_flag/f_ann_date)
- [x] Validation report generated; all identity checks pass or failures explained
- [x] Unit tests pass offline on fixture data (no token required)

**Test results (2026-11-19):**
- Unit tests: 14/14 passing (`pytest tests/ -q`)
- Live run 600519.SH: 68 BS / 65 IS / 63 CF rows, 2014FY–2026Q3, incl. revisions
- Identity checks: all PASS, 0 FAIL; 3 SKIP (null CFF in Q1 2017–2019 source rows)
- Idempotency: second ingest run inserted 0 rows
- Sanity vs reported: Moutai 2023 revenue ¥147.7B / parent NI ¥74.7B / assets ¥272.7B ✓

## Module 2 — Standardized mapping layer

**Objective:** Transform raw wide Tushare rows into a long `std_facts` table of
standardized concepts, driven by an editable YAML mapping
(`config/mapping_tushare.yml`), preserving full source detail and provenance.
Carries editable default Penman classes (operating vs financial) consumed by
Module 3 — defaults only, judgmental items flagged with notes.

**Data requirements:** raw_* tables from Module 1 (consolidated, 600519.SH).

**Logic / formulas:**
- Preferred-row selection per (ts_code, end_date, report_type): highest
  update_flag, then latest f_ann_date, then latest fetch. Rule explicit;
  superseded rows remain in raw.
- Wide→long: one fact per non-null mapped field; null = not disclosed →
  no fact emitted (never imputed). value_type='reported'.
- Single-quarter derivation (income & cashflow, cumulative YTD):
  Q1 = cum(Q1); Qn = cum(Qn) − cum(Qn−1). value_type='calculated',
  period_kind='single_quarter'. Missing prior cumulative → no derived fact.
  Per-share fields excluded (not additive across quarters).
- Tushare combined presentation fields (accounts_receiv_bill, oth_rcv_total,
  fix_assets_total, cip_total, oth_pay_total, accounts_pay, long_pay_total)
  are tagged class='presentation_combined' — they overlap granular fields
  and must never be summed with them.

**Acceptance criteria:**
- [x] M1 Round-trip integrity: every fact value equals its raw source field on the preferred row
- [x] M2 Derived single quarters: sum of four single quarters == FY cumulative (where all present)
- [x] M3 Exactly one preferred row per (ts_code, end_date, report_type, statement)
- [x] M4 Standardized identity: assets = liabilities + equity holds on std_facts
- [x] Coverage report lists populated-but-unmapped fields; key fields all mapped
- [x] Unit tests pass offline; live build for 600519.SH verified against raw

**Test results (2026-11-19):**
- Unit tests: 23/23 passing (9 new mapping tests)
- Live build 600519.SH: 8,451 facts (5,685 reported, 2,766 calculated);
  all populated raw fields mapped; M1–M4 all verified with 0 violations;
  derived Q4-2023 single-quarter revenue ¥44.43B matches reported Q4

## Module 3 — Penman reformulation engine

**Objective:** Reformulate balance sheet (NOA = OA−OL, NFO = FO−FA,
CSE = NOA−NFO−MI) and income statement (operating vs financing with explicit
tax allocation) from std_facts, with per-company classification overrides,
auditable coalesce decisions for Tushare combined fields, and full
reconciliation to reported statements. Residuals reported, never forced.

**Formulas:**
- OA/OL/FA/FO = Σ facts by effective class (default YAML class + overrides);
  subtotals/presentation_combined/equity excluded from sums
- Coalesce groups (combined vs granular Tushare fields): use granular when
  granular sum ≈ combined or combined missing; else use combined (class =
  group default, decision + reason recorded per period)
- NFE_pretax = financing expenses − financing income (concept-level signs)
- Tax allocation (Penman): NFE_after_tax = NFE × (1−t), t = statutory rate
  assumption (default 25%, recorded as assumption); OI_after_tax =
  net_income_total + NFE_after_tax
- Reconciliations: R1 OA+FA vs total_assets; R2 OL+FO vs total_liabilities;
  R3 NOA−NFO−MI vs reported parent equity; R4 classified pretax items vs
  reported pretax profit (residual = unclassified, reported explicitly)

**Acceptance criteria:**
- [x] R1–R3 residuals ≈ 0 for 600519.SH all periods — exactly 0 after explicit-fields re-ingest
- [x] R4 residual ≈ 0 — 0 for all cumulative periods; 6 single-quarter rows flagged & explained (partial quarterly disclosure)
- [x] Coalesce decisions recorded and auditable per period (302 recorded)
- [x] Overrides mechanism works (test-covered)
- [x] Negative NFO (net financial assets, the Moutai case) handled
- [x] Unit tests pass offline; live run verified

**Test results (2026-11-19):** 33/33 tests. Key fixes along the way:
(a) gateway default field set omits newer CAS lines → explicit field lists in
pipeline/fields.py (R1 residual ¥8.8B → 0); (b) post-2019 impairment lines
are income-signed in Tushare vs expense-signed old assets_impair_loss →
UNUSUAL_SIGNS map (R4: 57 flagged periods → 6, all single-quarter, explained).

## Module 4 — Ratio & decomposition engine

**Objective:** Nissim–Penman profitability decomposition on annual data, both
average- and opening-capital conventions, with explicit guards for negative or
near-zero denominators. Persist resolved balance-sheet components (post-
coalesce) so every ratio decomposes to auditable line items.

**Formulas (annual; capital basis stated per row):**
- RNOA = OI_after_tax / NOA_capital;   RNOA = OPM × ATO
- OPM = OI_after_tax / total_revenue;  ATO = total_revenue / NOA_capital
- OLLEV = OL_capital / NOA_capital (operating liability leverage)
- FLEV = NFO_capital / TE_capital;  NBC = NFE_after_tax / NFO_capital
- Spread = RNOA − NBC;  ROTCE = RNOA + FLEV × Spread  (total-equity level,
  TE = NOA − NFO = equity incl. minority — identity exact at this level)
- Parent ROCE = NI_parent / CSE_capital reported separately WITHOUT the
  identity (minority interests prevent the simplified decomposition)
- ATO decomposition: component_to_sales = avg component balance / total_revenue
  (inverse-turnover form; components from resolved post-coalesce balances)
- Margin decomposition: gross margin (revenue vs COGS — product-business
  proxy, noted), expense ratios, core vs unusual OPM
- Guards: |capital| < 5% of revenue → percentage ratios suppressed (NaN) +
  flag; NFO < 0 flagged informational (net financial assets); first year NaN
  (no opening balance). Never emit a misleading percentage.

**Acceptance criteria:**
- [x] K1 RNOA = OPM × ATO exact; K2 ROTCE identity = direct computation exact (1e-16)
- [x] Both capital conventions produced and labeled
- [x] Negative-NFO (Moutai) and near-zero guards test-covered
- [x] Resolved BS components persisted (reformulated_bs_components)
- [x] Live run: Moutai RNOA (123–227%) ≫ ROTCE (25–38%), cash-drag FLEV ≈ −0.8
- [x] All tests pass (40/40)

**Test results (2026-11-19):** RNOA decline 2019→2025 is pure ATO (4.6→2.5),
margin flat ~50% — NOA growing faster than revenue. roce_parent matches
external ROE sources. Gotcha fixed: `flags` column renamed `ratio_flags`
(pandas Series shadows `.flags` attribute, same trap as `.diff`).

## Module 5 — Working capital & cash conversion

**Objective:** Annual cash-conversion metrics from resolved components
(no double counting), plus pure, testable simulation functions (capital
released by efficiency changes; WC investment required by growth). Engine
only — interactive UI arrives with Module 7+.

**Formulas (average balances; 365-day year):**
- DIO = 365 × avg inventory / COGS
- DSO = 365 × avg TRADE receivables / revenue (notes + accounts + combined +
  receivables financing; other_receivables excluded — not trade)
- DPO = 365 × avg trade payables / purchases, purchases = COGS + ΔInventory
  (approximation DISCLOSED in `dpo_method`; COGS-only variant also reported)
- Advance days = 365 × avg customer advances (预收+合同负债) / revenue
- CCC = DIO + DSO − DPO (advances reported separately, not netted into CCC)
- OWC = inventory + trade receivables + prepayments − trade payables −
  other op payables − customer advances; OWC% of sales; ΔOWC vs Δrevenue;
  incremental OWC/Δrevenue guarded (|Δrev| < 5% of revenue → NaN + flag)
- Simulations: (a) hold sales/cost constant, vary DIO/DSO/DPO/advance days →
  required OWC and capital released; (b) constant efficiency, grow revenue →
  annual ΔOWC cash absorption. Faster turns release capital without changing
  operating income — the Bezos/Amazon lesson, test-asserted.

**Acceptance criteria:**
- [x] Metric cross-checks: DIO/DSO/DPO recomputed from raw components match
- [x] Moutai sanity: DIO 1,200–2,400 days, DSO 0–7, advance days 121→19
- [x] DPO approximation method disclosed (`dpo_method` column; dpo vs dpo_cogs
      diverge 62 vs 92 days in 2025 — disclosure matters)
- [x] Simulations: efficiency change releases capital, income not an output;
      growth mode absorbs cash, zero growth ⇒ zero investment
- [x] Missing data → NaN + flag (2021–22 CCC NaN: receivables undisclosed);
      48/48 tests pass

**Test results (2026-11-19):** key finding — Moutai's customer-advance
financing is eroding (121 → 19 days since 2016) while DIO rises again;
OWC stays ≈ 0–40% of sales only because advances+payables+salary/tax
payables fund the giant inventory.

## Module 6 — Earnings-to-cash reconciliation

**Objective:** True NI → CFO → FCF reconciliation from the reported
indirect-method supplemental disclosure (supp_* facts), as ordered bridge
steps ready for a waterfall UI. Residuals reported, never forced. FCF
definitions kept separate and labeled; no automatic good/bad judgment of
FCF levels.

**Structure:**
- Bridge: supp_net_profit + ordered add-backs (impairments, D&A incl. ROU,
  disposal/write-off losses, FV losses, finance expense, investment loss,
  deferred tax moves, ΔOWC trio) = computed CFO
- Checks: C0 supp_net_profit vs income-statement n_income (informational);
  C1 computed bridge vs supp_cfo_indirect; C2 supp_cfo_indirect vs direct
  n_cashflow_act. All residuals reported per year.
- CFO → FCF variants (formulas carried in output):
  fcf_simple = CFO − capex_paid;
  fcf_after_disposals = CFO − capex + asset disposal proceeds.
  CAS convention preserved and documented: interest received sits in
  investing, interest+dividends paid in financing — CFO is not adjusted.
- cash_conversion = CFO / NI (guard |NI| near zero); accruals = NI − CFO.
- Years without supplemental disclosure → flagged missing, no bridge.

**Acceptance criteria:**
- [x] C1 residual ≈ 0 for all 12 annual years (sign convention verified)
- [x] C2: indirect CFO equals direct CFO every year
- [x] Bridge steps ordered & labeled (start/adjustment/total) for waterfall
- [x] FCF variants arithmetically consistent; definitions carried as text
- [x] Missing supplemental → flag + no bridge (test-covered); 54/54 tests

**Test results (2026-11-19):** cash conversion ~1.0 avg with real swings
(2022: 0.56; 2025: 0.72 — ¥25B absorbed into WC: inventory build ¥7.1B,
receivables +¥11.0B, payables −¥6.8B), matching Module 5's rising DIO and
eroding advances. Capex ¥1–5B vs CFO ¥37–92B → FCF ≈ CFO.

## Module 7 — Frontend scaffold & data export

**Objective:** (a) `pipeline/export.py`: versioned per-company JSON bundle
from DuckDB (annual reformulated BS/IS, ratios, working capital, cash bridge
+ summary, resolved components, reconciliation flags — all precomputed; the
frontend performs NO financial math). (b) `app/`: Vite + React + TS + ECharts
scaffold with typed data model mirroring the export schema, restrained design
(no gradients/KPI-card noise), company/year context, and a working Overview
page proving the pipe: RNOA vs ROTCE series, NOA/NFO evolution, selected-year
cash waterfall, WC days series. Charts receive data via props; formulas stay
in Python.

**Acceptance criteria:**
- [x] Export: 173 KB bundle for 600519.SH; schema_version 1; NaN→null;
      offline test on tmp DB; fails loudly if pipeline incomplete
- [x] App: `tsc --noEmit` (strict) clean and `vite build` succeeds
- [x] Overview: 4 charts wired (returns, capital stocks, waterfall, WC days);
      per-year flags surfaced; nulls render as gaps/no bars
- [x] No financial formulas in components (data.ts: unit scaling + waterfall
      geometry only)
- [x] Year selector drives the waterfall

**Test results (2026-11-19):** 56/56 pipeline tests; preview smoke test:
index 200, bundle parses (167 bridge steps, 24 ratio rows). Open: full
echarts import (~390 KB gzip) — modularize later; interactive visual pass
scheduled with Module 8.

**Follow-up (2026-11-20):** 页头拆分为网站级导航（公司分析 / 财务知识库 /
参考案例）与公司级栏（公司切换器 · 六个分析页 · 年度）。新增 CLI
`companies` → `app/public/data/companies.json`（5,580 家，110 个行业，
`analyzed` 仅列实际存在的数据包；`export` 后自动刷新）；`CompanyPicker`
支持名称 / 代码 / 拼音首字母 / 行业搜索，按行业分组，↑↓ 逐家、PgUp/PgDn
跨行业、Enter 打开、Esc 关闭。未分析公司显示“尚未生成分析数据包”说明。
测试：pipeline 126/126，app 35/35；headless Chrome 核验键盘导航、搜索、
缺包页与知识库 / 案例页无公司栏。待办：目前只有 600519.SH 有数据包，
其余公司需先跑并验证 Modules 2–12 才能在切换器中“已分析”。

**Follow-up (2026-11-21):** 公司分析页按 ← / → 切换上一家 / 下一家已分析
公司，保留当前分析页与年度；顺序同切换器分组（行业按中文排序、行业未披露
置后，组内已分析在前再按代码），跳过无数据包的公司，首尾循环
（`companyOrder` / `adjacentCompany`，`app/src/companies.ts`）。焦点在
输入框、下拉框、切换器搜索内或按住修饰键时不触发。顺带修正
`searchCompanies` 无当前公司时把“行业未披露”排到最前。测试：app 38/38，
build 通过；headless Chrome 核验 茅台 → 老白干酒 → 舍得酒业 往返、
年度下拉 / 切换器 / ⌘→ 不触发、知识库页不触发。

## Module 8 — Interactive Business Economics Map

**Objective:** Five-layer map of the economic engine, per selected year.
Node values, components and identity checks assembled in Python
(`pipeline/economics_map.py` → `econ_map_nodes`, `econ_map_checks`;
exported in the bundle). Frontend renders layers as columns of node cards
with a contextual inspector (definition, components with values, 10y
history, declared related metrics) — no frontend math, no fake Sankey;
layer-level identities are accounting bridges with reported residuals.

**Layers & nodes (annual; stocks at year end, flows for the year):**
1. Capital sources: common equity, minority interests, financial debt,
   supplier credit (trade payables), customer advances, other operating
   liabilities. Identity: Σ = reported total assets (residual reported).
2. Capital employment: inventory, receivables+prepayments, PPE+CIP+ROU,
   intangibles+other operating, financial assets (the cash pile).
   Identity: Σ = reported total assets.
3. Operating performance: total revenue, gross profit (proxy note where
   finance-sub lines exist), core opex, core OI pretax, unusual, OI after
   tax. Consistency via Module 3's R4 (already ≈0).
4. Cash conversion: NI, noncash add-backs, ΔOWC (bridge trio), CFO, capex,
   FCF. Identity: NI + noncash + ΔOWC = CFO (C1 ≈ 0).
5. Capital allocation: capex (maintenance/growth split NOT claimed —
   labeled unknowable from statements), dividends+interest paid (CAS
   combined line, noted), debt repaid, other financing out (may include
   buybacks — noted), equity raised, FX, net cash change. Identity:
   CFO+CFI+CFF+FX = Δcash (V3).
- Every node: components_json (resolved concepts + values), note,
  related_metrics (declared keys into ratios/wc tables — frontend joins,
  doesn't compute). No causal language; relations labeled as identities
  or definitions.

**Acceptance criteria:**
- [x] Layer identity residuals = 0 for all 60 checks (12y × 5 layers);
      6 new offline tests
- [x] Bundle (300 KB) includes econ_map; Map tab with shared year selector,
      5 layers × 29 nodes/yr, inspector (history, components, related
      metrics, correlation≠causation caveat)
- [x] Capex notes: maintenance/growth split "NOT knowable"; dividends line
      includes interest (CAS); buybacks non-separable — all surfaced
- [x] tsc strict + build clean; preview 200; related-key coverage
      cross-checked Python↔frontend (none missing)

**Test results (2026-11-19):** 62/62 pipeline tests. Browser interaction
pass still pending (`cd app && npm run dev`).

**年度演化扩展（2026-11-20）：** `pipeline/econ_evolution.py` 把地图从年末
快照扩展为年初→年末演化：12 个科目组的期初/期末/变动（占年初总资产比例由
Python 计算），9 个勾稽面板按"期初+披露流量+推算轧差=期末"精确勾稽——披露
流量只取现金流量表/补充资料/利润表原文行并带 basis 标签，缺失披露直接跳过
（不默认为零），账面差额与披露口径的差异一律显式列为推算轧差（声明不代表
直接转换）。前端新 ② 节：双列发散变动条 + 可切换勾稽桥（实色=披露，斜纹=
推算）。E1–E3 实数据残差全 0；109/109 pipeline、24/24 app 测试；1440/390px
截图核验。详见 docs/module-08-economics-map.md。

## Module 9 — Profitability Driver Tree

**Objective:** Hierarchical expandable ROTCE/RNOA decomposition
(`pipeline/driver_tree.py` → `driver_tree_nodes`/`driver_tree_checks`,
assembled from ratios_annual; frontend `DriverTree.tsx` renders and joins —
no math). 21 nodes/yr×basis: ROTCE → RNOA (OPM: core/unusual/gross-margin
context; ATO: NOA/sales with signed component split + residual, OLLEV
context) + FLEV + Spread (NBC). Additive levels carry weights (+1/−1
operating liabilities) and a residual node so signed sums are exact;
residuals reported, never forced. Relations labeled identity/definition —
never causal.

**Acceptance criteria:**
- [x] T1–T5 identity checks ≤ 1e-12 all computable rows (120 checks, 10
      null: first year/suppressed — null, not fabricated)
- [x] Suppression guards from Module 4 propagate (NaN + flag carried)
- [x] Missing component → absorbed by other_net residual, sum stays exact
- [x] sort_order is depth-first; parents/depths consistent (test-covered)
- [x] Frontend tab: expand/collapse, minus badges, inspector with formula,
      10y history, related-metric join (shared metrics.ts, keys verified)
- [x] 70/70 tests; tsc strict + build clean; preview 200; bundle 510 KB

**Test results (2026-11-19):** Moutai 2025 avg: ROTCE 34.4% vs RNOA 122.8%
(FLEV −0.72 cash drag); NOA/sales 0.40 = inventory 0.34 + PP&E 0.13 +
other assets 0.08 − payables 0.10 − advances 0.05; browser interaction
pass still pending.

## Module 10 — Capital employed & reinvestment (Capital Investment Bridge)

**Objective:** Where did the year's capital go, what funded it, and how much
of operating income was reinvested — with exact identities and waterfall-
ready bridge steps (`pipeline/capital_bridge.py` → `capital_bridge_annual`,
`capital_summary_annual`, `capital_bridge_checks`; frontend
`app/src/CapitalView.tsx` Capital tab).

**Structure:**
- Investment side: NOA_begin + Δ component groups = NOA_end. Groups reuse
  Module 8's concept sets (ids match Map node ids), restricted to operating
  effective_class; OA/OL residual groups make the sum exact by construction
  (undisclosed items land in the residual, visibly). Liability growth enters
  with a minus sign. Schema mirrors cash_bridge_annual → WaterfallChart
  reused unchanged. First year: no bridge, flagged no_opening_balance.
- Funding side (Module 3 exact): ΔNOA = ΔCSE + ΔMI + ΔNFO, as columns.
- Checks: B1 bridge additive, B2 ΔNOA vs ΔOA−ΔOL, B3 funding identity —
  all ≈ 0 (float noise only).
- Metrics (guards as Module 4; never a misleading ratio): reinvestment_rate
  = ΔNOA/OI; noa_growth vs revenue_growth; capex vs disclosed D&A
  (supp_* lines; capex_to_da); fcf_from_oi = OI − ΔNOA (Penman) vs
  fcf_simple with fcf_articulation_diff REPORTED (CAS classification,
  dirty surplus, timing — expected nonzero, note carried as text).
  Maintenance/growth capex split carried as "not knowable" note.

**Acceptance criteria:**
- [x] B1–B3 ≈ 0 for all 11 bridge years of 600519.SH (max 5.7e−5 yuan)
- [x] Residual groups absorb undisclosed components, identity stays exact;
      class filter keeps misclassified concepts out (both test-covered)
- [x] Guards: first year / OI near zero / negative or near-zero NOA base /
      D&A undisclosed → NaN + flag
- [x] 80/80 tests; tsc strict + build clean; preview 200; bundle 545 KB
      (110 bridge steps, 12 summary rows, 33 checks); CLI `capital` cmd

**Test results (2026-11-19):** Moutai 2016–2018 ΔNOA negative (2016
reinvestment rate −0.90 — the advances boom meant customers funded more
than the whole asset build); since 2019 NOA grows 10–36%/yr vs revenue
10–18% (2025: +21% NOA on −1% revenue) — the ATO decline of Modules 4/9
in stock form, and the build is inventory (+¥7.1B of +¥13.0B ΔNOA in
2025), not plant (capex/D&A 1.0–3.1). Largest fcf_from_oi vs fcf_simple
gap is 2022 (¥24B), the 0.56 cash-conversion year from Module 6.

## Module 11 — Growth quality & residual income

**Objective:** Charge income for opening capital at explicit required
returns and explain the year-on-year change in residual income with exact
identities (`pipeline/residual_income.py` → `residual_income_annual`,
`value_bridge_annual`, `residual_income_checks`; frontend
`app/src/ValueView.tsx` "Value Creation" tab).

**Formulas (opening capital):**
- ReOI = OI − r_op × NOA_begin; core ReOI likewise; equity RE = NI_parent −
  r_e × CSE_begin. r_op / r_e are ASSUMPTIONS (CLI `--r-op/--r-e`, default
  8%), stored per row; OCI (CI − NI) reported separately (dirty surplus).
- Value Creation Bridge (waterfall): ReOI_{t−1} + ΔRev×PM_{t−1} +
  Rev_t×ΔPM_core + Rev_t×ΔPM_unusual − r_op×ΔNOA_begin = ReOI_t. Exact, no
  RNOA needed; sales-first order is a stated convention.
- Penman drivers: ΔReOI = margin (ΔPM×ATO_{t−1}×NOA_{t−1}) + turnover
  (PM_t×ΔATO×NOA_{t−1}) + growth (s_{t−1}×ΔNOA_begin); only where RNOA is
  meaningful on both bases.
- Checks: RI1 bridge additive, RI2 driver split additive, RI3/RI4 opening
  RNOA/ROCE vs Module 4.

**Acceptance criteria:**
- [x] RI1–RI4 within tolerance all years (money max 1.5e−5 yuan; ratio 0)
- [x] Rate assumptions carried as columns; Δr shifts ReOI by exactly
      Δr × NOA_begin (test-covered)
- [x] Guards: first year / no prior ReOI / negative NOA base (bridge kept,
      drivers suppressed) / non-positive or tiny ReOI base → NaN + flag
- [x] 88/88 tests; tsc strict + build clean; preview 200; bundle 575 KB
      (60 bridge steps, 42 checks); headless-Chrome visual pass of the tab

**Test results (2026-11-19):** Moutai capital charge ¥1.3–5.0B vs OI
¥16–88B → ReOI ≈ OI. ReOI fell ¥4.85B in 2025 (sales −1.06, core margin
−2.51, charge on new NOA −1.31). Penman drivers 2025: growth +¥30.1B vs
turnover −¥31.6B, so the new (inventory) capital earned nothing at the
margin. Equity RE runs ¥2.7–16B below ReOI as the ~¥180B cash pile grows
(ROCE − r_e 18–32 pts vs RNOA − r_op 43–260).

## Module 12 — Valuation & reverse analysis

**Objective:** Value the company under explicit simple forecasting schemes
and reverse-engineer what the market price implies, with rate sensitivity
(`pipeline/market.py` → `raw_daily_basic`, `market_snapshot_annual`;
`pipeline/valuation.py` → `valuation_annual`, `valuation_bridge_annual`,
`valuation_grid`, `valuation_reverse_curve`, `valuation_checks`; frontend
`app/src/ValuationView.tsx` Valuation tab).

**Structure:**
- Market data: Tushare `daily_basic` (works on the gateway), December
  windows, raw + provenance; snapshot = last trading day of the fiscal year;
  万 units converted. Hindsight anchor (year-end price vs later-published
  year-end book) stated everywhere.
- Models (r_op, r_e, g are assumption columns; CLI `--r-op/--r-e/--g`,
  default 8/8/3%): book (SF1), ReOI flat (SF2), ReOI growing at g (primary),
  Penman SF3 RNOA anchor; V_E = V_NOA − NFO − MI at book. Equity RI and AEG
  on the same forecast (identical by algebra); forward vs normal P/E;
  historical AEG with implied net payout d = NI − ΔCSE.
- Reverse engineering, closed form: implied g (ReOI / RNOA / FCF reverse
  DCF / equity RE), implied r_op and r_e at assumed g; each round-tripped.
- Sensitivity: 7×7 r×g grid of V/P (primary model) and implied-g-vs-r curve.
- Valuation bridge waterfall: NOA → ReOI flat / r → growth → NFA → MI →
  model equity → market premium → market cap.

**Acceptance criteria:**
- [x] Checks V1–V10, M1–M2 within tolerance (132 checks; money max
      ¥2.4e−3, M1 1.7e−13, M2 2.4e−6 — Tushare's pe = mcap / prior-year NI
      independently confirms units and the publication lag)
- [x] Implied-g/r round trips exact; undefined solutions → NaN + flag
- [x] Guards: first year, no market data (models kept, reverse dropped),
      g ≥ r (growth models NaN), negative NOA base (RNOA anchor only)
- [x] 101/101 tests (3 market + 10 valuation new); tsc strict + build
      clean; bundle 756 KB; headless-Chrome visual pass (2020, 2025)

**Test results (2026-11-19):** 2025 V/P 1.09 (model ¥1,885B vs mcap
¥1,725B); price implies g 2.5% at r 8% or r_op 8.5% at g 3%. 2020–21 peak
V/P 0.45–0.50 with implied g 5.9% and forward P/E 50 vs model 18; implied
g has fallen every year since. AEG turned negative in 2025 (−¥5.3B).

## Module 13 — Financial concepts knowledge base

**Objective:** A searchable `/knowledge` page, linked throughout the app,
explaining the definitions, formulas, interpretation and limits of the
financial concepts already used in Modules 1–12.

**Acceptance criteria:**
- [x] 34 Chinese concepts across six topics; formula, interpretation, app convention,
      caveat, related concepts and return-to-analysis links per entry
- [x] Search supports acronyms, full text and Chinese aliases; topic filters
      combine with search; empty results have a clear-filters action
- [x] All six analysis views link to concepts; every exported map/tree node
      and every declared shared metric has a validated mapping
- [x] Real `/knowledge/<slug>` deep links, refresh and browser Back/Forward;
      selected year persists in URLs; unknown routes/concepts recover cleanly
- [x] Knowledge renders independently of company-data availability;
      responsive reader and keyboard-accessible native links
- [x] 17/17 frontend tests, 101/101 pipeline tests, strict TS + build pass;
      browser verification at narrow and wide widths, no console errors

**Test results (2026-11-19):** No financial calculations or pipeline schema
changes. Formula conventions remain explicit (average/opening capital,
parent/total equity, DPO estimates, separate FCF definitions, assumed rates,
missing/suppressed values). See docs/module-13-knowledge.md and its screenshot.

**Follow-up (2026-11-20):** 新增三表勾稽示意图 `app/src/ArticulationDiagram.tsx`
（中文 SVG，重构利润表／资产负债表／现金流量表的存量-流量勾稽：NOA、NFO、CSE
三条存量方程 + FCF 经营端与融资端两条公式为同一笔现金，含 OI／NFO／净股利口径
说明），展示于 reformulation、noa、nfo、oi、fcf 五个条目。无金额与单位，纯概念
图。tsc + build 通过，21/21 测试通过，headless Chrome 截图核验。

## Module 14 — 参考案例（贵州茅台）

**当前内容：** `/cases` 与 `/cases/moutai-600519` 展示贵州茅台六步商业实质导览。
按总览→地图→驱动树→资本→价值→估值的顺序引用公司数据包中已算结果，并
链接到相应分析页。Amazon 2004 与运输设备案例已按要求移除，旧地址显示未找到。
实现与口径见 docs/module-14-reference-cases.md。

## 全站中文与金额单位（2026-11-19）

网站默认采用简体中文，财报科目沿用中国企业报表名称，专业术语保留英文缩写。
金额原值为人民币元，图表及科目明细统一按亿元展示；股价及每股价值使用元/股，
收益率差采用百分点，极小金额勾稽差额按元保留精度。知识库新增单位说明。
后续约定见 AGENTS.md，实施与验证见 docs/chinese-display-and-units.md。

## 总览：历年折旧摊销、经营现金流与资本开支（2026-11-20）

“历年盈利、现金流与回报”新增横向年份表（`CashInvestmentTable`，`app/src/Overview.tsx`）：
折旧摊销（`capital_summary.da_total`）、经营活动现金流量净额、减：现金资本开支、
自由现金流（`fcf_simple`）及资本开支／折旧摊销（倍）。表头统一标“亿元”，单元格
不重复单位（`format.ts` 新增 `formatAmountNumber`），条形按本行最大值缩放，所选年度
列高亮，数值可点开原始计算项。纯展示，无管线或公式改动。
同日调整：表格开头加合并净利润（`ni_total`）与归母净利润（`ni_parent`），标题改为
“净利润、折旧摊销、经营现金流与资本开支”；移除“净利润与自由现金流”图表卡片，表格
置于区块首位，每股自由现金流卡片改为整行。

口径复核：亚马逊“operating cycle＝存货天数＋应收天数－应付天数”与现有 CCC 公式一致；
其 FCF“经营现金流减购置固定资产（含资本化内部使用软件和网站开发）”与 `fcf_simple`
（扣减“购建固定资产、无形资产和其他长期资产支付的现金”）扣减范围相近，故不改公式。
知识库 ccc／fcf／capex 补充：营业周期名称差异与分母核对、CAS 利息分类与租赁本金
未扣减、D&A 构成及使用权资产折旧对倍数的影响；新增亚马逊 2004 股东信来源。
测试 31/31，tsc + build 通过，headless Chrome 核验 2025／2018。

## 总览：现金循环周期卡片（2026-11-21）

每股自由现金流下方新增“现金循环周期（CCC）”整行卡片（`CccCard`，`app/src/Overview.tsx`）：
所选年度 CCC（DIO ＋ DSO − DPO，天）、CCC < 0 时标“现金生成型：先收客户款，后付供应商款”，
否则标“经营周期需垫付营运资金”（仅按正负选标签）；十年折线含“扣除客户预收款后”第二条线；
口径说明（存货天数以营业成本为分母、应付以估算采购额为分母、预收款另列）及知识库链接；
“查看逐年明细与计算口径”新增“历年现金循环周期”表（DIO／DSO／DPO／CCC／预收款天数／扣除后）。
管线：`working_capital.py` 新增 `ccc_net_advances` ＝ CCC − 客户预收款天数（任一缺失即为空，
不按零扣减），`calculation_details` 增加同名天数口径；CCC 本身不变。`HistoryChart` 支持“天”单位
（纵轴保留零线）。旧数据包缺该字段时只画 CCC 并提示重新导出。
600519.SH 重新导出：与备份相比仅新增 `ccc_net_advances`（12 年）；2021–2022 应收未披露，CCC 如实留空。
002594.SZ 重新导出用于核验负值（2025 CCC −24 天，扣除后 −46 天）。其余公司待下次 `analyze-all`
（指纹已变，将全量重跑约 96 分钟）。测试：管线 135/135，前端 39/39，tsc + build 通过，
headless Chrome 核验 600519／002594（新包）及 000651（旧包）。

## Module 17 — 好生意榜单（首页，2026-11-22）

网站首页 `/` 改为跨公司榜单（总览移至 `/overview`，站点导航：好生意榜单 · 公司分析 · 财务知识库 ·
参考案例）。`pipeline/screens.py` 读取各公司年度表，按 2021–2025 五年记录生成
`app/public/data/screens.json`（CLI `screens`；`analyze-all` 结束时自动生成）：自由现金流持续增长、
高且稳定的归母 ROE（≥15%）、经营资产回报高（RNOA ≥20%）、先收款后付款（CCC<0 且收入增长）、
利润含金量高（累计 FCF ≥ 累计净利润）及多项入选（≥3 个榜单）。剔除恒等式校验未通过、
年报不足五年及最新营业总收入低于 10 亿元的公司，数量在页面列示。首轮真实数据复核后调整两处排名
（FCF 改为同比中位数并限制单年降幅 ≤20%；CCC 榜按收入规模排序，见 docs/module-17-screens.md）。
2025 年：参与排名 3,166 家；多项入选 26、FCF 65、ROE 96、RNOA 155、CCC 156、含金量 308 家。
测试：管线 146/146、前端 47/47（榜单用合成样例 `tests/fixtures/screens_sample.json` 固定格式）。

## GitHub Pages 发布（2026-11-22）

源码推送到 `chenjing002/business-model-explorer` 的 `main`；静态网站（构建产物 ＋ 公司数据包）
发布到 GitHub Pages。单个 Pages 站点上限 1 GB、数据包约 1.8 GB，故按交易所拆成同源的两个站点：
主站（应用、公司列表、上证与北证数据包）与 `business-model-explorer-data`（深证数据包）。
发布版仅将 `calculation_details` 按科目重组、跨年相同字段只存一次（`by_code_v1`），
逐包校验可完全还原，总量 0.86 GB（两站各约 0.4–0.5 GB）。命令 `pages [--publish]`
（`pipeline/pages.py`），前端子路径与分站取数见 `app/src/site.ts`，说明见
docs/github-pages.md。测试：管线 140/140、前端 42/42；本地模拟 Pages（子路径、404 回退、
gzip 原样下发）以 headless Chrome 核验总览（深证包）、知识库深链与经济地图。
同日按用户要求删除总览顶部横幅（`overview__header`：公司代码行、“××年经营总览”标题、
章节快捷链接与年报链接），总览直接从“历年盈利、现金流与回报”开始；各节年报页码来源链接保留。

## Module 15 — Incremental ingestion for all A-shares

**Objective:** Fetch and store the raw Tushare data of every listed A-share
company (universe, three statements, year-end market data) with the
Module 1 storage rules; resumable and incremental. Raw layer only —
mapping/analysis for other companies is not part of this module.

**Commands:** `ingest-all` (`--list-status L,D`, `--codes`, `--limit`,
`--workers 4`, `--cpm 240`, `--lookback-days 365`, `--force`,
`--no-market`) and `validate-all` (writes `data/bulk_*.csv`).

**Key decisions (gateway probes):** per-company statement calls, because
`balancesheet_vip` omits ~590 listed companies and unpaginated
`cashflow_vip` truncates at 6,400 rows; bulk `daily_basic` by year-end
trade date, paginated; `ingest_log` gives resume and incremental ann_date
windows.

**Store fixes found on the way:** 141 columns typed DuckDB "NULL" from
Moutai's first frame (would reject goodwill / lt_borr / every bank line)
→ explicit column types + lossless repair; SQL anti-join dedupe; field
lists widened to explicit ∪ gateway default (bank deposits, insurance
reserves, client deposits, deriv_liab were dropped before).

**Acceptance criteria:**
- [x] Universe stored (`raw_stock_basic`, 5,580 listed)
- [x] Statements for every listed company with a published report;
      FY2025 annual present for 5,444/5,444 listed by 2025-12-31
- [x] 0 request errors; empty responses only for 4 IPOs of November 2026
- [x] Identity checks run on all rows; failures reported, not corrected
- [x] Idempotent refetch (0 new rows) and resume (0 requests) on live data
- [x] 600519.SH results unchanged (std_facts rebuilt: 8,677 facts, diff 0)
- [x] Offline tests pass (125/125; 12 new)

**Test results (2026-11-20):** 16,725 requests in 72 min, 919,734 rows;
V1–V6 FAIL 167 rows / 94 companies (< 0.03%), see
docs/module-15-bulk-ingestion.md; year-end daily_basic 2014–2025, absent
companies = suspended that day.

**Follow-ups (not started):** delisted companies (`--list-status L,D`) for
survivorship-free history; mapping for banks / insurers / brokers
(comp_type 2/3/4) before Modules 2–12 can analyse them; `total_opcost`
(营业总成本(二)) is now stored and listed as unmapped for 600519.SH.

## Module 16 — Batch analysis for all A-shares

**Objective:** run Modules 2–12 and the bundle export for every stored
company so the company picker can open them; report per-company failures
and identity-check results without correcting them.

**Commands:** `analyze-all` (`--codes`, `--industry`, `--limit`, `--force`,
`--out`, assumption flags as the single-company commands); `companies`
(index only). Reports: `data/analysis_*.csv`.

**Key decisions:** financial statements (comp_type ≠ 1) skipped with reason
until their mapping exists; no annual report → skipped; per-company try with
step-level error capture; incremental by input fingerprint (raw rows +
config + analysis module sources); bundles gzipped (~0.35 MB vs 2.4 MB);
L4 counted as a disclosure diagnostic, not a failure.

**Fixes found on the way:** impairment sign by statement format (old CAS
layout expense-signed to FY2018, 财会〔2019〕6号 income-signed); 永续债 in
equity was mapped as a financial asset; 衍生金融负债 unmapped; valuation
without any year-end price no longer fails the company; Moutai-specific
notes made generic. 600519.SH numbers unchanged (17 tables vs backup).

**Acceptance criteria:**
- [x] Every stored company gets a logged status (ok / failed+step / skipped+reason)
- [x] Picker and notice show the reason; company bar shows failed check families
- [x] Incremental rerun skips unchanged companies; `--force` reruns
- [x] Offline tests (pipeline + app) pass; 600519.SH unchanged
- [x] Full run completed and results reviewed (see docs/module-16-bulk-analysis.md)

**Test results (2026-11-21):** third full run (final code) 96.6 min: 5,479
ok, 0 failed, 97 financial + 4 no-annual-report skipped. T/B/RI/V checks 0
failures; 457 companies (8.3%) flag ≥1 identity family (mostly vendor rows
missing granular lines), shown in the company bar. E failures 1,060 → 331
and R4 310 → 142 across the three runs via the fixes above plus the
年度演化 structural-zero fix and 12 missing flag labels. Pipeline 134/134,
app 37/37, build clean; 600519.SH identical (24 tables); headless Chrome
sweep of 38 companies × 6 pages clean; picker with 5,580 companies ~0.2 s.

**Follow-ups (not started):** financial-statement mapping (97 companies);
overlapping finance-subsidiary lines (`depos`, `payables`,
`acc_receivable`, `invest_as_receiv`); delisted companies; cheaper
re-export path for export-only changes.

## Unresolved issues
- "Today's price" valuation (latest annual anchor rolled forward to a
  later price) not built — needs value roll-forward; see module-12 doc.
- Gateway (tuaremax.top) returns no parent-company (report_type=6) or
  adjusted (4/5) statements — only consolidated available. Parent-vs-
  consolidated comparison blocked until vendor enables them.
- Point-in-time (publication-date-aware) query layer not yet built.
