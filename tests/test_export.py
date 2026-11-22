"""Offline test for the JSON export bundle (Module 7)."""
import gzip
import json

import numpy as np
import pandas as pd
import pytest

from pipeline.export import EXPORT_TABLES, SCHEMA_VERSION, export_company
from pipeline.overview import build_overview
from pipeline.store import Store


@pytest.fixture
def seeded_store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    base = dict(ts_code="T", end_date="20231231")
    frames = {
        "reformulated_bs": pd.DataFrame([{**base, "noa": 750.0, "nfo": np.nan}]),
        "reformulated_is": pd.DataFrame([{**base, "period_kind": "cumulative",
                                          "oi_after_tax": 385.0},
                                         {**base, "end_date": "20230630",
                                          "period_kind": "cumulative",
                                          "oi_after_tax": 180.0}]),
        "ratios_annual": pd.DataFrame([{**base, "basis": "average", "rnoa": 0.5}]),
        "working_capital_annual": pd.DataFrame([{**base, "dio": 1300.0}]),
        "cash_bridge_annual": pd.DataFrame([{**base, "step_order": 0,
                                             "concept": "supp_net_profit",
                                             "label": "NI", "value": 400.0,
                                             "step_kind": "start"}]),
        "cash_summary_annual": pd.DataFrame([{**base, "cfo": 500.0}]),
        "reformulated_bs_components": pd.DataFrame([{**base, "concept": "inventory",
                                                     "effective_class": "operating_asset",
                                                     "value": 300.0}]),
        "reclass_decisions": pd.DataFrame([{**base, "kind": "coalesce",
                                            "concept": "x", "choice": "granular_match",
                                            "reason": "r"}]),
        "econ_map_nodes": pd.DataFrame([{**base, "layer": 1,
                                         "layer_name": "Capital sources",
                                         "node_id": "common_equity",
                                         "label": "Common equity", "value": 650.0,
                                         "flow_or_stock": "stock",
                                         "components_json": "[]", "note": "",
                                         "related_json": "[]"}]),
        "econ_map_checks": pd.DataFrame([{**base, "layer": 1,
                                          "check": "L1_sources_vs_total_assets",
                                          "residual": 0.0}]),
        "econ_evolution_groups": pd.DataFrame([{**base, "side": "sources",
                                                "group_id": "common_equity",
                                                "label": "Common equity",
                                                "panel_id": "common_equity",
                                                "begin_value": 560.0,
                                                "end_value": 650.0,
                                                "delta": 90.0,
                                                "delta_share_of_assets": 0.09,
                                                "evo_flags": ""}]),
        "econ_evolution_flows": pd.DataFrame([{**base, "side": "sources",
                                               "panel_id": "common_equity",
                                               "panel_label": "Common equity",
                                               "step_order": 0,
                                               "concept": "opening_balance",
                                               "label": "Opening balance",
                                               "value": 560.0,
                                               "step_kind": "start",
                                               "basis": "balance",
                                               "note": ""}]),
        "econ_evolution_checks": pd.DataFrame([{**base,
                                                "check": "E4_cash_rollforward",
                                                "residual": 0.0}]),
        "driver_tree_nodes": pd.DataFrame([{**base, "basis": "average",
                                            "node_id": "rotce",
                                            "parent_id": None, "depth": 0,
                                            "sort_order": 0, "label": "ROTCE",
                                            "fmt": "pct", "relation": "root",
                                            "weight": np.nan, "value": 0.38,
                                            "formula": "RNOA + FLEV × Spread",
                                            "related_json": "[]", "note": "",
                                            "node_flags": ""}]),
        "driver_tree_checks": pd.DataFrame([{**base, "basis": "average",
                                             "check": "T2_rnoa_vs_opm_x_ato",
                                             "residual": 0.0}]),
        "capital_bridge_annual": pd.DataFrame([{**base, "step_order": 0,
                                                "concept": "noa_begin",
                                                "label": "NOA, end 2022",
                                                "value": 600.0,
                                                "step_kind": "start"}]),
        "capital_summary_annual": pd.DataFrame([{**base, "noa_end": 750.0,
                                                 "delta_noa": 150.0,
                                                 "cap_flags": ""}]),
        "capital_bridge_checks": pd.DataFrame([{**base,
                                                "check": "B1_bridge_additive",
                                                "residual": 0.0}]),
        "residual_income_annual": pd.DataFrame([{**base, "reoi": 340.0,
                                                 "r_op_assumed": 0.08,
                                                 "ri_flags": ""}]),
        "value_bridge_annual": pd.DataFrame([{**base, "step_order": 0,
                                              "concept": "reoi_prev",
                                              "label": "ReOI 2022",
                                              "value": 300.0,
                                              "step_kind": "start"}]),
        "residual_income_checks": pd.DataFrame([{**base,
                                                 "check": "RI1_bridge_additive",
                                                 "residual": 0.0}]),
        "market_snapshot_annual": pd.DataFrame([{**base, "trade_date": "20231229",
                                                 "market_cap": 3000.0}]),
        "valuation_annual": pd.DataFrame([{**base, "v_to_p": 1.1,
                                           "val_flags": ""}]),
        "valuation_bridge_annual": pd.DataFrame([{**base, "step_order": 0,
                                                  "concept": "noa",
                                                  "label": "NOA (book)",
                                                  "value": 750.0,
                                                  "step_kind": "start"}]),
        "valuation_grid": pd.DataFrame([{**base, "model": "reoi_g", "r": 0.08,
                                         "g": 0.03, "v_to_p": 1.0}]),
        "valuation_reverse_curve": pd.DataFrame([{**base, "r": 0.08,
                                                  "implied_g_reoi": 0.02}]),
        "valuation_checks": pd.DataFrame([{**base, "check": "V2_bridge_additive",
                                           "residual": 0.0}]),
    }
    for table, df in frames.items():
        s.con.register("_df", df)
        s.con.execute(f"CREATE TABLE {table} AS SELECT * FROM _df")
        s.con.unregister("_df")
    yield s
    s.close()


def test_export_bundle_complete_and_json_safe(seeded_store, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "T.json").write_text("{}", encoding="utf-8")  # stale pre-gzip bundle
    path = export_company(seeded_store, "T", out)
    assert path.name == "T.json.gz" and not (out / "T.json").exists()
    bundle = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    assert bundle["schema_version"] == SCHEMA_VERSION
    assert bundle["ts_code"] == "T"
    for _, (key, _) in EXPORT_TABLES.items():
        assert key in bundle and len(bundle[key]) >= 1
    # NaN exported as null, not 0 or string
    assert bundle["reformulated_bs"][0]["nfo"] is None
    # annual_only filter drops the H1 income row
    assert len(bundle["reformulated_is"]) == 1
    assert bundle["conventions"]["missing"].startswith("null means")
    assert bundle["unit"] == "CNY_yuan"
    assert bundle["overview"]["company_name"] is None
    assert bundle["overview"]["years"][0]["disclosure"] is None
    assert bundle["overview"]["years"][0]["revenue_yoy"] is None


def test_overview_uses_revenue_and_comparable_annual_data_for_another_company():
    prior, current = "20221231", "20231231"
    bundle = {
        "ts_code": "002000.SZ",
        "reformulated_bs": [{"end_date": current, "oa": 8e8, "fa": 2e8, "total_assets_reported": 1e9}],
        "reformulated_is": [
            {"end_date": prior, "period_kind": "cumulative", "revenue": 1e9, "total_revenue": 1.1e9},
            {"end_date": current, "period_kind": "cumulative", "revenue": 1.1e9, "total_revenue": 1.3e9},
        ],
        "ratios": [{"end_date": prior, "basis": "average", "rnoa": 0.2},
                   {"end_date": current, "basis": "opening", "rnoa": 0.4},
                   {"end_date": current, "basis": "average", "rnoa": 0.18}],
        "cash_summary": [{"end_date": prior, "cfo": -1e8}, {"end_date": current, "cfo": 2e8}],
        "calculation_details": {current: {
            "raw:cash_paid_for_investments": {"value": 2e8},
            "raw:cash_from_investment_disposals": {"value": 3e8},
        }},
    }
    company = {"name": "测试公司", "annual": {current: {
        "unit": "CNY_yuan", "report_url": "https://example.com/annual.pdf",
        "inventory": {"page": 5, "rows": [{"label": "原材料", "begin": 0, "end": 1e8}]},
    }}}
    overview = build_overview(bundle, {bundle["ts_code"]: company})
    assert overview["company_name"] == "测试公司"
    row = overview["years"][0]
    assert row["revenue_yoy"] == 0.1
    assert row["rnoa_change"] == -0.02
    assert row["cfo_yoy"] is None
    assert row["investment_net_outflow"] == -1e8
    assert row["oa_share"] == 0.8
    assert row["fa_share"] == 0.2
    assert row["disclosure"]["inventory"]["rows"][0]["delta"] == 1e8
    assert row["disclosure"]["inventory"]["source"].endswith("#page=5")
    assert row["disclosure"]["share_repurchase"] is None
    assert bundle["calculation_details"][current]["overview:rnoa_change"]["unit"] == "pp"
    assert bundle["calculation_details"][current]["overview:cfo_yoy"]["reason"]

    company["annual"][current]["unit"] = "CNY_wan"
    with pytest.raises(ValueError, match="CNY_yuan"):
        build_overview(bundle, {bundle["ts_code"]: company})


def test_overview_history_du_pont_and_per_share_use_reported_balances_and_units():
    dates = ["20211231", "20221231", "20241231", "20251231"]
    bundle = {
        "ts_code": "T",
        "reformulated_bs": [{"end_date": date, "total_assets_reported": assets}
                            for date, assets in zip(dates, [80e8, 120e8, 200e8, 200e8])],
        "reformulated_is": [{"end_date": date, "period_kind": "cumulative", "ni_total": 10e8,
                             "revenue": 50e8, "total_revenue": 80e8} for date in dates],
        "ratios": [],
        "cash_summary": [{"end_date": date, "fcf_simple": -4e8} for date in dates],
        "market_snapshot": [{"end_date": date, "shares": shares}
                            for date, shares in zip(dates, [1e8, 2e8, None, 0])],
        "calculation_details": {date: {"raw:total_equity": {"value": equity}}
                                for date, equity in zip(dates, [40e8, 60e8, -30e8, -50e8])},
    }
    first, second, gap, negative_equity = [row["history"] for row in build_overview(bundle, {})["years"]]
    assert second == pytest.approx({"avg_assets": 100e8, "avg_equity": 50e8, "net_margin": 0.125,
                                   "asset_turnover": 0.8, "equity_multiplier": 2., "roe": 0.2,
                                   "fcf_per_share": -2.})
    assert second["roe"] == pytest.approx(second["net_margin"] * second["asset_turnover"] * second["equity_multiplier"])
    assert first["net_margin"] == 0.125
    assert first["roe"] is None and gap["asset_turnover"] is None
    assert negative_equity["asset_turnover"] == 0.4
    assert negative_equity["roe"] is None and negative_equity["equity_multiplier"] is None
    assert gap["fcf_per_share"] is None and negative_equity["fcf_per_share"] is None
    details = bundle["calculation_details"][dates[1]]
    assert details["overview:avg_equity"]["unit"] == "CNY_yuan"
    assert details["overview:avg_equity"]["inputs"] == ["@raw:total_equity", "raw:total_equity"]
    assert details["overview:fcf_per_share"]["unit"] == "price"
    assert details["overview:fcf_per_share"]["inputs"] == ["fcf_simple", "shares"]
    assert bundle["calculation_details"][dates[3]]["overview:roe"]["reason"] == "平均股东权益非正值"


def test_export_fails_loudly_when_pipeline_incomplete(tmp_path):
    s = Store(tmp_path / "empty.duckdb")
    try:
        with pytest.raises(RuntimeError, match="run the full pipeline"):
            export_company(s, "T", tmp_path / "out")
    finally:
        s.close()


def test_company_index_lists_universe_and_only_bundles_that_exist(tmp_path):
    from pipeline.export import INDEX_FILE, export_company_index

    s = Store(tmp_path / "t.duckdb")
    universe = pd.DataFrame([
        {"ts_code": "600519.SH", "name": "贵州茅台", "industry": "白酒", "cnspell": "GZMT", "market": "主板"},
        {"ts_code": "000858.SZ", "name": "五粮液", "industry": "白酒", "cnspell": "WLY", "market": "主板"},
        {"ts_code": "688001.SH", "name": "测试科技", "industry": None, "cnspell": "CSKJ", "market": "科创板"},
    ])
    s.insert_raw("stock_basic", universe, "https://example.com", {"list_status": "L"})
    # A renamed company is stored as a new content-hash row; the latest one wins.
    s.insert_raw("stock_basic", universe.iloc[[1]].assign(name="五粮液股份"),
                 "https://example.com", {"list_status": "L"})
    out = tmp_path / "out"
    out.mkdir()
    # Only gzipped bundles count; a leftover plain .json is not loadable.
    for name in ["600519.SH.json.gz", "900001.SH.json.gz", "000858.SZ.json", INDEX_FILE, "notes.json"]:
        (out / name).write_text("{}", encoding="utf-8")
    from pipeline.bulk_analyze import _log
    _log(s, {"ts_code": "000858.SZ", "status": "failed", "reason": "error", "step": "reformulate",
             "finished_at": "2026-11-21T00:00:00"})
    _log(s, {"ts_code": "688001.SH", "status": "skipped", "reason": "financial",
             "finished_at": "2026-11-21T00:00:00"})
    _log(s, {"ts_code": "600519.SH", "status": "failed", "reason": "error", "step": "map",
             "finished_at": "2026-11-20T00:00:00"})
    _log(s, {"ts_code": "600519.SH", "status": "ok", "check_failures": "R1,L",
             "finished_at": "2026-11-21T00:00:00"})

    index = json.loads(export_company_index(s, out).read_text(encoding="utf-8"))
    s.close()
    assert index["schema_version"] == SCHEMA_VERSION
    assert index["analyzed"] == ["600519.SH", "900001.SH"]
    # latest log row per company wins; reasons only for companies without a bundle
    assert index["unavailable"] == {"000858.SZ": {"reason": "error", "step": "reformulate"},
                                    "688001.SH": {"reason": "financial", "step": None}}
    assert index["check_failures"] == {"600519.SH": ["R1", "L"]}
    rows = {row["ts_code"]: row for row in index["companies"]}
    assert len(index["companies"]) == 4
    assert rows["000858.SZ"]["name"] == "五粮液股份"
    # Missing industry stays null; a bundle outside the universe is kept, not dropped.
    assert rows["688001.SH"]["industry"] is None
    assert rows["900001.SH"] == {"ts_code": "900001.SH", "name": None, "industry": None,
                                 "cnspell": None, "market": None}


def test_export_without_market_data_keeps_empty_market_tables(seeded_store, tmp_path):
    from pipeline.export import MAY_BE_EMPTY_TABLES
    for table in MAY_BE_EMPTY_TABLES:
        seeded_store.con.execute(f"DELETE FROM {table}")
    path = export_company(seeded_store, "T", tmp_path / "out")
    bundle = json.loads(gzip.decompress(path.read_bytes()))
    for table in MAY_BE_EMPTY_TABLES:
        assert bundle[EXPORT_TABLES[table][0]] == []
    # core analysis tables still fail loudly when empty
    seeded_store.con.execute("DELETE FROM ratios_annual")
    with pytest.raises(RuntimeError, match="No rows in ratios_annual"):
        export_company(seeded_store, "T", tmp_path / "out")
