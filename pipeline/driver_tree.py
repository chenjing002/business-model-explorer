"""Module 9 — Profitability Driver Tree (annual).

Hierarchical RNOA/ROTCE decomposition assembled HERE from ratios_annual;
the frontend only renders the tree and joins declared related-metric keys.
Every parent–child relation is an accounting identity or definition — never
a causal claim. Additive levels carry explicit weights (+1/−1) and a
residual node so the signed sum is exact; residuals are reported, never
forced to zero.

Tree (per year × capital basis):
  rotce                       ROTCE = RNOA + FLEV × Spread   (identity terms)
  ├─ rnoa                     RNOA = OPM × ATO               (identity terms)
  │  ├─ opm                   OI after tax / revenue
  │  │  ├─ opm_core  (+1)     additive: core margin
  │  │  ├─ opm_unusual (+1)   additive residual: opm − opm_core
  │  │  └─ gross_margin       context (product-business proxy)
  │  └─ ato                   revenue / NOA
  │     ├─ noa_to_sales       reciprocal: 1 / ATO
  │     │  ├─ *_to_sales      additive, signed (+ assets, − op liabilities)
  │     │  └─ other_net_to_sales (+1) residual (incl. undisclosed items)
  │     └─ ollev              context: OL / NOA
  ├─ flev                     NFO / TE
  └─ spread                   RNOA − NBC
     └─ nbc                   NFE after tax / NFO

Suppression guards from Module 4 propagate: a NaN input ratio yields NaN
nodes/checks (flag carried), never a fabricated number.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from .store import Store

# component_to_sales columns from Module 4 and their sign in NOA/sales
ASSET_COMPONENTS = ["inventory", "receivables", "prepayments",
                    "ppe", "cip", "intangibles"]
LIABILITY_COMPONENTS = ["op_payables", "customer_advances"]

OTHER_NET_NOTE = ("Remainder so signed components sum exactly to NOA/sales: "
                  "other operating assets net of other operating liabilities, "
                  "plus any component not disclosed that year.")

_COMP_META = {
    "inventory": ("Inventory", ["dio"], "Inventory held per yuan of sales."),
    "receivables": ("Receivables", ["dso"],
                    "Trade receivables (notes + accounts + financing)."),
    "prepayments": ("Prepayments", [], ""),
    "ppe": ("PP&E", [], "Includes right-of-use assets."),
    "cip": ("CIP", [], "Construction in progress."),
    "intangibles": ("Intangibles", [], ""),
    "op_payables": ("Operating payables", ["dpo", "dpo_cogs"],
                    "Supplier/employee/tax credit — reduces NOA."),
    "customer_advances": ("Customer advances", ["advance_days"],
                          "预收款项 + 合同负债 — customers financing the "
                          "business, reduces NOA."),
}

# node_id, parent, label, fmt, relation, weight, formula, related, note
# — in depth-first order: sort_order renders the tree top to bottom.
_S = [
    ("rotce", None, "ROTCE — return on total common equity", "pct", "root", None,
     "ROTCE = RNOA + FLEV × Spread (total-equity level: TE = equity incl. minority)",
     ["roce_parent"],
     "Value shown is the direct computation NI_total / TE; the identity "
     "version is checked in T1."),
    ("rnoa", "rotce", "RNOA — return on net operating assets", "pct",
     "identity_term", None, "RNOA = OPM × ATO", [],
     "The operating engine, independent of financing."),
    ("opm", "rnoa", "OPM — operating margin (after tax)", "pct",
     "identity_term", None, "OPM = OI after tax / revenue", [], ""),
    ("opm_core", "opm", "Core operating margin", "pct", "component", 1.0,
     "oi_core_after_tax / revenue", [], ""),
    ("opm_unusual", "opm", "Unusual-items margin", "pct", "residual", 1.0,
     "OPM − core OPM", [],
     "Nonrecurring: non-operating items, impairments, disposals."),
    ("gross_margin", "opm", "Gross margin", "pct", "context", None,
     "(revenue − COGS) / revenue", [],
     "Product-business proxy; excludes finance-subsidiary interest lines."),
    ("ato", "rnoa", "ATO — net operating asset turnover", "x",
     "identity_term", None, "ATO = revenue / NOA", [], ""),
    ("noa_to_sales", "ato", "NOA / sales (capital intensity)", "x",
     "reciprocal", None, "NOA / sales = 1 / ATO", [],
     "Years of sales tied up in net operating assets; decomposes additively "
     "below (operating liabilities enter with a minus sign)."),
    *[(f"{name}_to_sales", "noa_to_sales",
       f"{_COMP_META[name][0]} / sales", "x", "component",
       1.0 if name in ASSET_COMPONENTS else -1.0,
       f"avg {_COMP_META[name][0].lower()} / revenue",
       _COMP_META[name][1], _COMP_META[name][2])
      for name in ASSET_COMPONENTS + LIABILITY_COMPONENTS],
    ("other_net_to_sales", "noa_to_sales", "Other net / sales", "x",
     "residual", 1.0, "NOA/sales − Σ signed components", [],
     OTHER_NET_NOTE),
    ("ollev", "ato", "OLLEV — operating liability leverage", "x", "context",
     None, "OLLEV = OL / NOA", [],
     "Suppliers, customers and employees financing operations lift ATO."),
    ("flev", "rotce", "FLEV — financial leverage", "x", "identity_term", None,
     "FLEV = NFO / TE", [],
     "Negative FLEV = net financial assets; low-yield cash drags ROTCE below RNOA."),
    ("spread", "rotce", "Spread — operating return minus borrowing cost", "pct",
     "identity_term", None, "Spread = RNOA − NBC", [],
     "Leverage helps only while the spread is positive."),
    ("nbc", "spread", "NBC — net borrowing cost", "pct", "identity_term", None,
     "NBC = NFE after tax / NFO", [],
     "With net financial assets (NFO < 0) this is a return earned, not a "
     "cost paid."),
]

TREE_SPEC = [dict(zip(
    ["node_id", "parent_id", "label", "fmt", "relation", "weight",
     "formula", "related", "note"], s)) for s in _S]
_BY_ID = {s["node_id"]: s for s in TREE_SPEC}


def _depth(node_id: str) -> int:
    d, cur = 0, _BY_ID[node_id]
    while cur["parent_id"] is not None:
        d, cur = d + 1, _BY_ID[cur["parent_id"]]
    return d


def _f(row: dict, key: str) -> float:
    v = row.get(key)
    return np.nan if v is None else float(v)


def _node_values(row: dict) -> dict[str, float]:
    """All node values for one ratios_annual row (one year × basis)."""
    v = {k: _f(row, k) for k in ["rnoa", "flev", "spread", "nbc", "opm",
                                 "opm_core", "ato", "ollev", "gross_margin"]}
    v["rotce"] = _f(row, "rotce_direct")
    v["opm_unusual"] = v["opm"] - v["opm_core"]
    v["noa_to_sales"] = (1.0 / v["ato"]
                         if not math.isnan(v["ato"]) and v["ato"] != 0
                         else np.nan)
    signed = 0.0
    for name in ASSET_COMPONENTS + LIABILITY_COMPONENTS:
        val = _f(row, f"{name}_to_sales")
        v[f"{name}_to_sales"] = val
        if not math.isnan(val):
            signed += _BY_ID[f"{name}_to_sales"]["weight"] * val
    v["other_net_to_sales"] = v["noa_to_sales"] - signed
    return v


def compute_driver_tree(
    ratios: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ratios: Module-4 ratios_annual rows for one company."""
    nodes, checks = [], []
    for row in ratios.sort_values(["end_date", "basis"]).to_dict("records"):
        ts, ed, basis = row["ts_code"], row["end_date"], row["basis"]
        rflags = row.get("ratio_flags") or ""
        v = _node_values(row)
        for order, s in enumerate(TREE_SPEC):
            nodes.append(dict(
                ts_code=ts, end_date=ed, basis=basis,
                node_id=s["node_id"], parent_id=s["parent_id"],
                depth=_depth(s["node_id"]), sort_order=order,
                label=s["label"], fmt=s["fmt"], relation=s["relation"],
                weight=s["weight"], value=v[s["node_id"]],
                formula=s["formula"],
                related_json=json.dumps(s["related"]),
                note=s["note"], node_flags=rflags,
            ))
        signed_sum = sum(
            _BY_ID[n]["weight"] * v[n]
            for n in [f"{c}_to_sales" for c in
                      ASSET_COMPONENTS + LIABILITY_COMPONENTS
                      if not math.isnan(v[f"{c}_to_sales"])]
        ) + v["other_net_to_sales"]
        for check, residual in [
            ("T1_rotce_identity_vs_direct", _f(row, "rotce") - v["rotce"]),
            ("T2_rnoa_vs_opm_x_ato", v["rnoa"] - v["opm"] * v["ato"]),
            ("T3_opm_additive", v["opm"] - (v["opm_core"] + v["opm_unusual"])),
            ("T4_spread_definition", v["spread"] - (v["rnoa"] - v["nbc"])),
            ("T5_noa_to_sales_additive", v["noa_to_sales"] - signed_sum),
        ]:
            checks.append(dict(ts_code=ts, end_date=ed, basis=basis,
                               check=check,
                               residual=None if math.isnan(residual)
                               else residual))
    return pd.DataFrame(nodes), pd.DataFrame(checks)


def build_driver_tree(store: Store, ts_code: str) -> dict:
    ratios = store.con.execute(
        "SELECT * FROM ratios_annual WHERE ts_code = ?", [ts_code]).df()
    if ratios.empty:
        raise RuntimeError(f"No ratios for {ts_code}; run `ratios` first.")
    nodes, checks = compute_driver_tree(ratios)
    for table, df in [("driver_tree_nodes", nodes),
                      ("driver_tree_checks", checks)]:
        store.con.register("_df", df)
        exists = store.con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name=?",
            [table]).fetchall()[0][0]
        if exists:
            store.con.execute(f"DELETE FROM {table} WHERE ts_code = ?", [ts_code])
            store.con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM _df")
        else:
            store.con.execute(f"CREATE TABLE {table} AS SELECT * FROM _df")
        store.con.unregister("_df")
    return {"nodes": nodes, "checks": checks}
