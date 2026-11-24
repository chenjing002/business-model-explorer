# GitHub Pages publication

Publishes the static website — the built app plus the exported company
bundles — never the DuckDB store, raw data or `.env`.

- App: https://chenjing002.github.io/business-model-explorer/
- Source: `main` of https://github.com/chenjing002/business-model-explorer

## Why two Pages sites

A Pages site is capped at 1 GB; the 5,479 exported bundles are ~1.8 GB. The
published site is split by exchange across two project sites of the same
owner, which share the origin `chenjing002.github.io`, so every fetch stays
same-origin (no CORS):

| Pages site (repo, `gh-pages` branch) | Contents |
|---|---|
| `business-model-explorer` | app, `data/companies.json`, knowledge PDF, SH + BJ bundles |
| `business-model-explorer-data` | SZ bundles |

Published bundles keep every value. Only `calculation_details` is stored
code-major with the fields identical across years kept once per code
(`format: "by_code_v1"`), which halves the gzip size (~0.86 GB in total,
~0.4–0.5 GB per site). `pipeline/pages.py` checks that each bundle expands
back exactly before writing it; the app expands it on load
(`expandCalculationDetails`, `app/src/calculationDetails.ts`). The shared
fixture `tests/fixtures/calculation_details_compact.json` pins the format for
both languages. Local bundles in `app/public/data/` stay in the exported form.

## Commands

```
.venv/bin/python -m pipeline.cli pages             # build + stage + verify into build/pages/
.venv/bin/python -m pipeline.cli pages --publish   # … then force-push both gh-pages branches
```

`--publish` creates a missing repo, force-pushes each staged site as one
orphan commit (old bundles do not pile up in history) and enables Pages on
`gh-pages` the first time. Run it after `analyze-all` so the published
bundles and `companies.json` agree. A site over 950 MB stops the run.

## App under a sub-path

`app/src/site.ts` holds the deployment layout, injected at build time
(`BME_SITE` → Vite `define` `__SITE__`; `base` for asset URLs). App code keeps
site paths (`/map?year=2025`); `siteUrl` adds the prefix for anchors and
`pushState`, `appPath` strips it from `location.pathname`, `bundleUrl` picks
the site by exchange suffix. Locally nothing changes (base `/`). Deep links
work through `404.html`, a copy of `index.html` (Pages answers with status 404
but the app renders the route). Pages serves `.json.gz` as
`application/gzip` without `Content-Encoding`; the loader decompresses by
gzip magic bytes.

## Agent 静态数据接口

`pages` 构建会从同一批导出文件自动生成以下入口，不依赖浏览器、JavaScript 或 API 密钥：

| 路径（站点根路径下） | 用途 |
| --- | --- |
| `llms.txt` | 中文 Agent 导航与读取规则 |
| `data.html` | 无需 JavaScript 的数据入口页 |
| `api/v1/catalog.json` | 接口目录、单位、榜单和数据口径 |
| `api/v1/companies.json` | 公司代码、名称、行业、可用年份、缺失原因和完整直链 |
| `api/v1/rankings/{id}.json` | 单个完整榜单，保留规则、排序、统计窗口、指标和历史趋势 |
| `api/v1/companies/{ts_code}.json` | 单公司全部年度报表指标及分析指标，纯 JSON，无需解压 |

公司 JSON 按原有交易所规则分站存放；必须使用索引的 `history_url`，不要假设都在主站。
例如深圳公司的 URL 位于 `business-model-explorer-data`；索引和榜单在主站。
所有链接为绝对 URL，能直接交给 HTTP 客户端。

公司文件的 `years` 为升序报告期；`metrics[英文标识].values` 与 `years` 一一对应，
同一指标带中文 `label`、`unit`、`formula` 和来源字段。逐年口径变化放在
`metadata_by_year`，优先于该指标的公共元数据。`missing_reasons` 以报告期为键保留
具体缺失原因，未给具体原因时查 `missing_default`；空值、缺字段都不能当零。

`raw:*` 为报表披露科目，中文名称来自既有映射。税后经营收益（OI）是分析重构指标，
不等同于报表“营业利润”。金额单位为 `CNY_yuan`（元）；`pct` 为小数比例（0.15 = 15%），
`pp` 为比例差（0.01 = 1 个百分点）；价格为元/股，股数为股，天数为天，倍数为倍。
年末市值和股数已经换算，禁止再次乘 10000。校验差额保留原始精度。

图表桥接、情景网格和完整审计追溯仍在 `bundle_url` 指向的 gzip 包。
纯 JSON 不复制图表专用重复项；`source_url` 指向同一个 gzip 包，含公告日、行哈希等来源信息。
其中 `calculation_details` 为 `by_code_v1`：每项通过 `{**shared[code], **values[code][year]}` 恢复。

```python
import json
from urllib.request import urlopen

base = "https://chenjing002.github.io/business-model-explorer/"
def get(url):
    with urlopen(url, timeout=30) as response:
        return json.load(response)

catalog = get(base + "api/v1/catalog.json")
ranking = get(next(r["url"] for r in catalog["rankings"] if r["id"] == "high_roe"))
print(ranking["criteria"], ranking["rows"][:10])
companies = get(catalog["companies_url"])["companies"]
company = next(c for c in companies if c["ts_code"] == "600519.SH")
history = get(company["history_url"])
metric = history["metrics"]["raw:revenue"]
print(metric["label"], metric["unit"])
print(dict(zip(history["years"], metric["values"])))
```

这是静态文件接口，无服务端查询参数。榜单 `rank` 为从 1 开始的展示顺序，未重新计算排名。
数据日期分别保留 `exported_at`、`fiscal_year`、`window` 和报告期；不能将年末行情与
后来发布的年报直接用于无前视偏差的回测。发布命令和 950 MB 分站容量检查保持不变，
新增 JSON 同样计入容量；源码中不提交生成物。
