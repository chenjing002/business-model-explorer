"""Module 17 — 好生意榜单: cross-company screens over the analysed universe.

Reads the annual tables written by Modules 4–12 for every company whose
latest batch run succeeded and ranks them on five-year records: growing free
cash flow, high and stable ROE, high RNOA, a cash-generative operating cycle
(CCC < 0) and cash-backed profits, plus the companies that pass several of
them. The output is one static file, `app/public/data/screens.json`; the
frontend renders it without computing anything.

Screens are descriptive filters on reported history, not forecasts or
recommendations. Every threshold is stated in the file next to the list.

Universe (each step counted in the output, never silent):
- latest `analysis_log` status ok (general-business statements only);
- no failed identity-check family — reconciliation gaps make a ranking
  unreliable, so those companies are listed nowhere;
- annual 营业总收入 disclosed for every year of the window;
- latest-year 营业总收入 ≥ REVENUE_FLOOR, so tiny denominators do not
  dominate ratio rankings.
A metric missing in any window year drops the company from that list only.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .export import SCHEMA_VERSION, _table_exists, _write_json
from .store import Store

SCREENS_FILE = "screens.json"
WINDOW_YEARS = 5
REVENUE_FLOOR = 1e9          # 营业总收入 ≥ 10 亿元（人民币元）
FCF_MIN_UP_YEARS = 3         # of the 4 year-on-year steps
FCF_MAX_DROP = -0.20         # no single year-on-year decline worse than this
ROE_FLOOR = 0.15
RNOA_FLOOR = 0.20
FCF_TO_NI_FLOOR = 1.0
MULTI_MIN_LISTS = 3
# A fiscal year counts as published once this share of the previous year's
# companies have reported it.
YEAR_COVERAGE = 0.8

PANEL_COLUMNS = ["total_revenue", "fcf_simple", "cfo", "ni_total", "roce_parent", "rnoa",
                 "noa_capital", "opm", "ato", "ccc", "ccc_net_advances", "market_cap"]


def load_panel(store: Store) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(panel: one row per ts_code × fiscal year, meta: one row per ok company)."""
    con = store.con
    latest = con.execute(
        "SELECT ts_code, status, check_failures FROM analysis_log "
        "QUALIFY row_number() OVER (PARTITION BY ts_code ORDER BY finished_at DESC) = 1").df()
    meta = latest[latest.status == "ok"][["ts_code", "check_failures"]].reset_index(drop=True)
    if _table_exists(store, "raw_stock_basic"):
        names = con.execute(
            "SELECT ts_code, name, industry FROM raw_stock_basic "
            "QUALIFY row_number() OVER (PARTITION BY ts_code ORDER BY _fetched_at DESC) = 1").df()
        meta = meta.merge(names, on="ts_code", how="left")
    else:
        meta = meta.assign(name=None, industry=None)

    annual = "end_date LIKE '%1231'"
    frames = [
        con.execute("SELECT ts_code, end_date, total_revenue FROM reformulated_is "
                    f"WHERE period_kind = 'cumulative' AND {annual}").df(),
        con.execute("SELECT ts_code, end_date, fcf_simple, cfo, ni_total FROM cash_summary_annual "
                    f"WHERE {annual}").df(),
        con.execute("SELECT ts_code, end_date, roce_parent, rnoa, noa_capital, opm, ato FROM ratios_annual "
                    f"WHERE basis = 'average' AND {annual}").df(),
        con.execute("SELECT ts_code, end_date, ccc, ccc_net_advances FROM working_capital_annual "
                    f"WHERE {annual}").df(),
    ]
    if _table_exists(store, "market_snapshot_annual"):
        frames.append(con.execute("SELECT ts_code, end_date, market_cap FROM market_snapshot_annual "
                                  f"WHERE {annual}").df())
    panel = frames[0]
    for frame in frames[1:]:
        if frame.duplicated(["ts_code", "end_date"]).any():
            raise ValueError("annual table has duplicate company-years")
        panel = panel.merge(frame, on=["ts_code", "end_date"], how="left")
    panel = panel[panel.ts_code.isin(meta.ts_code)]
    panel = panel.assign(year=panel.end_date.str[:4]).reindex(columns=["ts_code", "year", *PANEL_COLUMNS])
    return panel, meta


def latest_fiscal_year(panel: pd.DataFrame) -> str:
    counts = panel.dropna(subset=["total_revenue"]).groupby("year").ts_code.nunique().sort_index()
    published = [y for y, n in counts.items()
                 if str(int(y) - 1) not in counts or n >= YEAR_COVERAGE * counts[str(int(y) - 1)]]
    return published[-1]


def _num(value):
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def compute_screens(panel: pd.DataFrame, meta: pd.DataFrame, fiscal_year: str | None = None,
                    revenue_floor: float = REVENUE_FLOOR) -> dict:
    """Pure: the screens.json payload (without timestamps) from panel + meta."""
    fiscal_year = fiscal_year or latest_fiscal_year(panel)
    window = [str(int(fiscal_year) - k) for k in range(WINDOW_YEARS - 1, -1, -1)]
    first, last = window[0], window[-1]

    flagged = set(meta.ts_code[meta.check_failures.fillna("").astype(str).str.len() > 0])
    clean = meta[~meta.ts_code.isin(flagged)].sort_values("ts_code")

    def wide(metric: str) -> pd.DataFrame:
        table = panel.pivot(index="ts_code", columns="year", values=metric)
        return table.reindex(index=clean.ts_code, columns=window).astype(float)

    revenue = wide("total_revenue")
    complete = revenue.notna().all(axis=1)
    large = complete & (revenue[last] >= revenue_floor)
    universe = list(revenue.index[large])
    W = {m: wide(m).loc[universe] for m in PANEL_COLUMNS}

    def all_years(frame: pd.DataFrame, test) -> pd.Series:
        return frame.notna().all(axis=1) & test(frame).all(axis=1)

    def cagr(frame: pd.DataFrame) -> pd.Series:
        ratio = frame[last] / frame[first]
        return ratio.where(ratio > 0) ** (1 / (WINDOW_YEARS - 1)) - 1

    def yoy_growth(frame: pd.DataFrame) -> pd.DataFrame:
        prev = frame[window[:-1]].where(frame[window[:-1]] > 0).to_numpy()
        return pd.DataFrame(frame[window[1:]].to_numpy() / prev - 1, index=frame.index)

    lists = []

    # 1. Free cash flow: positive every year and trending up.
    # Median year-on-year growth ranks: one near-zero base year cannot dominate.
    fcf = W["fcf_simple"]
    yoy = yoy_growth(fcf)
    ups = (yoy > 0).sum(axis=1)
    keep = (all_years(fcf, lambda f: f > 0) & (ups >= FCF_MIN_UP_YEARS)
            & (yoy.min(axis=1) >= FCF_MAX_DROP) & (fcf[last] > fcf[first]))
    growth = yoy.median(axis=1, skipna=False)
    lists.append(_list(
        "fcf_growth", "自由现金流持续增长",
        "近五年自由现金流每年为正、多数年份增长且没有大幅回落。",
        [f"{first}–{last} 年简式自由现金流（经营活动现金流量净额 − 现金资本开支）每年为正",
         f"4 个同比中至少 {FCF_MIN_UP_YEARS} 个增长，任一年降幅不超过 {-FCF_MAX_DROP:.0%}，且 {last} 年高于 {first} 年",
         "排名用 4 个同比增长率的中位数，避免单一年份的低基数主导排名",
         "按公司整体金额计算，不按每股：A 股送转股会使未复权的每股数据失真"],
        "按同比增长率中位数从高到低",
        ["fcf", "cfo", "capex"],
        columns=[("fcf_last", f"{last} 年自由现金流", "CNY_yuan"),
                 ("fcf_growth", "同比增长率中位数", "pct"),
                 ("up_years", "同比增长年数", "count"), ("market_cap", f"{last} 年末总市值", "CNY_yuan")],
        values={"fcf_last": fcf[last], "fcf_growth": growth, "up_years": ups, "market_cap": W["market_cap"][last]},
        trend=("自由现金流", "CNY_yuan", fcf), keep=keep, order=growth, ascending=False,
        meta=clean, window=window))

    # 2. ROE: high every year (归母口径).
    roe = W["roce_parent"]
    keep = all_years(roe, lambda r: r >= ROE_FLOOR)
    lists.append(_list(
        "high_roe", "高且稳定的净资产收益率",
        f"近五年归母净资产收益率每年不低于 {ROE_FLOOR:.0%}。",
        [f"{first}–{last} 年归母净资产收益率（归母净利润 ÷ 平均归母权益）每年 ≥ {ROE_FLOOR:.0%}",
         "平均归母权益为正；ROE 含财务杠杆的作用，可对照经营资产回报榜单"],
        "按五年平均值从高到低",
        ["roce", "rotce", "flev"],
        columns=[("roe_avg", "五年平均", "pct"), ("roe_min", "五年最低", "pct"),
                 ("roe_last", f"{last} 年", "pct"), ("market_cap", f"{last} 年末总市值", "CNY_yuan")],
        values={"roe_avg": roe.mean(axis=1), "roe_min": roe.min(axis=1), "roe_last": roe[last],
                "market_cap": W["market_cap"][last]},
        trend=("归母净资产收益率", "pct", roe), keep=keep, order=roe.mean(axis=1), ascending=False,
        meta=clean, window=window))

    # 3. RNOA: operating assets earn a high return every year.
    rnoa = W["rnoa"]
    keep = all_years(rnoa, lambda r: r >= RNOA_FLOOR) & all_years(W["noa_capital"], lambda n: n > 0)
    median = rnoa.median(axis=1)
    lists.append(_list(
        "high_rnoa", "经营资产回报高",
        f"近五年净经营资产收益率每年不低于 {RNOA_FLOOR:.0%}（Penman 口径，剔除金融资产与负债）。",
        [f"{first}–{last} 年净经营资产收益率（税后经营收益 ÷ 平均净经营资产）每年 ≥ {RNOA_FLOOR:.0%}",
         "平均净经营资产每年为正；净经营资产很小的公司比率会很高，宜结合利润率与周转率阅读"],
        "按五年中位数从高到低",
        ["rnoa", "opm", "ato"],
        columns=[("rnoa_median", "五年中位数", "pct"), ("rnoa_last", f"{last} 年", "pct"),
                 ("opm_last", f"{last} 年税后经营利润率", "pct"), ("ato_last", f"{last} 年周转率", "x")],
        values={"rnoa_median": median, "rnoa_last": rnoa[last], "opm_last": W["opm"][last],
                "ato_last": W["ato"][last]},
        trend=("净经营资产收益率", "pct", rnoa), keep=keep, order=median, ascending=False,
        meta=clean, window=window))

    # 4. Cash-generative operating cycle with growing sales.
    ccc = W["ccc"]
    keep = all_years(ccc, lambda c: c < 0) & (revenue.loc[universe, last] > revenue.loc[universe, first])
    lists.append(_list(
        "cash_cycle", "先收款后付款",
        "近五年现金循环周期每年为负，同时营业总收入增长。",
        [f"{first}–{last} 年现金循环周期（存货天数 ＋ 应收天数 − 应付天数）每年 < 0",
         f"{last} 年营业总收入高于 {first} 年",
         "客户预收款不计入现金循环周期，另列扣除预收款后的天数",
         "应付账款可能含工程及设备款；营业成本很低的公司应付天数偏大，天数宜与同业比较，故不按天数排名"],
        f"按 {last} 年营业总收入从高到低",
        ["ccc", "dio", "dso", "dpo", "advances"],
        columns=[("revenue_last", f"{last} 年营业总收入", "CNY_yuan"), ("ccc_last", f"{last} 年", "days"),
                 ("ccc_net_last", f"{last} 年扣除客户预收款后", "days"),
                 ("revenue_cagr", "营业总收入 4 年复合增长率", "pct")],
        values={"revenue_last": revenue.loc[universe, last], "ccc_last": ccc[last],
                "ccc_net_last": W["ccc_net_advances"][last], "revenue_cagr": cagr(revenue.loc[universe])},
        trend=("现金循环周期", "days", ccc), keep=keep, order=revenue.loc[universe, last], ascending=False,
        meta=clean, window=window))

    # 5. Profits backed by free cash flow.
    ni, cfo = W["ni_total"], W["cfo"]
    fcf_sum, ni_sum = fcf.sum(axis=1, min_count=WINDOW_YEARS), ni.sum(axis=1, min_count=WINDOW_YEARS)
    fcf_to_ni = fcf_sum / ni_sum.where(ni_sum > 0)
    keep = all_years(ni, lambda n: n > 0) & fcf.notna().all(axis=1) & (fcf_to_ni >= FCF_TO_NI_FLOOR)
    lists.append(_list(
        "cash_quality", "利润含金量高",
        "近五年净利润每年为正，且五年累计自由现金流不少于累计净利润。",
        [f"{first}–{last} 年合并净利润每年为正",
         f"五年累计自由现金流 ÷ 五年累计合并净利润 ≥ {FCF_TO_NI_FLOOR:.0%}",
         "折旧摊销大、资本开支少的公司比率偏高；比率高不代表利润在增长"],
        "按五年累计自由现金流从高到低",
        ["fcf", "cfo"],
        columns=[("fcf_sum", "五年累计自由现金流", "CNY_yuan"), ("fcf_to_ni", "累计自由现金流 ÷ 累计净利润", "pct"),
                 ("cfo_to_ni", "累计经营现金流 ÷ 累计净利润", "pct"), ("market_cap", f"{last} 年末总市值", "CNY_yuan")],
        values={"fcf_sum": fcf_sum, "fcf_to_ni": fcf_to_ni,
                "cfo_to_ni": cfo.sum(axis=1, min_count=WINDOW_YEARS) / ni_sum.where(ni_sum > 0),
                "market_cap": W["market_cap"][last]},
        trend=("自由现金流", "CNY_yuan", fcf), keep=keep, order=fcf_sum, ascending=False,
        meta=clean, window=window))

    # 6. Companies on several of the lists above.
    member = pd.DataFrame({item["id"]: pd.Series(1, index=[r["ts_code"] for r in item["rows"]], dtype=float)
                           for item in lists}).reindex(universe).notna()
    hits = member.sum(axis=1)
    keep = hits >= MULTI_MIN_LISTS
    titles = {item["id"]: item["title"] for item in lists}
    names = member.apply(lambda row: "、".join(titles[k] for k in member.columns if row[k]), axis=1)
    order = pd.DataFrame({"hits": hits, "roe": roe.mean(axis=1)})  # count first, then ROE
    multi = _list(
        "multi", "多项入选",
        f"同时进入下列五个榜单中至少 {MULTI_MIN_LISTS} 个的公司。",
        [f"入选榜单数 ≥ {MULTI_MIN_LISTS}（共 5 个）", "同数时按五年平均归母净资产收益率排序"],
        "按入选榜单数从多到少",
        ["fcf", "roce", "rnoa", "ccc"],
        columns=[("hits", "入选榜单数", "count"), ("lists", "入选榜单", "text"),
                 ("roe_avg", "五年平均归母 ROE", "pct"), ("market_cap", f"{last} 年末总市值", "CNY_yuan")],
        values={"hits": hits, "lists": names, "roe_avg": roe.mean(axis=1), "market_cap": W["market_cap"][last]},
        trend=("归母净资产收益率", "pct", roe), keep=keep, order=order, ascending=False,
        meta=clean, window=window)

    return {
        "schema_version": SCHEMA_VERSION,
        "unit": "CNY_yuan",
        "fiscal_year": fiscal_year,
        "window": window,
        "universe": {
            "analyzed_ok": int(len(meta)),
            "excluded_check_failures": int(len(flagged & set(meta.ts_code))),
            "excluded_incomplete_years": int((~complete).sum()),
            "excluded_below_revenue_floor": int((complete & ~large).sum()),
            "revenue_floor": revenue_floor,
            "ranked": len(universe),
        },
        "lists": [multi, *lists],
    }


def _list(list_id, title, summary, criteria, sort, concepts, *, columns, values, trend,
          keep, order, ascending, meta, window) -> dict:
    keep = keep.fillna(False).astype(bool)
    selected = order.loc[keep[keep].index]
    # Ties keep ts_code order; a DataFrame order sorts by its columns in turn.
    codes = list((selected.sort_values(by=list(selected.columns), ascending=ascending, kind="stable")
                  if isinstance(selected, pd.DataFrame)
                  else selected.sort_values(ascending=ascending, kind="stable")).index)
    info = meta.set_index("ts_code")
    label, unit, series = trend
    rows = []
    for code in codes:
        row_values = {}
        for key, _, col_unit in columns:
            value = values[key].get(code)
            row_values[key] = (None if value is None or (isinstance(value, float) and np.isnan(value))
                               else value if col_unit == "text"
                               else int(value) if col_unit == "count" else _num(value))
        rows.append({"ts_code": code, "name": _text(info.at[code, "name"]) if "name" in info else None,
                     "industry": _text(info.at[code, "industry"]) if "industry" in info else None,
                     "values": row_values,
                     "trend": [_num(series.at[code, y]) for y in window]})
    return {"id": list_id, "title": title, "summary": summary, "criteria": criteria, "sort": sort,
            "concepts": concepts,
            "columns": [{"key": key, "label": col_label, "unit": col_unit} for key, col_label, col_unit in columns],
            "trend": {"label": label, "unit": unit},
            "count": len(rows), "rows": rows}


def _text(value):
    return None if value is None or (isinstance(value, float) and np.isnan(value)) else str(value)


def export_screens(store: Store, out_dir: Path | str) -> Path:
    panel, meta = load_panel(store)
    payload = compute_screens(panel, meta)
    payload["exported_at"] = datetime.now(timezone.utc).isoformat()
    out = Path(out_dir) / SCREENS_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_json(payload, out)
    return out


def summarize(path: Path) -> str:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    u = data["universe"]
    lines = [f"Screens {data['window'][0]}–{data['fiscal_year']}: {u['ranked']:,} ranked of "
             f"{u['analyzed_ok']:,} ok (−{u['excluded_check_failures']} check failures, "
             f"−{u['excluded_incomplete_years']} incomplete years, "
             f"−{u['excluded_below_revenue_floor']} below revenue floor)"]
    for item in data["lists"]:
        top = "、".join(f"{r['name'] or r['ts_code']}" for r in item["rows"][:5])
        lines.append(f"  {item['title']}: {item['count']} · {top}")
    return "\n".join(lines)
