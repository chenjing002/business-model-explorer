# Module 8 — Interactive Business Economics Map

## Python assembly (`pipeline/economics_map.py`)

CLI `python -m pipeline.cli econmap 600519.SH` → tables `econ_map_nodes`
(ts_code, end_date, layer 1–5, node_id, label, value, flow_or_stock,
components_json, note, related_json) and `econ_map_checks` (layer identity
residuals). Exported in the bundle (300 KB). 29 nodes/year, 12 years.

Layers & identities (residuals reported, never forced — all 0 for 600519.SH):
1. **Capital sources**: CSE, MI, financial debt, supplier credit, customer
   advances, other OL. Σ = reported total assets.
2. **Capital employment**: inventory, receivables+prepaid, PPE+CIP+ROU,
   intangibles+other LT, other OA (remainder), financial assets.
   Σ = reported total assets.
3. **Operating performance**: total revenue, gross profit (营业收入−营业成本,
   finance-sub note), core OI pretax, unusual, OI after tax. Check = R4.
4. **Cash conversion**: NI, noncash add-backs, ΔOWC (bridge trio), CFO,
   capex, FCF. Check = C1 bridge residual.
5. **Capital allocation**: capex, dividends+interest (CAS combined — noted),
   debt repaid, other financing out (may contain buybacks — noted), equity
   raised, net cash change. Check = cash statement identity (V3).

Honesty invariants baked into node notes: maintenance-vs-growth capex is
"NOT knowable from financial statements"; FCF "level alone is not a verdict";
related metrics joined by declared keys only, with an explicit
correlation≠causation caveat in the inspector.

## Frontend (`app/src/EconMap.tsx`) — redesigned 2026-11-20

The page reads top-to-bottom as one year's economic cycle, with connector
arrows carrying the joined turnover/conversion ratios between sections:

1. **① 资本结构** — two aligned stacked bars (资本来源 / 资本占用), both
   summing to total assets, so the accounting identity is visually literal.
   Segment hue = reformulation family (blue operating, teal financial, slate
   equity, amber customer advances, sand "other"); every segment has an
   always-visible clickable chip (swatch + label + value) as labeling relief.
2. **② 营运资金循环** — DIO/DSO vs DPO/预收 day bars on a days scale with a
   CCC marker; copy states CCC = DIO + DSO − DPO and that advance days are
   deliberately NOT netted (joined keys: dio, dso, dpo, advance_days, ccc).
3. **③ 经营成果** — profit funnel 收入→毛利→核心→特殊→税后OI with joined
   margin annotations (gross_margin, opm_core, opm) and an RNOA badge.
4. **④ 现金转换** — NI→CFO→FCF waterfall rows (anchors re-based at reported
   values; capex drawn as the declared "CFO − capex" subtraction) with the
   净现比 (cash_conversion) badge.
5. **⑤ 资本配置** — outflows/inflows/结余 rows with reinvestment badges
   (reinvestment_rate, capex_to_da — declared on the capex_alloc node and
   joined from capital_summary) and a loop-back note into next year's ①.

Sections ①③④⑤ share ONE linear money scale (max of the two asset stack
sums), so capital invested vs profit vs cash compare directly; ② uses a
days scale (labeled). Per-section identity residuals shown verbatim via
`formatResidual`; nulls render as 未披露, never zero. Inspector unchanged:
stock/flow tag, note, 10-year history, components, related metrics,
correlation≠causation caveat. Colors validated with the dataviz palette
checker (adjacent-pair CVD and normal-vision floors pass; neutral slate/
sand band/chroma deviations are deliberate and chip-labeled).

## Verification (2026-11-20 redesign)

- Pipeline tests 105/105; app tests 23/23 (knowledge links added for
  ccc / reinvestment_rate / capex_to_da).
- `npm run build` clean (tsc strict); headless-Chrome screenshots checked
  at 1440px and 390px (sections, waterfall offsets, CCC marker, null years;
  390px verified via in-page probe — scrollWidth 375, no overflow).
- Bundle re-exported: capex_alloc now declares reinvestment_rate/capex_to_da;
  METRIC_SOURCES joins capital_summary; all 60 layer checks still 0.

## 年度演化扩展（2026-11-20）

**Pipeline** `pipeline/econ_evolution.py`（CLI 并入 `econmap` 命令）→ 三张表，
均入导出包（bundle 962 KB）：

- `econ_evolution_groups`：L1/L2 全部 12 个科目组（group_id 与地图节点一致）
  的期初/期末余额、变动额与占年初总资产比例（Python 计算，前端只排序渲染）。
  首年 begin 为 null + `no_opening_balance`。
- `econ_evolution_flows`：按 9 个勾稽面板（披露口径决定粒度：固定+无形合并
  ——资本开支为合并披露；三组经营负债合并——补充资料应付项目为合并披露）输出
  瀑布步骤：期初(start) + 披露流量(adjustment) + 推算轧差(adjustment) +
  期末(total)。每步带 `basis`（balance / disclosed_cashflow /
  disclosed_supplemental / disclosed_income / inferred_residual）与口径 note。
- `econ_evolution_checks`：E1/E2 两端变动合计 vs 报表总资产变动；E3×9 面板
  可加性（按构造精确）；E4 现金期初+净增加=期末（披露值滚动，informational）。

**诚实性规则**：披露流量只取报表原文行（现金流量表、间接法补充资料、利润表）；
缺失的披露行直接跳过（绝不默认为零），差额一律落入"推算轧差"并带说明
（NOT a direct conversion）；补充资料口径与账面科目口径的差异（如 2025 年
经营性应收披露 +109.8亿 vs 本组账面 +24.4亿，财务公司拆出资金所致）如实
留在轧差中。股东分红与利息合并披露、无法分离 → 权益轧差注明为推算净额。

**Frontend**：`app/src/EconEvolution.tsx`，作为地图新 ② 节（原②—⑤顺延为
③—⑥）。两列发散变动条（蓝=增加，红=减少，共用零轴与变动额比例尺，加粗=
变动超年初总资产 1%，每行带期初→期末与占比注记）；点击科目联动右侧原
inspector（group_id=node_id）并切换下方勾稽桥：实色=披露流量（basis 徽章
标注来源报表），斜纹=推算轧差，深灰蓝=期初/期末锚点；桥下列出全部口径
说明与"账面差额≠直接转换"声明。元级极小轧差按 AGENTS 约定缩小到万元/元
展示（`fmtFlowAmount`），不显示成 0.00 亿元。

**验证（2026-11-20）**：pipeline 109/109（新增 test_econ_evolution 8 项）；
实数据 121 项 E1–E3 残差全 0，E4 全 0；app 24/24（新增 evolution.test
3 项：面板可加性+渲染+首年如实说明）；tsc strict + build 通过；CDP 截图核验
1440px（存货、权益面板）与 390px（金融资产面板、无横向溢出——修复了长差额
文本撑破 `.frow__value` nowrap 的溢出）与 2014 首年提示。

## Open issues

- Node set is fixed per schema v1; per-node drill-to-source-row (raw_* hash
  links) deferred to the inspector enhancement pass.
- Stacked-bar segments narrower than ~2px rely on chips/tooltips for
  identification (honest widths kept; no minimum-width distortion).
