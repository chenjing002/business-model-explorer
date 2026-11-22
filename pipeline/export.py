"""Module 7 — Export validated analytical data to a per-company JSON bundle.

The frontend performs NO financial math: everything here is precomputed by
Modules 1–6 and exported as-is. NaN becomes null (missing stays missing).
Schema is versioned; breaking changes bump SCHEMA_VERSION.
"""
from __future__ import annotations

import gzip
import json
import re
from tempfile import NamedTemporaryFile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .calculation_details import build_calculation_details
from .overview import build_overview
from .store import Store

SCHEMA_VERSION = 1

# table -> (bundle key, filter to annual rows?)
EXPORT_TABLES = {
    "reformulated_bs": ("reformulated_bs", True),
    "reformulated_is": ("reformulated_is", True),
    "ratios_annual": ("ratios", False),
    "working_capital_annual": ("working_capital", False),
    "cash_bridge_annual": ("cash_bridge", False),
    "cash_summary_annual": ("cash_summary", False),
    "reformulated_bs_components": ("bs_components", True),
    "reclass_decisions": ("reclass_decisions", False),
    "econ_map_nodes": ("econ_map_nodes", False),
    "econ_map_checks": ("econ_map_checks", False),
    "econ_evolution_groups": ("econ_evolution_groups", False),
    "econ_evolution_flows": ("econ_evolution_flows", False),
    "econ_evolution_checks": ("econ_evolution_checks", False),
    "driver_tree_nodes": ("driver_tree_nodes", False),
    "driver_tree_checks": ("driver_tree_checks", False),
    "capital_bridge_annual": ("capital_bridge", False),
    "capital_summary_annual": ("capital_summary", False),
    "capital_bridge_checks": ("capital_checks", False),
    "residual_income_annual": ("residual_income", False),
    "value_bridge_annual": ("value_bridge", False),
    "residual_income_checks": ("ri_checks", False),
    "market_snapshot_annual": ("market_snapshot", False),
    "valuation_annual": ("valuation", False),
    "valuation_bridge_annual": ("valuation_bridge", False),
    "valuation_grid": ("valuation_grid", False),
    "valuation_reverse_curve": ("valuation_curve", False),
    "valuation_checks": ("valuation_checks", False),
}


# Empty when the company has no year-end price yet (listed after the latest
# year end, or suspended on every year-end trading day); exported as [].
MARKET_DEPENDENT_TABLES = {"market_snapshot_annual", "valuation_bridge_annual",
                           "valuation_grid", "valuation_reverse_curve"}
# Tables that are legitimately empty for some companies, exported as []:
# the market-dependent ones above, and the value-creation bridge, which needs
# revenue in two consecutive years (pre-revenue companies, e.g. 688759.SH, get
# residual_income rows flagged bridge_unavailable_no_revenue instead).
MAY_BE_EMPTY_TABLES = MARKET_DEPENDENT_TABLES | {"value_bridge_annual"}


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe records; NaN -> None (null)."""
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


INDEX_FILE = "companies.json"
INDEX_COLUMNS = ["ts_code", "name", "industry", "cnspell", "market"]
# Bundles are gzipped: ~2.4 MB of JSON per company compresses to ~0.35 MB,
# which keeps thousands of companies servable as static files.
BUNDLE_SUFFIX = ".json.gz"
_BUNDLE_NAME = re.compile(r"^[A-Z0-9]{1,12}\.[A-Z0-9]{1,8}\.json\.gz$")


def bundle_path(out_dir: Path | str, ts_code: str) -> Path:
    return Path(out_dir) / f"{ts_code}{BUNDLE_SUFFIX}"


def _table_exists(store: Store, table: str) -> bool:
    return bool(store.con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
        [table]).fetchall()[0][0])


def _write_json(payload: dict, out_path: Path, compress: bool = False) -> None:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    with NamedTemporaryFile(mode="wb", dir=out_path.parent, delete=False) as f:
        temporary = Path(f.name)
        try:
            data = text.encode("utf-8")
            # mtime=0: identical content gives identical bytes
            f.write(gzip.compress(data, compresslevel=6, mtime=0) if compress else data)
            f.close()
            temporary.chmod(0o644)
            temporary.replace(out_path)
        finally:
            temporary.unlink(missing_ok=True)


def export_company_index(store: Store, out_dir: Path | str) -> Path:
    """Company picker index: the stored universe plus which bundles exist.

    `analyzed` lists bundle files actually present in out_dir, so the picker
    never offers analysis the frontend cannot load. `unavailable` gives the
    latest batch-analysis reason for companies without a bundle (financial
    statements, no annual report, pipeline error with its step); companies
    absent from both have simply not been run. `check_failures` lists the
    identity-check families that failed for an analysed company — reported,
    never corrected. Industry stays null when stock_basic does not disclose
    one; bundles outside the universe are kept with null name/industry.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    analyzed = sorted(p.name[:-len(BUNDLE_SUFFIX)] for p in out_dir.iterdir()
                      if _BUNDLE_NAME.match(p.name))
    if _table_exists(store, "raw_stock_basic"):
        universe = store.con.execute(
            f"SELECT {', '.join(INDEX_COLUMNS)} FROM raw_stock_basic "
            "QUALIFY row_number() OVER (PARTITION BY ts_code ORDER BY _fetched_at DESC) = 1 "
            "ORDER BY ts_code").df()
    else:
        universe = pd.DataFrame(columns=INDEX_COLUMNS)
    missing = sorted(set(analyzed) - set(universe.ts_code))
    if missing:
        universe = pd.concat([universe, pd.DataFrame({"ts_code": missing})],
                             ignore_index=True)
    unavailable: dict[str, dict] = {}
    check_failures: dict[str, list[str]] = {}
    if _table_exists(store, "analysis_log"):
        latest = store.con.execute(
            "SELECT ts_code, status, reason, step, check_failures FROM analysis_log "
            "QUALIFY row_number() OVER (PARTITION BY ts_code ORDER BY finished_at DESC) = 1"
        ).fetchall()
        have = set(analyzed)
        for code, status, reason, step, failures in latest:
            if code in have:
                if status == "ok" and failures:
                    check_failures[code] = failures.split(",")
            elif status in ("skipped", "failed"):
                unavailable[code] = {"reason": reason, "step": step}
    _write_json({
        "schema_version": SCHEMA_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": "raw_stock_basic (Tushare stock_basic)",
        "analyzed": analyzed,
        "unavailable": dict(sorted(unavailable.items())),
        "check_failures": dict(sorted(check_failures.items())),
        "companies": _records(universe.reindex(columns=INDEX_COLUMNS)),
    }, out_dir / INDEX_FILE)
    return out_dir / INDEX_FILE


def export_company(store: Store, ts_code: str, out_dir: Path | str,
                   refresh_index: bool = True) -> Path:
    bundle: dict = {
        "schema_version": SCHEMA_VERSION,
        "ts_code": ts_code,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "unit": "CNY_yuan",
        "conventions": {
            "capital_basis": "rows labeled 'average' or 'opening' in ratios",
            "tax_rate": "statutory-rate assumption column tax_rate_assumed",
            "cfo": "CAS: interest received=investing, interest/dividends paid=financing",
            "missing": "null means not disclosed — never zero",
        },
    }
    for table, (key, annual_only) in EXPORT_TABLES.items():
        exists = store.con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
            [table]).fetchall()[0][0]
        if not exists:
            raise RuntimeError(
                f"Table {table} missing — run the full pipeline first "
                "(ingest → map → reformulate → ratios → wc → cash).")
        df = store.con.execute(
            f"SELECT * FROM {table} WHERE ts_code = ?", [ts_code]).df()
        if annual_only and "end_date" in df.columns:
            keep = df.end_date.str.endswith("1231")
            if "period_kind" in df.columns:
                keep &= df.period_kind.isin(["cumulative", "point"]) \
                    | df.period_kind.isna()
            df = df[keep]
        if df.empty and table not in MAY_BE_EMPTY_TABLES:
            raise RuntimeError(f"No rows in {table} for {ts_code}.")
        bundle[key] = _records(df.sort_values("end_date")
                               if "end_date" in df.columns else df)

    if store.con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name='std_facts'"
    ).fetchone()[0]:
        facts = store.con.execute(
            "SELECT * FROM std_facts WHERE ts_code = ? AND report_type = '1' "
            "AND value_type = 'reported' AND end_date LIKE '%1231'", [ts_code]
        ).df()
        bundle["calculation_details"] = build_calculation_details(store, bundle, facts)

    bundle["overview"] = build_overview(bundle)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = bundle_path(out_dir, ts_code)
    _write_json(bundle, out_path, compress=True)
    # the pre-gzip bundle of the same company would otherwise go stale
    (out_dir / f"{ts_code}.json").unlink(missing_ok=True)
    if refresh_index:
        export_company_index(store, out_dir)
    return out_path
