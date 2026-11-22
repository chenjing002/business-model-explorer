"""Offline tests for the Profitability Driver Tree (Module 9)."""
import json

import numpy as np
import pandas as pd
import pytest

from pipeline.driver_tree import (
    ASSET_COMPONENTS, LIABILITY_COMPONENTS, TREE_SPEC, compute_driver_tree)


def ratios_row(**over):
    """A consistent ratios_annual row: identities hold by construction."""
    opm, ato, flev, nbc = 0.5, 4.0, -0.8, 0.01
    rnoa = opm * ato  # 2.0
    spread = rnoa - nbc
    rotce = rnoa + flev * spread
    base = dict(
        ts_code="T", end_date="20231231", basis="average",
        revenue=1000.0, rnoa=rnoa, opm=opm, opm_core=0.48, ato=ato,
        ollev=0.6, flev=flev, nbc=nbc, spread=spread,
        rotce=rotce, rotce_direct=rotce, roce_parent=0.41,
        gross_margin=0.9,
        inventory_to_sales=0.28, receivables_to_sales=0.01,
        prepayments_to_sales=0.001, ppe_to_sales=0.12, cip_to_sales=0.01,
        intangibles_to_sales=0.05, op_payables_to_sales=0.09,
        customer_advances_to_sales=0.07, ratio_flags="net_financial_assets",
    )
    base.update(over)
    return base


def by_id(nodes, node_id):
    return nodes[nodes.node_id == node_id].iloc[0]


def test_structure_parents_depths_and_order():
    ids = {s["node_id"] for s in TREE_SPEC}
    for s in TREE_SPEC:
        assert s["parent_id"] is None or s["parent_id"] in ids
    nodes, _ = compute_driver_tree(pd.DataFrame([ratios_row()]))
    assert by_id(nodes, "rotce").depth == 0
    assert by_id(nodes, "rnoa").depth == 1
    assert by_id(nodes, "opm").depth == 2
    assert by_id(nodes, "inventory_to_sales").depth == 4
    # one row per spec node for the single year×basis
    assert len(nodes) == len(TREE_SPEC)


def test_identity_checks_exact_on_consistent_row():
    _, checks = compute_driver_tree(pd.DataFrame([ratios_row()]))
    assert set(checks.check) == {
        "T1_rotce_identity_vs_direct", "T2_rnoa_vs_opm_x_ato",
        "T3_opm_additive", "T4_spread_definition",
        "T5_noa_to_sales_additive"}
    assert checks.residual.abs().max() < 1e-12


def test_additive_margin_split_and_residual_component():
    nodes, _ = compute_driver_tree(pd.DataFrame([ratios_row()]))
    assert by_id(nodes, "opm_unusual").value == pytest.approx(0.02)
    # signed components + other_net sum exactly to 1/ATO
    kids = nodes[nodes.parent_id == "noa_to_sales"]
    signed = (kids.weight * kids.value).sum()
    assert signed == pytest.approx(1 / 4.0, abs=1e-15)
    assert by_id(nodes, "op_payables_to_sales").weight == -1.0
    assert by_id(nodes, "inventory_to_sales").weight == 1.0
    # other_net = 0.25 − (0.471 − 0.16) = −0.061
    assert by_id(nodes, "other_net_to_sales").value == pytest.approx(-0.061)


def test_rotce_value_is_direct_and_flags_carried():
    nodes, _ = compute_driver_tree(pd.DataFrame([ratios_row()]))
    r = by_id(nodes, "rotce")
    assert r.value == pytest.approx(2.0 + (-0.8) * 1.99)
    assert r.node_flags == "net_financial_assets"
    assert json.loads(by_id(nodes, "inventory_to_sales").related_json) == ["dio"]


def test_suppressed_inputs_propagate_nan_not_numbers():
    row = ratios_row(ato=np.nan, rnoa=np.nan, spread=np.nan, nbc=np.nan,
                     rotce=np.nan, ratio_flags="nfo_near_zero_suppressed")
    nodes, checks = compute_driver_tree(pd.DataFrame([row]))
    for nid in ["ato", "noa_to_sales", "other_net_to_sales", "rnoa", "nbc"]:
        assert pd.isna(by_id(nodes, nid).value)
    # component ratios still reported (computable without NOA)
    assert by_id(nodes, "inventory_to_sales").value == pytest.approx(0.28)
    sup = checks[checks.check.isin(
        ["T2_rnoa_vs_opm_x_ato", "T5_noa_to_sales_additive"])]
    assert sup.residual.isna().all()


def test_first_year_all_nan_with_flag():
    row = dict(ts_code="T", end_date="20221231", basis="average",
               revenue=900.0, ratio_flags="no_opening_balance")
    nodes, checks = compute_driver_tree(pd.DataFrame([row, ratios_row()]))
    first = nodes[nodes.end_date == "20221231"]
    assert first.value.isna().all()
    assert (first.node_flags == "no_opening_balance").all()
    assert checks[checks.end_date == "20221231"].residual.isna().all()


def test_missing_component_absorbed_by_residual_sum_still_exact():
    row = ratios_row()
    del row["cip_to_sales"]
    nodes, checks = compute_driver_tree(pd.DataFrame([row]))
    assert pd.isna(by_id(nodes, "cip_to_sales").value)
    t5 = checks[checks.check == "T5_noa_to_sales_additive"].iloc[0]
    assert abs(t5.residual) < 1e-15
    # residual now carries what cip used to: −0.061 + 0.01
    assert by_id(nodes, "other_net_to_sales").value == pytest.approx(-0.051)


def test_both_bases_produced():
    rows = [ratios_row(), ratios_row(basis="opening", ato=5.0, rnoa=2.5)]
    nodes, _ = compute_driver_tree(pd.DataFrame(rows))
    assert set(nodes.basis) == {"average", "opening"}
    assert by_id(nodes[nodes.basis == "opening"], "noa_to_sales").value \
        == pytest.approx(0.2)
