"""Annual comparisons and optional, traceable company disclosures for the overview."""
from __future__ import annotations

from decimal import Decimal
from math import isfinite
from urllib.parse import urlparse

import yaml

from .config import PROJECT_ROOT


def _value(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) else None


def _sub(current, prior):
    return float(Decimal(str(current)) - Decimal(str(prior))) if current is not None and prior is not None else None


def _divide(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator is not None and denominator > 0 else None


def _average(opening, closing):
    return (opening + closing) / 2 if opening is not None and closing is not None else None


def _annual_by_date(rows, **criteria):
    return {row["end_date"]: row for row in rows if row["end_date"].endswith("1231")
            and all(row.get(key) == value for key, value in criteria.items())}


def _disclosure(annual):
    if annual.get("unit") != "CNY_yuan":
        raise ValueError("总览附注金额单位必须为 CNY_yuan")
    report_url = annual["report_url"]
    url = urlparse(report_url)
    if url.scheme != "https" or not url.hostname or url.fragment:
        raise ValueError("总览附注的 report_url 必须为无页码片段的 HTTPS 地址")

    def section(key, fields=()):
        data = annual.get(key)
        if data is None:
            return None
        page = data["page"]
        if type(page) is not int or page < 1:
            raise ValueError(f"{key} 必须注明有效的年报页码")
        result = {"source": f"{report_url}#page={page}", "page": page}
        if fields:
            result["rows"] = [{"label": row["label"], **{field: amount(row, field) for field in fields}}
                              for row in data["rows"]]
        elif key == "cash_explanation":
            result["text"] = data["text"]
        else:
            result["value"] = amount(data, "value")
        return result

    def amount(row, key):
        value = row.get(key)
        if value is not None and _value(value) is None:
            raise ValueError(f"总览附注的 {key} 必须为有限数字或空值")
        return value

    inventory = section("inventory", ("begin", "end"))
    if inventory:
        for row in inventory["rows"]:
            row["delta"] = _sub(row["end"], row["begin"])
    return {
        "report_url": report_url,
        "products": section("products", ("revenue", "gross_margin")),
        "inventory": inventory,
        "cash_explanation": section("cash_explanation"),
        "shareholder_distribution": section("shareholder_distribution"),
        "share_repurchase": section("share_repurchase"),
    }


def _history_metrics(income, cash, market, balance, prior_balance, raw, prior_raw):
    net_income = _value(income.get("ni_total"))
    revenue = _value(income.get("total_revenue"))
    assets = _average(_value(prior_balance.get("total_assets_reported")),
                      _value(balance.get("total_assets_reported")))
    equity = _average(_value(prior_raw.get("raw:total_equity", {}).get("value")),
                      _value(raw.get("raw:total_equity", {}).get("value")))
    fcf = _value(cash.get("fcf_simple"))
    shares = _value(market.get("shares"))
    assets_missing = "缺少期初或期末资产总计" if assets is None else "平均总资产非正值"
    equity_missing = "缺少期初或期末股东权益合计" if equity is None else "平均股东权益非正值"

    return {
        "avg_assets": (assets, "平均总资产", "（期初资产总计 ＋ 期末资产总计）÷ 2",
                       "@raw:total_assets raw:total_assets", "CNY_yuan", assets_missing),
        "avg_equity": (equity, "平均股东权益（含少数股东）", "（期初股东权益合计 ＋ 期末股东权益合计）÷ 2",
                       "@raw:total_equity raw:total_equity", "CNY_yuan", equity_missing),
        "net_margin": (_divide(net_income, revenue), "销售净利率", "合并净利润 ÷ 营业总收入",
                       "raw:net_income_total raw:total_revenue", "pct",
                       "缺少合并净利润" if net_income is None else "营业总收入缺失或非正值"),
        "asset_turnover": (_divide(revenue, assets), "总资产周转率", "营业总收入 ÷ 平均总资产",
                           "raw:total_revenue overview:avg_assets", "x",
                           "缺少营业总收入" if revenue is None else assets_missing),
        "equity_multiplier": (_divide(assets, equity) if assets is not None and assets > 0 else None,
                              "权益乘数（财务杠杆）", "平均总资产 ÷ 平均股东权益",
                              "overview:avg_assets overview:avg_equity", "x",
                              assets_missing if assets is None or assets <= 0 else equity_missing),
        "roe": (_divide(net_income, equity), "合并净资产收益率（ROE）", "合并净利润 ÷ 平均股东权益",
                "raw:net_income_total overview:avg_equity", "pct",
                "缺少合并净利润" if net_income is None else equity_missing),
        "fcf_per_share": (_divide(fcf, shares), "每股自由现金流", "简式自由现金流 ÷ 年末总股本",
                          "fcf_simple shares", "price",
                          "缺少经营现金流量净额或现金资本开支" if fcf is None else "年末总股本缺失或非正值"),
    }


def build_overview(bundle, companies=None):
    if companies is None:
        path = PROJECT_ROOT / "config" / "overview_disclosures.yml"
        with path.open(encoding="utf-8") as f:
            companies = yaml.safe_load(f) or {}
    company = companies.get(bundle["ts_code"], {})
    disclosures = company.get("annual", {})
    bs = _annual_by_date(bundle["reformulated_bs"])
    income = _annual_by_date(bundle["reformulated_is"], period_kind="cumulative")
    ratios = _annual_by_date(bundle["ratios"], basis="average")
    cash = _annual_by_date(bundle["cash_summary"])
    market = _annual_by_date(bundle.get("market_snapshot", []))
    audit = bundle.get("calculation_details", {})
    rows = []

    for date, balance in sorted(bs.items()):
        prior = f"{int(date[:4]) - 1}1231"
        raw = audit.get(date, {})
        sales = _value(income.get(date, {}).get("revenue"))
        prior_sales = _value(income.get(prior, {}).get("revenue"))
        cfo = _value(cash.get(date, {}).get("cfo"))
        prior_cfo = _value(cash.get(prior, {}).get("cfo"))
        paid = _value(raw.get("raw:cash_paid_for_investments", {}).get("value"))
        recovered = _value(raw.get("raw:cash_from_investment_disposals", {}).get("value"))
        total_assets = _value(balance.get("total_assets_reported"))
        numbers = {
            "revenue_yoy": (_divide(_sub(sales, prior_sales), prior_sales), "营业收入同比", "（本年营业收入 − 上年营业收入）÷ 上年营业收入", "raw:revenue @raw:revenue", "pct", "上年营业收入缺失或非正值，或本年营业收入未披露"),
            "cfo_yoy": (_divide(_sub(cfo, prior_cfo), prior_cfo), "经营现金流量净额同比", "（本年经营现金流量净额 − 上年经营现金流量净额）÷ 上年经营现金流量净额", "raw:cfo @raw:cfo", "pct", "上年经营现金流量净额缺失或非正值，或本年未披露"),
            "rnoa_change": (_sub(_value(ratios.get(date, {}).get("rnoa")), _value(ratios.get(prior, {}).get("rnoa"))), "净经营资产收益率变动", "本年净经营资产收益率 − 上年净经营资产收益率", "rnoa @rnoa", "pp", "缺少本年或上年的净经营资产收益率"),
            "oa_share": (_divide(_value(balance.get("oa")), total_assets), "经营资产占比", "经营资产 ÷ 总资产", "oa raw:total_assets", "pct", "经营资产缺失或总资产缺失、非正值"),
            "fa_share": (_divide(_value(balance.get("fa")), total_assets), "金融资产占比", "金融资产 ÷ 总资产", "fa raw:total_assets", "pct", "金融资产缺失或总资产缺失、非正值"),
            "investment_net_outflow": (_sub(paid, recovered), "投资收付净流出", "投资支付的现金 − 收回投资收到的现金", "raw:cash_paid_for_investments raw:cash_from_investment_disposals", "CNY_yuan", "缺少投资支付或收回投资的现金披露"),
        }
        history = _history_metrics(income.get(date, {}), cash.get(date, {}), market.get(date, {}),
                                   balance, bs.get(prior, {}), raw, audit.get(prior, {}))
        if date in audit:
            for key, (value, label, formula, inputs, unit, reason) in (numbers | history).items():
                raw[f"overview:{key}"] = {"label": label, "value": value, "formula": formula,
                                          "inputs": inputs.split(), "unit": unit,
                                          **({"reason": reason} if value is None else {})}
        rows.append({"end_date": date, **{key: detail[0] for key, detail in numbers.items()},
                     "history": {key: detail[0] for key, detail in history.items()},
                     "disclosure": _disclosure(disclosures[date]) if date in disclosures else None})
    return {"company_name": company.get("name"), "years": rows}
