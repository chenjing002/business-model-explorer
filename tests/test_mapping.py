"""Offline tests for the standardized mapping layer (Module 2)."""
import numpy as np
import pandas as pd
import pytest

from pipeline.mapping import (
    DEFAULT_MAPPING_PATH,
    build_facts,
    derive_single_quarters,
    load_mapping,
    mapping_coverage,
    select_preferred,
)


@pytest.fixture(scope="module")
def cfg():
    return load_mapping(DEFAULT_MAPPING_PATH)


def test_real_mapping_config_loads_and_is_consistent(cfg):
    # load_mapping validates: all statements present, concept/class present,
    # no concept mapped from two fields.
    assert cfg["balancesheet"]["period_kind"] == "point"
    assert cfg["income"]["period_kind"] == "cumulative"
    assert cfg["cashflow"]["fields"]["n_cashflow_act"]["concept"] == "cfo"


def raw_income_rows():
    def row(end_date, revenue, update_flag="0", f_ann_date="20240101"):
        return dict(
            ts_code="600519.SH", end_date=end_date, report_type="1",
            f_ann_date=f_ann_date, update_flag=update_flag,
            revenue=revenue, basic_eps=revenue / 1e9,
            _row_hash=f"h{end_date}{update_flag}", _fetched_at="t",
        )
    return [
        row("20230331", 100.0),
        row("20230630", 250.0),
        row("20230930", 420.0),
        row("20231231", 600.0),
        # revision of FY: must be preferred over the original
        row("20231231", 610.0, update_flag="1", f_ann_date="20240601"),
    ]


def test_select_preferred_picks_latest_revision():
    df = pd.DataFrame(raw_income_rows())
    pref = select_preferred(df)
    assert len(pref) == 4  # one row per period
    fy = pref[pref.end_date == "20231231"].iloc[0]
    assert fy.revenue == 610.0 and fy.update_flag == "1"


def test_build_facts_roundtrip_and_null_handling(cfg):
    rows = raw_income_rows()
    rows[0]["revenue"] = np.nan  # Q1 revenue not disclosed
    facts = build_facts(pd.DataFrame(rows), cfg, "income")
    rev = facts[facts.concept == "revenue"]
    # No fact for the null; values match raw on preferred rows (M1)
    assert set(rev.end_date) == {"20230630", "20230930", "20231231"}
    assert rev.set_index("end_date").value.to_dict() == {
        "20230630": 250.0, "20230930": 420.0, "20231231": 610.0}
    assert (rev.value_type == "reported").all()
    assert (rev.period_kind == "cumulative").all()
    fy = rev[rev.end_date == "20231231"].iloc[0]
    assert fy.source_row_hash == "h202312311" and fy.raw_field == "revenue"


def test_single_quarter_derivation(cfg):
    facts = build_facts(pd.DataFrame(raw_income_rows()), cfg, "income")
    sq = derive_single_quarters(facts)
    rev = sq[sq.concept == "revenue"].set_index("end_date").value.to_dict()
    assert rev == {"20230331": 100.0, "20230630": 150.0,
                   "20230930": 170.0, "20231231": 190.0}
    # M2: four single quarters sum to FY cumulative (revised value)
    assert abs(sum(rev.values()) - 610.0) < 1e-9
    assert (sq.value_type == "calculated").all()
    assert (sq.period_kind == "single_quarter").all()


def test_single_quarter_skips_gap_and_per_share(cfg):
    rows = [r for r in raw_income_rows() if r["end_date"] != "20230630"]
    facts = build_facts(pd.DataFrame(rows), cfg, "income")
    sq = derive_single_quarters(facts)
    rev = sq[sq.concept == "revenue"]
    # Q3 single needs missing Q2 cumulative -> not derived
    assert "20230930" not in set(rev.end_date)
    assert "20230331" in set(rev.end_date)
    # per-share values are never differenced
    assert sq[sq.penman_class == "per_share"].empty


def test_balance_sheet_facts_are_point_not_differenced(cfg):
    df = pd.DataFrame([dict(
        ts_code="600519.SH", end_date="20231231", report_type="1",
        f_ann_date="20240402", update_flag="0", inventories=46_000_000_000.0,
        _row_hash="h", _fetched_at="t",
    )])
    facts = build_facts(df, cfg, "balancesheet")
    inv = facts[facts.concept == "inventory"].iloc[0]
    assert inv.period_kind == "point"
    assert inv.penman_class == "operating_asset"
    assert derive_single_quarters(facts).empty


def test_std_identity_holds_on_facts(cfg):
    # M4: assets = liabilities + equity via standardized concepts
    df = pd.DataFrame([dict(
        ts_code="600519.SH", end_date="20231231", report_type="1",
        f_ann_date="20240402", update_flag="0",
        total_assets=100.0, total_liab=40.0, total_hldr_eqy_inc_min_int=60.0,
        _row_hash="h", _fetched_at="t",
    )])
    facts = build_facts(df, cfg, "balancesheet")
    v = facts.set_index("concept").value
    assert v["total_assets"] == v["total_liabilities"] + v["total_equity"]


def test_mapping_coverage_reports_unmapped(cfg):
    df = pd.DataFrame([dict(
        ts_code="600519.SH", end_date="20231231", report_type="1",
        inventories=1.0, some_new_vendor_field=5.0, _row_hash="h",
    )])
    cov = mapping_coverage(df, cfg, "balancesheet")
    assert list(cov.unmapped_field) == ["some_new_vendor_field"]


def test_combined_presentation_fields_tagged(cfg):
    spec = cfg["balancesheet"]["fields"]["accounts_receiv_bill"]
    assert spec["class"] == "presentation_combined"
