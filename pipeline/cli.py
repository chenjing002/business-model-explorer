"""CLI: ingest one company's statements and run the validation report.

Usage:
  .venv/bin/python -m pipeline.cli ingest 600519.SH --start 20150101
  .venv/bin/python -m pipeline.cli validate 600519.SH
  .venv/bin/python -m pipeline.cli summary
  .venv/bin/python -m pipeline.cli ingest-all            # every listed A-share
  .venv/bin/python -m pipeline.cli validate-all
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

import pandas as pd

from .config import get_settings
from .store import Store
from .validate import validate_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pipeline.cli")


def cmd_ingest(args) -> int:
    from .client import TushareClient  # imported here so offline commands need no token

    settings = get_settings()
    client = TushareClient(settings)
    store = Store(settings.db_path)
    try:
        from .ingest import ingest_company

        results = ingest_company(
            client, store, args.ts_code, args.start, args.end,
            report_types=tuple(args.report_types.split(",")),
        )
    finally:
        store.close()
    print(f"\nIngestion results for {args.ts_code} ({args.start}–{args.end}):")
    for (stmt, rt), r in results.items():
        status = f"ERROR: {r['error']}" if r["error"] else "ok"
        print(f"  {stmt:13s} rt={rt}: fetched {r['fetched']:3d}, inserted {r['inserted']:3d}  [{status}]")
    return 0


def cmd_validate(args) -> int:
    settings = get_settings()
    store = Store(settings.db_path)
    try:
        bs = store.load_raw("balancesheet", args.ts_code)
        inc = store.load_raw("income", args.ts_code)
        cf = store.load_raw("cashflow", args.ts_code)
    finally:
        store.close()
    if bs.empty and inc.empty and cf.empty:
        print(f"No stored data for {args.ts_code}. Run ingest first.")
        return 1
    checks, coverage = validate_all(bs, inc, cf)

    out_checks = settings.db_path.parent / f"validation_checks_{args.ts_code}.csv"
    out_cov = settings.db_path.parent / f"validation_coverage_{args.ts_code}.csv"
    checks.to_csv(out_checks, index=False)
    coverage.to_csv(out_cov, index=False)

    print(f"\nValidation summary for {args.ts_code}:")
    print(checks.groupby(["check", "status"]).size().unstack(fill_value=0).to_string())
    fails = checks[checks.status == "FAIL"]
    if not fails.empty:
        print(f"\nFAILURES ({len(fails)} rows) — reported, not corrected:")
        with pd.option_context("display.max_rows", 200, "display.width", 200):
            print(fails[["check", "ts_code", "end_date", "report_type", "lhs", "rhs", "diff"]].to_string(index=False))
    cov_fail = coverage[coverage.status == "FAIL"]
    if not cov_fail.empty:
        print(f"\nCOVERAGE GAPS:\n{cov_fail.to_string(index=False)}")
    print(f"\nReports written to {out_checks} and {out_cov}")
    return 0 if fails.empty else 2


def cmd_map(args) -> int:
    from .mapping import build_std_facts

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        result = build_std_facts(store, args.ts_code)
    finally:
        store.close()
    print(f"\nstd_facts rebuilt for {args.ts_code}:")
    print(f"  total facts: {result['facts']}  "
          f"(reported {result['reported']}, calculated {result['calculated']})")
    cov = result["coverage"]
    if cov.empty:
        print("  mapping coverage: all populated fields mapped")
    else:
        print(f"  populated-but-unmapped fields ({len(cov)}):")
        print(cov.to_string(index=False))
    return 0


def cmd_reformulate(args) -> int:
    from .reformulate import build_reformulated

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        result = build_reformulated(store, args.ts_code, tax_rate=args.tax_rate)
    finally:
        store.close()
    bs, is_ = result["bs"], result["is"]
    print(f"\nReformulated statements for {args.ts_code} "
          f"(tax rate assumption {args.tax_rate:.0%}):")
    ann = bs[bs.end_date.str.endswith("1231")]
    cols = ["end_date", "noa", "nfo", "minority_interests", "cse_calc",
            "r1_assets_residual", "r2_liab_residual", "r3_cse_residual"]
    with pd.option_context("display.float_format", lambda v: f"{v/1e9:,.2f}"):
        print("\nAnnual reformulated BS (billions CNY):")
        print(ann[cols].to_string(index=False))
    ann_is = is_[(is_.period_kind == "cumulative")
                 & (is_.end_date.str.endswith("1231"))]
    cols2 = ["end_date", "oi_core_pretax", "unusual_pretax", "nfe_pretax",
             "oi_after_tax", "ni_total", "r4_pretax_residual"]
    with pd.option_context("display.float_format", lambda v: f"{v/1e9:,.2f}"):
        print("\nAnnual reformulated IS (billions CNY):")
        print(ann_is[cols2].to_string(index=False))
    for name, col, df in [("R1", "r1_assets_residual", bs),
                          ("R2", "r2_liab_residual", bs),
                          ("R3", "r3_cse_residual", bs),
                          ("R4", "r4_pretax_residual", is_)]:
        bad = df[df[col].abs() > 1e6]
        print(f"{name}: {len(bad)} periods with |residual| > ¥1M "
              f"(max {df[col].abs().max():,.0f})")
    print(f"\nreclass decisions recorded: {len(result['decisions'])}")
    return 0


def cmd_ratios(args) -> int:
    from .ratios import build_ratios

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        ratios = build_ratios(store, args.ts_code)
    finally:
        store.close()
    avg = ratios[ratios.basis == "average"].copy()
    pct = ["rnoa", "opm", "opm_core", "ato", "ollev", "flev", "nbc", "spread",
           "rotce", "rotce_direct", "roce_parent", "gross_margin"]
    cols = ["end_date"] + [c for c in pct if c in avg.columns] + ["ratio_flags"]
    with pd.option_context("display.float_format", lambda v: f"{v:.3f}",
                           "display.width", 250):
        print(f"\nAnnual ratios for {args.ts_code} (average-capital basis):")
        print(avg[cols].to_string(index=False))
    both = avg.dropna(subset=["rnoa"])
    k1 = (both.rnoa - both.opm * both.ato).abs().max()
    k2 = (both.dropna(subset=["rotce"]).rotce
          - both.dropna(subset=["rotce"]).rotce_direct).abs().max()
    print(f"\nK1 max |RNOA − OPM×ATO| = {k1:.2e}")
    print(f"K2 max |ROTCE identity − direct| = {k2:.2e}")
    return 0


def cmd_wc(args) -> int:
    from .working_capital import build_working_capital

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        wc = build_working_capital(store, args.ts_code)
    finally:
        store.close()
    cols = ["end_date", "dio", "dso", "dpo", "dpo_cogs", "ccc", "advance_days",
            "owc_pct_sales", "incr_owc_per_incr_revenue", "wc_flags"]
    with pd.option_context("display.float_format", lambda v: f"{v:,.1f}",
                           "display.width", 220):
        print(f"\nWorking capital & cash conversion for {args.ts_code} "
              f"(average balances; {wc.dpo_method.dropna().iloc[0] if 'dpo_method' in wc and wc.dpo_method.notna().any() else ''}):")
        print(wc[[c for c in cols if c in wc.columns]].to_string(index=False))
    return 0


def cmd_cash(args) -> int:
    from .cash_reconciliation import build_cash_reconciliation

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        result = build_cash_reconciliation(store, args.ts_code)
    finally:
        store.close()
    s = result["summary"]
    disp = s.copy()
    for c in ["ni_total", "cfo", "capex_paid", "fcf_simple",
              "c1_bridge_residual", "c2_indirect_vs_direct"]:
        disp[c] = disp[c] / 1e9
    cols = ["end_date", "ni_total", "cfo", "capex_paid", "fcf_simple",
            "cash_conversion", "c1_bridge_residual", "c2_indirect_vs_direct",
            "cf_flags"]
    with pd.option_context("display.float_format", lambda v: f"{v:,.2f}",
                           "display.width", 220):
        print(f"\nEarnings-to-cash summary for {args.ts_code} "
              f"(money in billions CNY; cash_conversion = CFO/NI ratio):")
        print(disp[cols].to_string(index=False))
    b = result["bridge"]
    if not b.empty:
        latest = b[b.end_date == b.end_date.max()]
        print(f"\nBridge {latest.end_date.iloc[0]} (billions CNY):")
        with pd.option_context("display.float_format", lambda v: f"{v/1e9:,.2f}"):
            print(latest[["step_order", "label", "value"]].to_string(index=False))
    return 0


def cmd_export(args) -> int:
    from .export import export_company

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        path = export_company(store, args.ts_code, args.out)
    finally:
        store.close()
    size_kb = path.stat().st_size / 1024
    print(f"Exported {args.ts_code} bundle -> {path} ({size_kb:,.0f} KB)")
    print(f"Company index refreshed -> {path.parent / 'companies.json'}")
    return 0


def cmd_pages(args) -> int:
    from pathlib import Path

    from .pages import DEFAULT_OUT, publish, stage

    out = Path(args.out) if args.out else DEFAULT_OUT
    report = stage(out, build=not args.skip_build)
    totals = report.pop("_bundles")
    print(f"Bundles: {totals['count']:,} · exported {totals['source_bytes'] / 1e9:.2f} GB "
          f"→ published {totals['published_bytes'] / 1e9:.2f} GB")
    for name, site in report.items():
        print(f"  {name}: {site['bundles']:,} bundles, {site['bytes'] / 1e6:,.0f} MB -> {site['path']}")
    if args.publish:
        for url in publish(out):
            print(f"Published {url}")
    return 0


def cmd_screens(args) -> int:
    from .screens import export_screens, summarize

    store = Store(get_settings().db_path)
    try:
        path = export_screens(store, args.out)
    finally:
        store.close()
    print(f"{summarize(path)}\n-> {path}")
    return 0


def cmd_companies(args) -> int:
    from .export import export_company_index

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        path = export_company_index(store, args.out)
    finally:
        store.close()
    index = json.loads(path.read_text(encoding="utf-8"))
    print(f"Company index -> {path} ({path.stat().st_size / 1024:,.0f} KB): "
          f"{len(index['companies']):,} companies, {len(index['analyzed'])} with bundles")
    return 0


def cmd_econmap(args) -> int:
    from .econ_evolution import build_econ_evolution
    from .economics_map import build_economics_map

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        result = build_economics_map(store, args.ts_code)
        evo = build_econ_evolution(store, args.ts_code)
    finally:
        store.close()
    nodes, checks = result["nodes"], result["checks"]
    print(f"\nEconomics map for {args.ts_code}: {len(nodes)} nodes, "
          f"{nodes.end_date.nunique()} years")
    bad = checks[checks.residual.abs() > 1e6]
    print(f"Layer identity checks: {len(checks)} total, "
          f"{len(bad)} with |residual| > ¥1M")
    if not bad.empty:
        with pd.option_context("display.float_format", lambda v: f"{v:,.0f}"):
            print(bad.to_string(index=False))
    groups, flows, echecks = evo["groups"], evo["flows"], evo["checks"]
    print(f"Evolution: {len(groups)} group rows, {len(flows)} flow steps, "
          f"{len(echecks)} checks")
    e_id = echecks[echecks.check.str.startswith(("E1", "E2", "E3"))]
    ebad = e_id[e_id.residual.abs() > 1e-3]
    print(f"Evolution identity checks (E1–E3): {len(e_id)} total, "
          f"{len(ebad)} with |residual| > ¥0.001")
    if not ebad.empty:
        print(ebad.to_string(index=False))
    e4 = echecks[(echecks.check == "E4_cash_rollforward")
                 & (echecks.residual.abs() > 1e-3)]
    if not e4.empty:
        print("E4 cash roll-forward (informational, disclosed lines):")
        print(e4.to_string(index=False))
    return 0


def cmd_drivertree(args) -> int:
    from .driver_tree import build_driver_tree

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        result = build_driver_tree(store, args.ts_code)
    finally:
        store.close()
    nodes, checks = result["nodes"], result["checks"]
    print(f"\nDriver tree for {args.ts_code}: {len(nodes)} node rows, "
          f"{nodes.end_date.nunique()} years × {nodes.basis.nunique()} bases "
          f"× {nodes.node_id.nunique()} nodes")
    bad = checks[checks.residual.abs() > 1e-12]
    nulls = checks[checks.residual.isna()]
    print(f"Identity checks: {len(checks)} total, {len(bad)} with "
          f"|residual| > 1e-12, {len(nulls)} null (suppressed/first year)")
    if not bad.empty:
        print(bad.to_string(index=False))
    avg = nodes[(nodes.basis == "average")
                & (nodes.end_date == nodes.end_date.max())]
    with pd.option_context("display.float_format", lambda v: f"{v:.4f}",
                           "display.width", 200):
        print(f"\nTree, {avg.end_date.iloc[0]} (average basis):")
        for r in avg.sort_values("sort_order").itertuples():
            print(f"  {'  ' * r.depth}{r.label}: "
                  f"{'—' if pd.isna(r.value) else f'{r.value:.4f}'}")
    return 0


def cmd_capital(args) -> int:
    from .capital_bridge import build_capital_bridge

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        result = build_capital_bridge(store, args.ts_code)
    finally:
        store.close()
    s, checks = result["summary"], result["checks"]
    disp = s.copy()
    for c in ["noa_begin", "noa_end", "delta_noa", "delta_nfo", "capex_paid",
              "da_total", "fcf_from_oi", "fcf_simple", "fcf_articulation_diff"]:
        disp[c] = disp[c] / 1e9
    cols = ["end_date", "noa_begin", "noa_end", "delta_noa", "delta_nfo",
            "revenue_growth", "noa_growth", "reinvestment_rate", "capex_paid",
            "da_total", "capex_to_da", "fcf_from_oi", "fcf_simple", "cap_flags"]
    with pd.option_context("display.float_format", lambda v: f"{v:,.2f}",
                           "display.width", 260):
        print(f"\nCapital employed & reinvestment for {args.ts_code} "
              f"(stocks/flows in billions CNY; growth/rates as ratios):")
        print(disp[cols].to_string(index=False))
    bad = checks[checks.residual.abs() > 1.0]
    print(f"\nChecks B1–B3: {len(checks)} total, {len(bad)} with "
          f"|residual| > ¥1 (max {checks.residual.abs().max():,.2e})")
    if not bad.empty:
        print(bad.to_string(index=False))
    b = result["bridge"]
    if not b.empty:
        latest = b[b.end_date == b.end_date.max()]
        print(f"\nCapital Investment Bridge {latest.end_date.iloc[0]} (billions CNY):")
        with pd.option_context("display.float_format", lambda v: f"{v/1e9:,.2f}"):
            print(latest[["step_order", "label", "value"]].to_string(index=False))
    return 0


def cmd_residual(args) -> int:
    from .residual_income import build_residual_income

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        result = build_residual_income(store, args.ts_code,
                                       r_op=args.r_op, r_e=args.r_e)
    finally:
        store.close()
    s, checks = result["summary"], result["checks"]
    disp = s.copy()
    for c in ["oi_after_tax", "noa_begin", "capital_charge", "reoi",
              "re_common", "delta_reoi", "sales_effect", "core_margin_effect",
              "unusual_effect", "capital_charge_effect", "margin_effect",
              "turnover_effect", "growth_effect"]:
        disp[c] = disp[c] / 1e9
    cols = ["end_date", "oi_after_tax", "noa_begin", "capital_charge", "reoi",
            "re_common", "rnoa_open", "roce_open", "reoi_growth", "delta_reoi",
            "sales_effect", "core_margin_effect", "unusual_effect",
            "capital_charge_effect", "ri_flags"]
    cols2 = ["end_date", "delta_reoi", "margin_effect", "turnover_effect",
             "growth_effect"]
    with pd.option_context("display.float_format", lambda v: f"{v:,.2f}",
                           "display.width", 280):
        print(f"\nResidual income for {args.ts_code} (r_op {args.r_op:.1%}, "
              f"r_e {args.r_e:.1%} — assumptions; money in billions CNY, "
              f"opening capital):")
        print(disp[cols].to_string(index=False))
        print("\nPenman drivers of ΔReOI (billions CNY):")
        print(disp[disp.drivers_available][cols2].to_string(index=False))
    # RI1/RI2 are money (yuan), RI3/RI4 are ratios
    money = checks.check.str.startswith(("RI1", "RI2"))
    tol = money.map({True: 1.0, False: 1e-12})
    bad = checks[checks.residual.abs() > tol]
    print(f"\nChecks RI1–RI4: {len(checks)} total, {len(bad)} beyond tolerance "
          f"(¥1 money / 1e-12 ratio); max money {checks[money].residual.abs().max():,.2e}, "
          f"max ratio {checks[~money].residual.abs().max():,.2e}")
    if not bad.empty:
        print(bad.to_string(index=False))
    return 0


def cmd_market(args) -> int:
    from .client import TushareClient
    from .market import build_market_snapshot, ingest_market

    settings = get_settings()
    client = TushareClient(settings)
    store = Store(settings.db_path)
    try:
        years = list(range(args.start_year, args.end_year + 1))
        results = ingest_market(client, store, args.ts_code, years)
        snap = build_market_snapshot(store, args.ts_code)
    finally:
        store.close()
    print(f"\ndaily_basic (December windows) for {args.ts_code}:")
    for y, r in results.items():
        status = f"ERROR: {r['error']}" if r["error"] else "ok"
        print(f"  {y}: fetched {r['fetched']:3d}, inserted {r['inserted']:3d}  [{status}]")
    disp = snap.copy()
    disp["market_cap"] = disp.market_cap / 1e9
    disp["shares"] = disp.shares / 1e6
    with pd.option_context("display.float_format", lambda v: f"{v:,.4g}",
                           "display.width", 200):
        print("\nYear-end snapshots (market cap ¥B, shares M):")
        print(disp[["end_date", "trade_date", "close", "shares", "market_cap",
                    "pe_reported", "pb_reported",
                    "m1_mcap_residual_rel"]].to_string(index=False))
    return 0


def cmd_valuation(args) -> int:
    from .valuation import build_valuation

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        out = build_valuation(store, args.ts_code, r_op=args.r_op,
                              r_e=args.r_e, g=args.g)
    finally:
        store.close()
    s, checks = out["summary"], out["checks"]
    disp = s.copy()
    money = ["market_cap", "v_equity_book", "v_equity_reoi_flat",
             "v_equity_reoi_g", "v_equity_rnoa_g", "v_equity_ri",
             "aeg_actual"]
    for c in money:
        disp[c] = disp[c] / 1e9
    cols = ["end_date", "market_cap", *money[1:6], "v_to_p", "v_per_share",
            "price"]
    cols2 = ["end_date", "implied_g_reoi", "implied_g_rnoa", "implied_g_fcf",
             "implied_g_equity", "implied_r_op", "implied_r_e",
             "forward_pe_market", "forward_pe_model", "trailing_pe",
             "aeg_actual", "cum_div_growth", "val_flags"]
    with pd.option_context("display.float_format", lambda v: f"{v:,.3f}",
                           "display.width", 280):
        print(f"\nValuation for {args.ts_code} (r_op {args.r_op:.1%}, r_e "
              f"{args.r_e:.1%}, g {args.g:.1%} — assumptions; ¥B):")
        print(disp[cols].to_string(index=False))
        print("\nReverse analysis (rates as ratios):")
        print(disp[cols2].to_string(index=False))
    # M1/M2 are relative; M2 is informational (Tushare rounds pe to 4 dp)
    rel = checks.check.str.startswith(("M1", "M2"))
    tol = checks.check.map(lambda c: 1e-4 if c.startswith("M1")
                           else 1e-3 if c.startswith("M2") else 1.0)
    bad = checks[checks.residual.abs() > tol]
    print(f"\nChecks: {len(checks)} total, {len(bad)} beyond tolerance "
          f"(¥1 money / 1e-4 M1 / 1e-3 M2 relative); max money "
          f"{checks[~rel].residual.abs().max():,.2e}, max relative "
          f"{checks[rel].residual.abs().max():,.2e}")
    if not bad.empty:
        print(bad.to_string(index=False))
    b = out["bridge"]
    if not b.empty:
        latest = b[b.end_date == b.end_date.max()]
        print(f"\nValuation bridge {latest.end_date.iloc[0]} (¥B):")
        with pd.option_context("display.float_format", lambda v: f"{v/1e9:,.1f}"):
            print(latest[["step_order", "label", "value"]].to_string(index=False))
    return 0


def cmd_ingest_all(args) -> int:
    from dataclasses import replace

    from .bulk_ingest import ingest_all
    from .client import TushareClient

    settings = replace(get_settings(), max_calls_per_minute=args.cpm)
    client = TushareClient(settings)
    store = Store(settings.db_path)
    try:
        r = ingest_all(
            client, store, args.start, args.end,
            list_statuses=tuple(args.list_status.split(",")),
            report_types=tuple(args.report_types.split(",")),
            lookback_days=args.lookback_days, workers=args.workers,
            codes=args.codes.split(",") if args.codes else None,
            limit=args.limit, market=not args.no_market, force=args.force,
        )
    finally:
        store.close()
    s = r["statements"]
    print(f"\nRun {r['run_id']}: universe {r['universe']} companies "
          f"(list_status {args.list_status}), {r['companies']} ingested")
    print(f"Statement requests: {r['planned']} planned "
          f"({r['incremental']} incremental, {r['skipped']} already up to date)")
    print(f"  done {s['done']}, rows fetched {s['fetched']:,}, new rows "
          f"{s['inserted']:,}, empty responses {s['empty']}, errors {s['errors']}")
    for code, api, err in s["error_list"][:20]:
        print(f"  ERROR {code} {api}: {err[:160]}")
    if r["market"]:
        print("Year-end daily_basic:")
        for y, m in r["market"].items():
            if m.get("skipped"):
                print(f"  {y} {m['trade_date']}: already stored")
            else:
                status = f"ERROR: {m['error']}" if m["error"] else "ok"
                print(f"  {y} {m['trade_date']}: {m['fetched']:,} rows "
                      f"({m['pages']} pages), {m['inserted']:,} new  [{status}]")
    return 0 if s["errors"] == 0 else 2


def cmd_validate_all(args) -> int:
    from .bulk_validate import validate_store

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        r = validate_store(store, args.as_of)
    finally:
        store.close()
    out = settings.db_path.parent
    cov, fy = r["coverage"], r["fy"]
    cov.to_csv(out / "bulk_coverage_by_company.csv", index=False)
    r["identity_summary"].to_csv(out / "bulk_validation_summary.csv", index=False)
    r["identity_failures"].to_csv(out / "bulk_validation_failures.csv", index=False)
    r["market"].to_csv(out / "bulk_market_coverage.csv", index=False)

    listed = cov[cov.list_status == "L"]
    print(f"\nUniverse: {len(r['universe'])} companies in raw_stock_basic, "
          f"{len(listed)} listed")
    exp = listed[listed[f"fy{fy}_expected"]]
    for abbr, name in [("bs", "balancesheet"), ("is", "income"),
                       ("cf", "cashflow")]:
        none = listed[listed[f"{abbr}_rows"] == 0]
        no_fy = exp[~exp[f"{abbr}_has_fy{fy}"]]
        print(f"  {name:13s}: {len(listed) - len(none)}/{len(listed)} listed "
              f"companies have rows; FY{fy} annual present for "
              f"{len(exp) - len(no_fy)}/{len(exp)} listed by {fy}-12-31"
              + (f"; missing e.g. {', '.join(no_fy.ts_code[:8])}" if len(no_fy) else ""))
    s = r["identity_summary"]
    piv = s.pivot_table(index="check", columns="status", values="rows",
                        aggfunc="sum", fill_value=0)
    print(f"\nIdentity checks over all stored rows (PASS/FAIL/SKIP):\n{piv.to_string()}")
    if not r["identity_failures"].empty:
        by = (s[s.status == "FAIL"].groupby(["check", "comp_type"]).rows.sum())
        print(f"\nFAIL rows by comp_type (1 一般企业 2 银行 3 保险 4 证券) — "
              f"reported, not corrected:\n{by.to_string()}")
    m = r["market"]
    if not m.empty:
        print(f"\nYear-end daily_basic coverage of listed companies:\n"
              f"{m[['trade_date', 'rows', 'listed_by_date', 'present', 'absent']].to_string(index=False)}")
    e = r["errors"]
    print(f"\nRequest errors in latest run: {len(e)}")
    if not e.empty:
        print(e[["ts_code", "api", "error"]].head(20).to_string(index=False))
    print(f"\nReports written to {out}/bulk_*.csv")
    return 0


def cmd_analyze_all(args) -> int:
    from pathlib import Path

    from .bulk_analyze import Params, analyze_all, write_reports

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        result = analyze_all(
            store, Params(out_dir=Path(args.out), tax_rate=args.tax_rate,
                          r_op=args.r_op, r_e=args.r_e, g=args.g),
            codes=args.codes.split(",") if args.codes else None,
            industry=args.industry, limit=args.limit, force=args.force)
        paths = write_reports(store, settings.db_path.parent)
    finally:
        store.close()
    c = result.counts
    print(f"\nanalyze-all {result.run_id}: ok {c['ok']}, failed {c['failed']}, "
          f"skipped {c['skipped']}, unchanged {c['unchanged']} "
          f"({result.seconds / 60:,.1f} min)")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    return 0


def cmd_summary(args) -> int:
    settings = get_settings()
    store = Store(settings.db_path)
    try:
        print(store.summary().to_string(index=False))
    finally:
        store.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest")
    pi.add_argument("ts_code")
    pi.add_argument("--start", default="20150101")
    pi.add_argument("--end", default=date.today().strftime("%Y%m%d"))
    pi.add_argument("--report-types", dest="report_types", default="1,6,4,5")
    pi.set_defaults(fn=cmd_ingest)

    pv = sub.add_parser("validate")
    pv.add_argument("ts_code")
    pv.set_defaults(fn=cmd_validate)

    pm = sub.add_parser("map")
    pm.add_argument("ts_code")
    pm.set_defaults(fn=cmd_map)

    pr = sub.add_parser("reformulate")
    pr.add_argument("ts_code")
    pr.add_argument("--tax-rate", dest="tax_rate", type=float, default=0.25)
    pr.set_defaults(fn=cmd_reformulate)

    pra = sub.add_parser("ratios")
    pra.add_argument("ts_code")
    pra.set_defaults(fn=cmd_ratios)

    pw = sub.add_parser("wc")
    pw.add_argument("ts_code")
    pw.set_defaults(fn=cmd_wc)

    pc = sub.add_parser("cash")
    pc.add_argument("ts_code")
    pc.set_defaults(fn=cmd_cash)

    pem = sub.add_parser("econmap")
    pem.add_argument("ts_code")
    pem.set_defaults(fn=cmd_econmap)

    pdt = sub.add_parser("drivertree")
    pdt.add_argument("ts_code")
    pdt.set_defaults(fn=cmd_drivertree)

    pcap = sub.add_parser("capital")
    pcap.add_argument("ts_code")
    pcap.set_defaults(fn=cmd_capital)

    pri = sub.add_parser("residual")
    pri.add_argument("ts_code")
    pri.add_argument("--r-op", dest="r_op", type=float, default=0.08)
    pri.add_argument("--r-e", dest="r_e", type=float, default=0.08)
    pri.set_defaults(fn=cmd_residual)

    pmk = sub.add_parser("market")
    pmk.add_argument("ts_code")
    pmk.add_argument("--start-year", dest="start_year", type=int, default=2014)
    pmk.add_argument("--end-year", dest="end_year", type=int,
                     default=date.today().year - 1)
    pmk.set_defaults(fn=cmd_market)

    pva = sub.add_parser("valuation")
    pva.add_argument("ts_code")
    pva.add_argument("--r-op", dest="r_op", type=float, default=0.08)
    pva.add_argument("--r-e", dest="r_e", type=float, default=0.08)
    pva.add_argument("--g", dest="g", type=float, default=0.03)
    pva.set_defaults(fn=cmd_valuation)

    pe = sub.add_parser("export")
    pe.add_argument("ts_code")
    pe.add_argument("--out", default="app/public/data")
    pe.set_defaults(fn=cmd_export)

    pco = sub.add_parser("companies", help="export the company picker index only")
    pco.add_argument("--out", default="app/public/data")
    pco.set_defaults(fn=cmd_companies)

    psc = sub.add_parser("screens", help="export the 好生意榜单 cross-company screens")
    psc.add_argument("--out", default="app/public/data")
    psc.set_defaults(fn=cmd_screens)

    ppg = sub.add_parser("pages", help="stage (and with --publish, push) the GitHub Pages sites")
    ppg.add_argument("--out", default=None, help="staging root (default build/pages)")
    ppg.add_argument("--skip-build", action="store_true", help="reuse the staged app build")
    ppg.add_argument("--publish", action="store_true", help="force-push each site's gh-pages branch")
    ppg.set_defaults(fn=cmd_pages)

    pia = sub.add_parser("ingest-all")
    pia.add_argument("--start", default="20150101",
                     help="ann_date window start (as for `ingest`)")
    pia.add_argument("--end", default=date.today().strftime("%Y%m%d"))
    pia.add_argument("--list-status", dest="list_status", default="L",
                     help="stock_basic list_status values: L listed, D delisted, P paused")
    pia.add_argument("--report-types", dest="report_types", default="1",
                     help="gateway serves only 1 (consolidated)")
    pia.add_argument("--lookback-days", dest="lookback_days", type=int,
                     default=365)
    pia.add_argument("--workers", type=int, default=4)
    pia.add_argument("--cpm", type=int, default=240,
                     help="max calls per minute across all workers")
    pia.add_argument("--codes", help="comma-separated ts_codes (subset run)")
    pia.add_argument("--limit", type=int, help="first N companies only (trial run)")
    pia.add_argument("--no-market", dest="no_market", action="store_true",
                     help="skip year-end daily_basic")
    pia.add_argument("--force", action="store_true",
                     help="ignore ingest_log coverage and refetch full windows")
    pia.set_defaults(fn=cmd_ingest_all)

    pval = sub.add_parser("validate-all")
    pval.add_argument("--as-of", dest="as_of", default=None)
    pval.set_defaults(fn=cmd_validate_all)

    paa = sub.add_parser("analyze-all", help="run Modules 2–12 + export for stored companies")
    paa.add_argument("--codes", help="comma-separated ts_codes (subset run)")
    paa.add_argument("--industry", help="stock_basic industry, e.g. 白酒")
    paa.add_argument("--limit", type=int, help="first N companies only (trial run)")
    paa.add_argument("--force", action="store_true",
                     help="rerun companies whose inputs are unchanged")
    paa.add_argument("--out", default="app/public/data")
    paa.add_argument("--tax-rate", dest="tax_rate", type=float, default=0.25)
    paa.add_argument("--r-op", dest="r_op", type=float, default=0.08)
    paa.add_argument("--r-e", dest="r_e", type=float, default=0.08)
    paa.add_argument("--g", dest="g", type=float, default=0.03)
    paa.set_defaults(fn=cmd_analyze_all)

    ps = sub.add_parser("summary")
    ps.set_defaults(fn=cmd_summary)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
