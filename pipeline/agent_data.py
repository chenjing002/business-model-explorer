"""Read-only, uncompressed static API built from the same published bundles."""
from __future__ import annotations

import html
import json
from pathlib import Path

API = "api/v1"
UNITS = {
    "CNY_yuan": "人民币元；展示亿元时除以 100000000",
    "pct": "小数比例，0.15 = 15%", "pp": "比例之差，0.01 = 1 个百分点",
    "price": "人民币元/股", "shares": "股", "days": "天", "x": "倍",
    "residual": "人民币元；校验差额，保留极小非零值", "count": "个", "text": "文本",
}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"),
                               allow_nan=False) + "\n", encoding="utf-8")


def history(bundle: dict, source_url: str) -> dict:
    """Annual report fields and analytical metrics, without chart-only duplicates.

    Labels/units/formulas come from the audited export (raw labels ultimately
    come from mapping_tushare.yml), never from inferred English field names.
    """
    if bundle.get("unit") != "CNY_yuan":
        raise ValueError(f"{bundle.get('ts_code')}: expected CNY_yuan")
    details = bundle.get("calculation_details", {})
    fields, rows = {}, []
    for date, metrics in sorted(details.items()):
        values, reasons, metadata = {}, {}, {}
        for code, detail in metrics.items():
            if ":" in code and not code.startswith(("raw:", "overview:")):
                continue
            # Vendor market inputs in 万元/万股 remain in the audit bundle;
            # market_cap/shares already contain the correctly converted values.
            if detail["unit"] not in UNITS:
                if code.startswith("raw:daily_basic."):
                    continue
                raise ValueError(f"{code}: unknown unit {detail['unit']}")
            spec = {k: detail[k] for k in ("label", "unit", "formula", "source", "inputs") if k in detail}
            fields.setdefault(code, spec)
            if fields[code] != spec:
                metadata[code] = spec
            values[code] = detail.get("value")
            if values[code] is None and detail.get("reason"):
                reasons[code] = detail["reason"]
        rows.append({"end_date": date, "values": values, "missing_reasons": reasons,
                     **({"field_overrides": metadata} if metadata else {})})
    series = {}
    for code, spec in fields.items():
        reasons = {r["end_date"]: r["missing_reasons"][code] for r in rows if code in r["missing_reasons"]}
        changes = {r["end_date"]: r["field_overrides"][code] for r in rows if code in r.get("field_overrides", {})}
        series[code] = {**spec, "values": [r["values"].get(code) for r in rows],
                        **({"missing_reasons": reasons} if reasons else {}),
                        **({"metadata_by_year": changes} if changes else {})}
    return {"schema_version": 1, "ts_code": bundle["ts_code"], "unit": "CNY_yuan",
            "exported_at": bundle.get("exported_at"), "source_url": source_url,
            "conventions": bundle.get("conventions", {}),
            "missing_default": "未披露或源数据未提供计算结果；详见原始数据包",
            "years": [r["end_date"] for r in rows], "metrics": series}


def stage_catalog(app: Path, companies: dict, screens: dict, summaries: dict,
                  base_url: str, company_url, bundle_url) -> None:
    """Small discovery files stay on the app site; company files may be sharded."""
    entries = []
    for company in companies["companies"]:
        code = company["ts_code"]
        available = code in summaries
        entries.append({**company, "available": available,
                        "history_url": company_url(code) if available else None,
                        "bundle_url": bundle_url(code) if available else None,
                        "years": summaries.get(code, []),
                        "unavailable": companies.get("unavailable", {}).get(code) if not available else None,
                        "check_failures": companies.get("check_failures", {}).get(code, [])})
    write_json(app / API / "companies.json", {
        "schema_version": 1, "exported_at": companies.get("exported_at"),
        "source": companies.get("source"), "count": len(entries), "companies": entries})
    lists = []
    context = {k: v for k, v in screens.items() if k != "lists"}
    for ranking in screens["lists"]:
        item = {**context, **ranking, "rows": [
            {**row, "rank": rank, "history_url": company_url(row["ts_code"])
             if row["ts_code"] in summaries else None}
            for rank, row in enumerate(ranking["rows"], 1)]}
        write_json(app / API / "rankings" / f"{ranking['id']}.json", item)
        lists.append({k: item[k] for k in ("id", "title", "count", "criteria", "sort")} |
                     {"url": f"{base_url}{API}/rankings/{ranking['id']}.json"})
    write_json(app / API / "catalog.json", {
        "schema_version": 1, "title": "商业模式探索器 · 数据接口", "unit": "CNY_yuan",
        "companies_url": f"{base_url}{API}/companies.json", "rankings": lists,
        "units": UNITS, "ranking_exported_at": screens.get("exported_at"),
        "fiscal_year": screens.get("fiscal_year"), "window": screens.get("window"),
        "history_format": "years 为升序报告期；metrics[英文标识].values 与 years 一一对应；逐年 metadata_by_year 优先；空值查 missing_reasons 或 missing_default",
        "history_scope": "全部年度报表披露字段及非图表专用分析指标。完整桥接、估值网格、审计来源见 bundle_url。",
        "notes": ["税后经营收益（OI）是重构指标，不等同于报表营业利润。",
                  "年末市值已经换算为元，总股本已经换算为股，不得再次倍乘。",
                  "榜单顺序与网页一致；rank 为从 1 开始的展示序号；没有查询参数或在线计算。",
                  "缺失字段与 null 均不表示零；原始数据包保留公告日、行哈希与计算依据。",
                  "年末行情与随后披露的年报组成事后分析锚点，不能直接用作无前视偏差的历史回测。"]})
    links = [("数据目录（先读）", f"{API}/catalog.json"), ("公司索引", f"{API}/companies.json")]
    links += [(r["title"], f"{API}/rankings/{r['id']}.json") for r in lists]
    guide = ("# 商业模式探索器 · Agent 数据入口\n\n"
             "> 无需运行 JavaScript、无需登录。HTTP GET 下列静态 JSON 即可。\n\n" +
             "\n".join(f"- [{label}]({base_url}{url})" for label, url in links) +
             "\n\n先读公司索引，按 ts_code / name / industry 找到公司，再 GET history_url 获取全部可用年度。"
             "history_url 可能位于 business-model-explorer-data；请跟随索引，不要猜分站路径。\n"
             "metrics 的 values 数组与 years 报告期数组一一对应，指标含中文 label、unit 和 formula；metadata_by_year 为当年口径变化。"
             "金额为人民币元，pct 为小数比例（0.15=15%），pp 为比例差（0.01=1个百分点）。"
             "null 不等于零，missing_reasons 保留原因。数据日期以各文件 exported_at / end_date 为准。\n"
             "完整审计数据在 bundle_url：显式 gzip 文件，需解压，calculation_details 为 by_code_v1 格式。"
             "该字段以 shared[code] 与 values[code][year] 合并恢复；years 列出全部报告期。\n")
    (app / "llms.txt").write_text(guide, encoding="utf-8")
    (app / "data.html").write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>数据接口 · 商业模式探索器</title>'
        '<h1>榜单与公司历年数据</h1><p>静态 JSON 接口，无需执行 JavaScript。</p><ul>' +
        ''.join(f'<li><a href="{html.escape(url)}">{html.escape(label)}</a></li>' for label, url in links) +
        '</ul><p>公司索引提供每家公司的历年数据直链。金额为人民币元，空值不等于零。</p>'
        '<a href="llms.txt">Agent 使用说明</a></html>', encoding="utf-8")
