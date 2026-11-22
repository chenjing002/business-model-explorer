# Module 17 — 好生意榜单 (cross-company screens, home page)

The site's home page (`/`) ranks the analysed universe on five-year records.
The company overview moved to `/overview`; the site nav reads
好生意榜单 · 公司分析 · 财务知识库 · 参考案例.

Screens describe reported history only — no forecast, no valuation, no
recommendation. All values and rankings are computed in Python; the frontend
renders `data/screens.json` as is.

## Files

```
pipeline/screens.py     load_panel (DuckDB annual tables) → compute_screens (pure) → screens.json
pipeline/bulk_analyze.py  analyze-all writes screens.json after the company index
pipeline/cli.py         `screens` command (prints the universe counts and each list's top 5)
app/src/screens.ts      types, loader, unit formatting
app/src/ScreensView.tsx list cards + ranked table + sparkline (shape only, row min–max)
tests/test_screens.py   rules, universe counts, JSON safety; pins tests/fixtures/screens_sample.json
app/tests/screens.test.mjs  renders the pinned sample (synthetic companies, not real data)
```

## Universe

Latest `analysis_log` status ok (general-business statements) → minus
companies with any failed identity-check family (a reconciliation gap makes a
ranking unreliable) → annual 营业总收入 for every window year → latest-year
营业总收入 ≥ 10 亿元. Each step's count is in the file and on the page. A
metric missing in any window year drops the company from that list only;
missing values are never treated as zero.

Window: the five fiscal years ending at the latest year that ≥ 80 % of the
previous year's companies have reported.

## Lists

| id | 标题 | Rule (every window year unless noted) | Order |
|---|---|---|---|
| fcf_growth | 自由现金流持续增长 | `fcf_simple` > 0; ≥ 3 of 4 year-on-year increases; no year-on-year fall worse than −20 %; last > first | median year-on-year growth ↓ |
| high_roe | 高且稳定的净资产收益率 | `roce_parent` (归母净利润 ÷ 平均归母权益) ≥ 15 % | 5-year mean ↓ |
| high_rnoa | 经营资产回报高 | `rnoa` ≥ 20 % and average NOA > 0 | 5-year median ↓ |
| cash_cycle | 先收款后付款 | `ccc` < 0; 营业总收入 last > first | latest 营业总收入 ↓ |
| cash_quality | 利润含金量高 | 合并净利润 > 0; Σ FCF ÷ Σ 净利润 ≥ 100 % | Σ FCF ↓ |
| multi | 多项入选 | on ≥ 3 of the five lists | count ↓, then mean ROE ↓ |

FCF growth uses company totals, not per share: A-share bonus issues (送转股)
change share counts without restating history. RNOA can be very large when
NOA is small; the table shows OPM and ATO next to it.

Two rankings were changed after reviewing the first real run (2021–2025):
- FCF growth ranked by 4-year CAGR put near-zero base years on top (安孚科技
  0.0 → 9.2 亿元 = 809 %), and "≥ 3 rises" admitted lumpy series (嘉益股份
  3.0 → 0.4 → 5.5). The −20 % drop limit keeps the trend steady (185 → 65
  companies) and the median year-on-year rate ranks it; one outlier step
  cannot dominate a median.
- CCC ranked by days put software, coal and water companies on top
  (泛微网络 −1,037 天): tiny 营业成本 and construction payables in 应付账款
  inflate DPO. Days are comparable within an industry, not across, so the
  list keeps the CCC < 0 rule but ranks by size (中国石油、中国移动、宁德时代…).

## Output schema (`screens.json`, schema_version 1, unit CNY_yuan)

`fiscal_year`, `window`, `universe` (counts + `revenue_floor` in 元),
`lists[]`: `id`, `title`, `summary`, `criteria[]`, `sort`, `concepts[]`
(knowledge-base ids), `columns[]` (`key`, `label`, `unit` ∈ CNY_yuan / pct /
days / x / count / text), `trend` (`label`, `unit`), `count`, `rows[]`
(`ts_code`, `name`, `industry`, `values{key: value|null}`, `trend[]` one value
per window year).
