"""Offline tests for batch analysis (Module 16): eligibility, failure capture,
incremental skips and the identity-check summary."""
import json

import pandas as pd
import pytest

from pipeline import bulk_analyze
from pipeline.bulk_analyze import Params, analyze_all, latest_log, summarize_checks
from pipeline.export import INDEX_FILE
from pipeline.store import Store


def _bs(code, end_date, comp_type="1"):
    return {"ts_code": code, "ann_date": end_date, "f_ann_date": end_date, "end_date": end_date,
            "report_type": "1", "comp_type": comp_type, "update_flag": "0", "total_assets": 100.0}


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.duckdb")
    s.insert_raw("stock_basic", pd.DataFrame([
        {"ts_code": c, "name": n, "industry": i, "cnspell": "X", "market": "主板"}
        for c, n, i in [("000001.SZ", "平安银行", "银行"), ("000858.SZ", "五粮液", "白酒"),
                        ("600519.SH", "贵州茅台", "白酒"), ("688999.SH", "新股", "半导体"),
                        ("600000.SH", "转型公司", "银行")]]), "u", {})
    s.insert_raw("balancesheet", pd.DataFrame([
        _bs("000001.SZ", "20251231", "2"),
        _bs("000858.SZ", "20241231"), _bs("000858.SZ", "20251231"),
        _bs("600519.SH", "20251231"),
        _bs("688999.SH", "20250930"),  # interim only, no annual report yet
        # comp_type is judged by the latest annual report
        _bs("600000.SH", "20241231", "1"), _bs("600000.SH", "20251231", "2"),
    ]), "u", {})
    yield s
    s.close()


@pytest.fixture
def fake_pipeline(monkeypatch):
    calls = []

    def fake_analyze(store, ts_code, params):
        calls.append(ts_code)
        if ts_code == "000858.SZ":
            error = RuntimeError("No std_facts")
            error.step = "reformulate"
            raise error
        (params.out_dir / f"{ts_code}.json.gz").write_bytes(b"")

    monkeypatch.setattr(bulk_analyze, "analyze_company", fake_analyze)
    monkeypatch.setattr(bulk_analyze, "summarize_checks", lambda store, code: pd.DataFrame([
        {"ts_code": code, "family": "R1", "checked": 2, "failed": 1, "max_abs_residual": 5e6},
        {"ts_code": code, "family": "T", "checked": 3, "failed": 0, "max_abs_residual": 0.0}]))
    return calls


def test_batch_skips_financials_and_missing_reports_and_records_failures(store, fake_pipeline, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "000858.SZ.json.gz").write_bytes(b"")  # stale bundle from an earlier success
    result = analyze_all(store, Params(out_dir=out))
    assert result.counts == {"ok": 1, "failed": 1, "skipped": 3, "unchanged": 0}
    assert fake_pipeline == ["000858.SZ", "600519.SH"]
    log = latest_log(store).set_index("ts_code")
    assert log.loc["000001.SZ", ["status", "reason"]].tolist() == ["skipped", "financial"]
    assert log.loc["600000.SH", "reason"] == "financial"
    assert log.loc["688999.SH", "reason"] == "no_annual_report"
    assert log.loc["000858.SZ", ["status", "step"]].tolist() == ["failed", "reformulate"]
    assert "No std_facts" in log.loc["000858.SZ", "error"]
    assert log.loc["600519.SH", ["status", "check_failures"]].tolist() == ["ok", "R1"]
    assert log.loc["600519.SH", "n_annual"] == 1
    # a failed company never keeps a bundle the picker would offer
    assert not (out / "000858.SZ.json.gz").exists()
    index = json.loads((out / INDEX_FILE).read_text(encoding="utf-8"))
    assert index["analyzed"] == ["600519.SH"]
    assert index["unavailable"]["000858.SZ"] == {"reason": "error", "step": "reformulate"}
    assert index["unavailable"]["000001.SZ"]["reason"] == "financial"
    assert index["check_failures"] == {"600519.SH": ["R1"]}


def test_batch_is_incremental_on_raw_inputs(store, fake_pipeline, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    analyze_all(store, Params(out_dir=out))
    fake_pipeline.clear()
    again = analyze_all(store, Params(out_dir=out))
    assert again.counts["unchanged"] == 5 and fake_pipeline == []
    # new raw rows change the company's fingerprint
    store.insert_raw("balancesheet", pd.DataFrame([_bs("600519.SH", "20241231")]), "u", {})
    fake_pipeline.clear()
    analyze_all(store, Params(out_dir=out))
    assert fake_pipeline == ["600519.SH"]
    # a deleted bundle is rebuilt; --force reruns everything eligible
    (out / "600519.SH.json.gz").unlink()
    fake_pipeline.clear()
    analyze_all(store, Params(out_dir=out))
    assert fake_pipeline == ["600519.SH"]
    fake_pipeline.clear()
    analyze_all(store, Params(out_dir=out), force=True)
    assert fake_pipeline == ["000858.SZ", "600519.SH"]
    fake_pipeline.clear()
    analyze_all(store, Params(out_dir=out), codes=["600519.SH"], force=True)
    assert fake_pipeline == ["600519.SH"]


def test_check_summary_uses_cli_tolerances_and_ignores_diagnostics(tmp_path):
    s = Store(tmp_path / "c.duckdb")
    tables = {
        "reformulated_bs": pd.DataFrame({"ts_code": "T", "end_date": ["20241231", "20250630", "20251231"],
                                         "r1_assets_residual": [2e6, 9e9, 0.0],
                                         "r2_liab_residual": [0.0, 0.0, None],
                                         "r3_cse_residual": [0.0, 0.0, 0.0]}),
        "reformulated_is": pd.DataFrame({"ts_code": "T", "end_date": ["20251231", "20251231"],
                                         "period_kind": ["cumulative", "single_quarter"],
                                         "r4_pretax_residual": [0.0, 5e9]}),
        "econ_map_checks": pd.DataFrame({"ts_code": "T", "end_date": "20251231",
                                         "check": ["L1_sources_vs_total_assets", "L4_bridge_residual"],
                                         "residual": [0.0, 3e8]}),
        "econ_evolution_checks": pd.DataFrame({"ts_code": "T", "end_date": "20251231",
                                               "check": ["E1_sources_delta", "E2_employment_delta",
                                                         "E3_panel_additive_inventory", "E4_cash_rollforward"],
                                               "residual": [1150.0, 2e6, 0.01, 1e9]}),
        "driver_tree_checks": pd.DataFrame({"ts_code": "T", "end_date": "20251231",
                                            "check": ["T1_rotce"], "residual": [None]}),
        "capital_bridge_checks": pd.DataFrame({"ts_code": "T", "end_date": "20251231",
                                               "check": ["B1"], "residual": [0.5]}),
        "residual_income_checks": pd.DataFrame({"ts_code": "T", "end_date": "20251231",
                                                "check": ["RI1_bridge", "RI3_rnoa"],
                                                "residual": [0.5, 1e-9]}),
        "valuation_checks": pd.DataFrame({"ts_code": "T", "end_date": "20251231",
                                          "check": ["M1_mcap", "M2_pe", "V2_bridge"],
                                          "residual": [2e-4, 0.5, 0.0]}),
    }
    for name, df in tables.items():
        s.con.register("_df", df)
        s.con.execute(f"CREATE TABLE {name} AS SELECT * FROM _df")
        s.con.unregister("_df")
    got = summarize_checks(s, "T").set_index("family")
    s.close()
    # annual rows only; interim and single-quarter residuals are not counted
    assert got.loc["R1", ["checked", "failed"]].tolist() == [2, 1]
    assert got.loc["R2", "checked"] == 1  # null residual = not computed
    assert got.loc["R4", ["checked", "failed"]].tolist() == [1, 0]
    # L4 (disclosed indirect-method bridge), E4 and M2 are diagnostics
    assert got.loc["L", ["checked", "failed"]].tolist() == [1, 0]
    assert got.loc["L4", ["checked", "failed"]].tolist() == [1, 1]
    # E1/E2 difference the L1/L2 totals (¥1M); E3 is exact (¥0.001); E4 informational
    assert got.loc["E", ["checked", "failed"]].tolist() == [3, 2]
    assert got.loc["T", "checked"] == 0 and pd.isna(got.loc["T", "max_abs_residual"])
    assert got.loc["RI", ["checked", "failed"]].tolist() == [2, 1]
    assert got.loc["V", ["checked", "failed"]].tolist() == [2, 1]
    assert set(bulk_analyze.DIAGNOSTIC_FAMILIES) == {"L4"}
