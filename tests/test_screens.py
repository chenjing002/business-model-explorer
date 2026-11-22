"""Offline tests for the cross-company screens (Module 17)."""
import json

import pandas as pd

from pipeline.screens import compute_screens, latest_fiscal_year

YEARS = ["2021", "2022", "2023", "2024", "2025"]
GOOD = dict(total_revenue=[2e9, 2.2e9, 2.5e9, 2.8e9, 3e9], fcf_simple=[10, 12, 13, 15, 20],
            cfo=[14, 16, 17, 19, 25], ni_total=[8, 8, 8, 8, 8], roce_parent=[.2] * 5, rnoa=[.3] * 5,
            noa_capital=[50] * 5, opm=[.1] * 5, ato=[3.0] * 5, ccc=[-10.0] * 5,
            ccc_net_advances=[-30.0] * 5, market_cap=[None, None, None, None, 9e10])


def company(code, **overrides):
    values = {**GOOD, **overrides}
    return [dict(ts_code=code, year=year, **{k: v[i] for k, v in values.items()})
            for i, year in enumerate(YEARS)]


def build(rows_by_company, flagged=()):
    panel = pd.DataFrame([row for rows in rows_by_company for row in rows])
    codes = sorted(panel.ts_code.unique())
    meta = pd.DataFrame({"ts_code": codes, "check_failures": ["R1" if c in flagged else None for c in codes],
                         "name": [f"公司{c[:1]}" for c in codes], "industry": "测试"})
    return panel, meta


def lists(result):
    return {item["id"]: [row["ts_code"] for row in item["rows"]] for item in result["lists"]}


def test_universe_filters_are_counted_never_silent():
    rows = [company("A.SH"), company("C.SH"),
            company("D.SZ", total_revenue=[5e8] * 5),                   # below the 10 亿元 floor
            company("E.SZ", total_revenue=[None, 2e9, 2e9, 2e9, 2e9])]  # a missing year
    result = compute_screens(*build(rows, flagged={"C.SH"}))
    u = result["universe"]
    assert (u["analyzed_ok"], u["excluded_check_failures"], u["excluded_incomplete_years"],
            u["excluded_below_revenue_floor"], u["ranked"]) == (4, 1, 1, 1, 1)
    assert all("C.SH" not in codes for codes in lists(result).values())
    assert result["window"] == YEARS and result["fiscal_year"] == "2025"


def test_low_base_year_does_not_dominate_fcf_growth():
    rows = [company("S.SH", fcf_simple=[10, 12, 14, 16, 18]),       # steady
            company("Z.SH", fcf_simple=[0.01, 9, 8.5, 9.5, 10])]    # one near-zero base year
    rows.append(company("D.SH", fcf_simple=[10, 12, 6, 14, 16]))   # 3 rises but a −50% year
    got = lists(compute_screens(*build(rows)))
    assert got["fcf_growth"] == ["S.SH", "Z.SH"]


def test_each_screen_applies_its_own_rule():
    rows = [
        company("A.SH"),                                              # passes everything
        company("B.SH", fcf_simple=[10, 9, 11, 12, 13], roce_parent=[.2, .2, .14, .2, .2]),
        company("F.SZ", noa_capital=[-50] * 5),                       # RNOA on negative NOA
        company("G.SZ", total_revenue=[3e9, 2.8e9, 2.5e9, 2.2e9, 2e9]),  # CCC<0 but shrinking
        company("H.SZ", fcf_simple=[10, -1, 13, 15, 20]),             # one negative FCF year
        company("I.SZ", fcf_simple=[1, 2, 3, 4, 5], ni_total=[8] * 5),  # FCF below profits
    ]
    got = lists(compute_screens(*build(rows)))
    assert got["fcf_growth"] == ["I.SZ", "A.SH", "F.SZ", "G.SZ", "B.SH"]  # by median growth
    assert "H.SZ" not in got["fcf_growth"]
    assert "B.SH" not in got["high_roe"] and "A.SH" in got["high_roe"]
    assert "F.SZ" not in got["high_rnoa"]
    assert "G.SZ" not in got["cash_cycle"]
    assert "I.SZ" not in got["cash_quality"] and "A.SH" in got["cash_quality"]
    assert got["multi"][0] == "A.SH"


def test_values_trend_and_columns_are_json_ready():
    result = compute_screens(*build([company("A.SH")]))
    text = json.dumps(result, ensure_ascii=False, allow_nan=False)  # NaN would raise
    fcf = next(item for item in result["lists"] if item["id"] == "fcf_growth")
    row = fcf["rows"][0]
    assert row["trend"] == [10, 12, 13, 15, 20]
    # year-on-year 20%, 8.3%, 15.4%, 33.3% → median = mean of 15.4% and 20%
    assert abs(row["values"]["fcf_growth"] - (15 / 13 - 1 + 12 / 10 - 1) / 2) < 1e-12
    assert row["values"]["up_years"] == 4
    assert row["values"]["market_cap"] == 9e10
    assert {c["unit"] for item in result["lists"] for c in item["columns"]} <= {
        "CNY_yuan", "pct", "days", "count", "x", "text"}
    multi = result["lists"][0]
    assert multi["id"] == "multi" and multi["rows"][0]["values"]["hits"] == 5
    assert "自由现金流持续增长" in multi["rows"][0]["values"]["lists"]
    assert "NaN" not in text


def test_latest_fiscal_year_waits_for_coverage():
    panel, _ = build([company("A.SH"), company("B.SH"), company("C.SH")])
    early = pd.DataFrame([dict(ts_code="A.SH", year="2026", total_revenue=1e9)])
    assert latest_fiscal_year(pd.concat([panel, early], ignore_index=True)) == "2025"


SAMPLE = "fixtures/screens_sample.json"


def sample_payload():
    rows = [company("T00001.SH"), company("T00002.SZ", fcf_simple=[10, 9, 11, 12, 13], ccc=[-5, 3, -2, -4, -6]),
            company("T00003.SZ", roce_parent=[.25, .3, .28, .22, .24], market_cap=[None] * 5),
            company("T00004.SH", total_revenue=[5e8] * 5)]
    panel, meta = build(rows)
    meta["name"] = meta.ts_code.map({"T00001.SH": "示例甲", "T00002.SZ": "示例乙",
                                     "T00003.SZ": "示例丙", "T00004.SH": "示例丁"})
    return compute_screens(panel, meta)


def test_sample_fixture_is_current():
    # app/tests/screens.test.mjs renders this file; regenerate it with
    # `.venv/bin/python -c "from tests.test_screens import write_sample; write_sample()"`.
    from pathlib import Path
    pinned = json.loads((Path(__file__).parent / SAMPLE).read_text(encoding="utf-8"))
    assert json.loads(json.dumps(sample_payload(), ensure_ascii=False)) == pinned


def write_sample():
    from pathlib import Path
    (Path(__file__).parent / SAMPLE).write_text(
        json.dumps(sample_payload(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
