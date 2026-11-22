# Module 7 — Frontend Scaffold & Data Export

## Export (`pipeline/export.py`)

CLI: `python -m pipeline.cli export 600519.SH [--out app/public/data]`
→ `{ts_code}.json` bundle (schema_version 1, ~173 KB for 600519.SH).
Contains: reformulated_bs/is (annual), ratios, working_capital, cash_bridge,
cash_summary, bs_components, reclass_decisions + a `conventions` block.
NaN → null ("null means not disclosed — never zero"). Export fails loudly if
any pipeline table is missing (run ingest → map → reformulate → ratios → wc
→ cash first). **The frontend performs NO financial math** — Python owns all
formulas; the app only rescales units and computes chart geometry.

## App (`app/` — Vite + React 18 + TS strict + ECharts 5)

```
src/types.ts        typed mirror of the bundle schema
src/data.ts         loadBundle, unit scaling, waterfall bar geometry
src/useECharts.ts   init/resize/dispose hook (no wrapper dependency)
src/charts/theme.ts restrained palette + conventions
src/charts/*.tsx    ReturnsChart, CapitalChart, WaterfallChart, WcDaysChart
src/App.tsx         site nav + company bar (picker · tabs · year) and routes
src/CompanyPicker.tsx  searchable, industry-grouped company switcher
src/companies.ts    company index loading, search and grouping
src/Overview.tsx    three-part annual business overview
```

Commands: `npm run dev` | `npm run build` (runs `tsc --noEmit` first) |
`npm run preview`. Static output → Cloudflare Workers/Static Assets ready.

Visual conventions encoded in theme: stocks = bars, flows/returns = lines,
calculated/judgmental = dashed, negative adjustments red; line gaps = null
(not disclosed); per-year flags (wc/cf) surfaced in panel notes.

## 年度经营总览

总览按年度展示收入与盈利来源、资本占用与回报驱动、主要余额变动、利润到经营现金流及资金用途。原趋势图和间接法瀑布图可按需展开，多年趋势标记所选年度。金额在数据包中为人民币元，页面按亿元显示。

- 通过 `python -m pipeline.cli export <公司代码> --out app/public/data` 导出，打开 `/?company=<公司代码>&year=<年份>`。其余公司分析页的链接会保留公司与年度。无 `company` 参数时使用默认公司。
- `pipeline/overview.py` 计算同比、资产占比、收益率差值和投资收付净额。缺少输入时保留空值。
- `config/overview_disclosures.yml` 可按公司代码与 `YYYY1231` 增补年报披露。`unit` 使用 `CNY_yuan`，毛利率填小数。`report_url` 填年报 PDF 地址，各披露区块的 `page` 填 PDF 实际页序。分产品、存货构成、现金流解释、股东分配和股份回购均为可选项。配置后重新导出相应公司数据包。

## 网站导航与公司切换（2026-11-20）

- 页头分两层：网站级导航（公司分析 / 财务知识库 / 参考案例）始终显示；公司级栏（公司切换器、总览至估值六个分析页、年度）只在公司分析页显示。`routes.ts` 的 `COMPANY_VIEWS` / `isCompanyView` 定义分层。
- 公司索引：`python -m pipeline.cli companies [--out app/public/data]` 由 `raw_stock_basic`（每家取最新快照）导出 `companies.json`（代码、名称、行业、拼音首字母、板块，约 580 KB）；`analyzed` 只列出目录中实际存在的数据包。`export` 每次导出公司数据包后会自动刷新索引。行业缺失保持 null，前端归入“行业未披露”组，不臆造；数据包对应公司若不在股票列表中也保留。
- 切换器（`CompanyPicker.tsx` + `companies.ts`）：可按名称、代码、拼音首字母或行业搜索，结果按行业分组（无查询时当前公司所在行业在前，其余按中文排序；有查询时按最佳匹配排序，组内已分析公司在前）。键盘：在切换按钮上按 ↓/↑ 打开；↑/↓ 逐家移动（循环）；PgUp/PgDn 跳到上一个或下一个行业；Enter 打开；Esc 关闭。打开时定位到当前公司，便于逐家查看同行业公司。
- 未生成数据包的公司仍可选择，页面说明“尚未生成分析数据包”，不显示空图表。静态服务器对缺失文件返回 SPA 页面（200 text/html），`loadBundle` 会识别这种情况并报告缺包，避免显示 JSON 解析错误。

## Verification (2026-11-19)

- Pipeline tests 56/56 (export bundle test incl. NaN→null, annual filter,
  loud failure on incomplete pipeline).
- `npm run build` clean (tsc strict + vite, 1.19 MB js — full echarts
  import; tree-shaking deferred). Preview smoke test: index 200, bundle
  fetch parses (167 bridge steps, 24 ratio rows).

## Open issues

- ECharts imported whole (~390 KB gzip) — switch to modular imports when
  chart set stabilizes.
- Company picker lists all 5,580 listed companies, but only 600519.SH has an
  analysis bundle; other companies need Modules 2–12 run (and validated) first.
- Charts verified by build + data smoke test; interactive visual pass happens
  with Module 8 (Economics Map) work in the browser.
