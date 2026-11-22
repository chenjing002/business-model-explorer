"""Offline tests for the DuckDB raw store: idempotency, revisions, provenance."""
import pandas as pd
import pytest

from pipeline.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "test.duckdb")
    yield s
    s.close()


def sample_df(**over):
    base = dict(
        ts_code="600519.SH", ann_date="20240402", f_ann_date="20240402",
        end_date="20231231", report_type="1", comp_type="1",
        total_assets=272_658_000_000.0, update_flag="0",
    )
    base.update(over)
    return pd.DataFrame([base])


def test_insert_and_load_preserves_values_and_provenance(store):
    n = store.insert_raw("balancesheet", sample_df(), "https://gw.example", {"ts_code": "600519.SH"})
    assert n == 1
    out = store.load_raw("balancesheet", "600519.SH")
    assert len(out) == 1
    assert out.loc[0, "total_assets"] == 272_658_000_000.0
    assert out.loc[0, "_source_url"] == "https://gw.example"
    assert "600519.SH" in out.loc[0, "_api_params"]
    assert out.loc[0, "_fetched_at"]  # timestamp recorded


def test_refetch_identical_data_is_idempotent(store):
    df = sample_df()
    assert store.insert_raw("balancesheet", df, "u", {}) == 1
    assert store.insert_raw("balancesheet", df, "u", {}) == 0
    assert len(store.load_raw("balancesheet")) == 1


def test_revision_kept_as_new_row_not_overwrite(store):
    store.insert_raw("balancesheet", sample_df(), "u", {})
    revised = sample_df(total_assets=272_600_000_000.0, update_flag="1", f_ann_date="20240610")
    assert store.insert_raw("balancesheet", revised, "u", {}) == 1
    out = store.load_raw("balancesheet")
    assert len(out) == 2  # both original and restated rows preserved
    assert set(out.update_flag) == {"0", "1"}


def test_schema_evolution_adds_new_columns(store):
    store.insert_raw("balancesheet", sample_df(), "u", {})
    with_new_col = sample_df(end_date="20221231", oth_eqt_tools_p_shr=1_000_000.0)
    assert store.insert_raw("balancesheet", with_new_col, "u", {}) == 1
    out = store.load_raw("balancesheet")
    assert "oth_eqt_tools_p_shr" in out.columns
    assert len(out) == 2


def test_empty_frame_is_noop(store):
    assert store.insert_raw("income", pd.DataFrame(), "u", {}) == 0
    assert store.summary().loc[lambda d: d.statement == "income", "rows"].iloc[0] == 0
