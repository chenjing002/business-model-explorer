"""Module 16 — Run the analysis pipeline (Modules 2–12) for every stored company.

Per company, in order: map → reformulate → ratios → wc → cash → econmap →
evolution → drivertree → capital → residual → market → valuation → export
(gzipped bundle). Every company runs in its own try: a failure records the
step and the error in `analysis_log` and the batch moves on.

Eligibility, decided from the stored raw statements (never guessed):
- general-business statements only (comp_type 1). Banks (2), insurers (3),
  brokers (4) and other financials (7) have different statement structures;
  their mapping is not built, so they are skipped with reason `financial`.
  A company whose comp_type changed is judged by its latest annual report.
- at least one consolidated annual report (end_date ****1231), else
  `no_annual_report`.

Identity checks are summarised per company and family with the tolerances
the single-company CLI prints (`analysis_checks`, annual rows only; E1/E2 use
the L1/L2 ¥1M of the totals they difference);
failures are reported, never corrected. L4 — the company's own indirect-method
bridge (NI + noncash + ΔOWC vs CFO) — is counted as a *diagnostic* family: a
residual there means the supplementary disclosure does not add up, not that
the reformulation broke, so it never enters `check_failures`. E4 and M2 are
informational in the CLI and are not counted.

Incremental: a company is skipped when its input fingerprint — raw row count
and latest fetch time across the three statements and daily_basic, plus a
hash of the mapping/override configs and the analysis module sources — is
unchanged since its last logged run (and its bundle still exists when that
run succeeded). `--force` reruns everything.
"""
from __future__ import annotations

import hashlib
import logging
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .capital_bridge import build_capital_bridge
from .cash_reconciliation import build_cash_reconciliation
from .driver_tree import build_driver_tree
from .econ_evolution import build_econ_evolution
from .economics_map import build_economics_map
from .export import bundle_path, export_company, export_company_index
from .mapping import build_std_facts
from .market import build_market_snapshot
from .ratios import build_ratios
from .reformulate import build_reformulated
from .residual_income import build_residual_income
from .screens import export_screens
from .store import Store
from .valuation import build_valuation
from .working_capital import build_working_capital

log = logging.getLogger(__name__)

PACKAGE = Path(__file__).resolve().parent
CONFIG = PACKAGE.parent / "config"
# Inputs whose change invalidates every company's results.
FINGERPRINT_FILES = [
    CONFIG / "mapping_tushare.yml", CONFIG / "overrides.yml", CONFIG / "overview_disclosures.yml",
    *(PACKAGE / f"{name}.py" for name in [
        "mapping", "reformulate", "ratios", "working_capital", "cash_reconciliation",
        "economics_map", "econ_evolution", "driver_tree", "capital_bridge",
        "residual_income", "market", "valuation", "export", "overview",
        "calculation_details", "fields"]),
]
ELIGIBLE_COMP_TYPE = "1"

# family -> (table, residual column or None for a `check` table, tolerance, relative)
# Tolerances mirror the single-company CLI output.
CHECK_FAMILIES = {
    "R1": ("reformulated_bs", "r1_assets_residual", 1e6),
    "R2": ("reformulated_bs", "r2_liab_residual", 1e6),
    "R3": ("reformulated_bs", "r3_cse_residual", 1e6),
    "R4": ("reformulated_is", "r4_pretax_residual", 1e6),
    "L": ("econ_map_checks", None, 1e6),
    "L4": ("econ_map_checks", None, 1e6),
    "E": ("econ_evolution_checks", None, 1e-3),
    "T": ("driver_tree_checks", None, 1e-12),
    "B": ("capital_bridge_checks", None, 1.0),
    "RI": ("residual_income_checks", None, None),
    "V": ("valuation_checks", None, None),
}
INFORMATIONAL_CHECKS = ("E4", "M2")
DIAGNOSTIC_FAMILIES = ("L4",)


def _in_family(family: str, check: str) -> bool:
    if family == "L":
        return not check.startswith("L4")
    if family == "L4":
        return check.startswith("L4")
    return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def code_fingerprint(files: list[Path] = FINGERPRINT_FILES) -> str:
    h = hashlib.sha1()
    for path in files:
        h.update(path.name.encode())
        h.update(path.read_bytes() if path.exists() else b"<missing>")
    return h.hexdigest()


def _tolerance(family: str, check: str) -> float | None:
    """None = informational, not counted."""
    if check.startswith(INFORMATIONAL_CHECKS):
        return None
    if family == "RI":
        return 1.0 if check.startswith(("RI1", "RI2")) else 1e-12
    if family == "V":
        return 1e-4 if check.startswith("M1") else 1.0
    if family == "E" and check.startswith(("E1", "E2")):
        # E1/E2 are year-on-year deltas of the totals L1/L2 check at ¥1M; with
        # the CLI's ¥0.001 a sub-¥1M R1 residual that passes everywhere else
        # failed here (median ¥1,150 on the first full run). E3 is exact.
        return 1e6
    return CHECK_FAMILIES[family][2]


def summarize_checks(store: Store, ts_code: str) -> pd.DataFrame:
    """One row per check family: rows checked, failures, max |residual|."""
    rows = []
    for family, (table, column, _) in CHECK_FAMILIES.items():
        if column:
            where = "ts_code = ? AND end_date LIKE '%1231'"
            if table == "reformulated_is":
                where += " AND period_kind = 'cumulative'"
            values = [(family, v) for (v,) in store.con.execute(
                f"SELECT {column} FROM {table} WHERE {where}", [ts_code]).fetchall()]
        else:
            values = [(check, v) for check, v in store.con.execute(
                f'SELECT "check", residual FROM {table} WHERE ts_code = ?', [ts_code]).fetchall()]
        checked = failed = 0
        worst = 0.0
        for check, value in values:
            if not _in_family(family, check):
                continue
            tol = _tolerance(family, check)
            if tol is None or value is None or pd.isna(value):
                continue
            checked += 1
            worst = max(worst, abs(value))
            failed += abs(value) > tol
        rows.append(dict(ts_code=ts_code, family=family, checked=checked,
                         failed=failed, max_abs_residual=worst if checked else None))
    return pd.DataFrame(rows)


def eligibility(store: Store) -> pd.DataFrame:
    """Per stored company: latest annual comp_type and annual report count."""
    return store.con.execute("""
        SELECT ts_code,
               arg_max(comp_type, end_date) AS comp_type,
               count(DISTINCT end_date) AS n_annual,
               min(end_date) AS first_end, max(end_date) AS last_end
        FROM raw_balancesheet
        WHERE report_type = '1' AND end_date LIKE '%1231'
        GROUP BY ts_code""").df()


def input_fingerprints(store: Store, code_hash: str) -> dict[str, str]:
    parts = " UNION ALL ".join(
        f"SELECT ts_code, _fetched_at FROM {t}"
        for t in ["raw_balancesheet", "raw_income", "raw_cashflow", "raw_daily_basic"]
        if _exists(store, t))
    rows = store.con.execute(
        f"SELECT ts_code, count(*), max(_fetched_at) FROM ({parts}) GROUP BY ts_code").fetchall()
    return {code: hashlib.sha1(f"{code_hash}|{n}|{latest}".encode()).hexdigest()
            for code, n, latest in rows}


def _exists(store: Store, table: str) -> bool:
    return bool(store.con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
        [table]).fetchall()[0][0])


def _write_rows(store: Store, table: str, df: pd.DataFrame, ts_code: str | None = None) -> None:
    store.con.register("_df", df)
    if _exists(store, table):
        if ts_code is not None:
            store.con.execute(f"DELETE FROM {table} WHERE ts_code = ?", [ts_code])
        store.con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM _df")
    else:
        store.con.execute(f"CREATE TABLE {table} AS SELECT * FROM _df")
    store.con.unregister("_df")


LOG_COLUMNS = {"ts_code": "VARCHAR", "run_id": "VARCHAR", "status": "VARCHAR",
               "reason": "VARCHAR", "step": "VARCHAR", "error": "VARCHAR",
               "fingerprint": "VARCHAR", "n_annual": "BIGINT", "first_end": "VARCHAR",
               "last_end": "VARCHAR", "check_failures": "VARCHAR",
               "seconds": "DOUBLE", "finished_at": "VARCHAR"}


def _log(store: Store, row: dict) -> None:
    if not _exists(store, "analysis_log"):
        cols = ", ".join(f"{c} {t}" for c, t in LOG_COLUMNS.items())
        store.con.execute(f"CREATE TABLE analysis_log ({cols})")
    store.con.execute(
        f"INSERT INTO analysis_log ({', '.join(LOG_COLUMNS)}) VALUES "
        f"({', '.join('?' for _ in LOG_COLUMNS)})",
        [row.get(c) for c in LOG_COLUMNS])


def latest_log(store: Store) -> pd.DataFrame:
    if not _exists(store, "analysis_log"):
        return pd.DataFrame(columns=list(LOG_COLUMNS))
    return store.con.execute(
        "SELECT * FROM analysis_log QUALIFY row_number() OVER "
        "(PARTITION BY ts_code ORDER BY finished_at DESC) = 1").df()


@dataclass
class Params:
    out_dir: Path
    tax_rate: float = 0.25
    r_op: float = 0.08
    r_e: float = 0.08
    g: float = 0.03


def analyze_company(store: Store, ts_code: str, params: Params) -> None:
    """Run every analysis step for one company; raises on the first failure
    with `step` attached so the caller can log where it stopped."""
    steps = [
        ("map", lambda: build_std_facts(store, ts_code)),
        ("reformulate", lambda: build_reformulated(store, ts_code, tax_rate=params.tax_rate)),
        ("ratios", lambda: build_ratios(store, ts_code)),
        ("wc", lambda: build_working_capital(store, ts_code)),
        ("cash", lambda: build_cash_reconciliation(store, ts_code)),
        ("econmap", lambda: build_economics_map(store, ts_code)),
        ("evolution", lambda: build_econ_evolution(store, ts_code)),
        ("drivertree", lambda: build_driver_tree(store, ts_code)),
        ("capital", lambda: build_capital_bridge(store, ts_code)),
        ("residual", lambda: build_residual_income(store, ts_code, r_op=params.r_op, r_e=params.r_e)),
        ("market", lambda: build_market_snapshot(store, ts_code)),
        ("valuation", lambda: build_valuation(store, ts_code, r_op=params.r_op,
                                              r_e=params.r_e, g=params.g)),
        ("export", lambda: export_company(store, ts_code, params.out_dir, refresh_index=False)),
    ]
    for name, run in steps:
        try:
            run()
        except Exception as error:  # noqa: BLE001 — recorded per company, batch continues
            error.step = name  # type: ignore[attr-defined]
            raise


@dataclass
class BatchResult:
    run_id: str
    counts: dict = field(default_factory=dict)
    seconds: float = 0.0


def analyze_all(store: Store, params: Params, codes: list[str] | None = None,
                industry: str | None = None, limit: int | None = None,
                force: bool = False, progress_every: int = 100) -> BatchResult:
    run_id = new_run_id()
    started = time.time()
    elig = eligibility(store)
    if _exists(store, "raw_stock_basic"):
        universe = store.con.execute(
            "SELECT ts_code, industry FROM raw_stock_basic QUALIFY row_number() OVER "
            "(PARTITION BY ts_code ORDER BY _fetched_at DESC) = 1").df()
    else:
        universe = pd.DataFrame({"ts_code": elig.ts_code, "industry": None})
    targets = universe.merge(elig, on="ts_code", how="left")
    if codes:
        targets = targets[targets.ts_code.isin(codes)]
    if industry:
        targets = targets[targets.industry == industry]
    targets = targets.sort_values("ts_code")
    if limit:
        targets = targets.head(limit)

    code_hash = code_fingerprint()
    fingerprints = input_fingerprints(store, code_hash)
    previous = latest_log(store).set_index("ts_code")
    counts = {"ok": 0, "failed": 0, "skipped": 0, "unchanged": 0}
    total = len(targets)
    log.info("analyze-all %s: %d companies", run_id, total)

    for i, t in enumerate(targets.itertuples(index=False), start=1):
        code = t.ts_code
        fp = fingerprints.get(code)
        row = dict(ts_code=code, run_id=run_id, fingerprint=fp,
                   n_annual=None if pd.isna(t.n_annual) else int(t.n_annual),
                   first_end=None if pd.isna(t.first_end) else t.first_end,
                   last_end=None if pd.isna(t.last_end) else t.last_end)
        if not force and code in previous.index and previous.at[code, "fingerprint"] == fp \
                and (previous.at[code, "status"] != "ok" or bundle_path(params.out_dir, code).exists()):
            counts["unchanged"] += 1
        elif pd.isna(t.n_annual) or not t.n_annual:
            counts["skipped"] += 1
            _log(store, {**row, "status": "skipped", "reason": "no_annual_report",
                         "seconds": 0.0, "finished_at": _now()})
        elif t.comp_type != ELIGIBLE_COMP_TYPE:
            counts["skipped"] += 1
            _log(store, {**row, "status": "skipped", "reason": "financial",
                         "error": f"comp_type {t.comp_type}", "seconds": 0.0, "finished_at": _now()})
        else:
            t0 = time.time()
            try:
                analyze_company(store, code, params)
            except Exception as error:  # noqa: BLE001
                counts["failed"] += 1
                bundle_path(params.out_dir, code).unlink(missing_ok=True)
                _log(store, {**row, "status": "failed", "reason": "error",
                             "step": getattr(error, "step", None),
                             "error": f"{type(error).__name__}: {error}"[:2000],
                             "seconds": time.time() - t0, "finished_at": _now()})
                log.warning("%s failed at %s: %s", code, getattr(error, "step", "?"), error)
                log.debug("%s", traceback.format_exc())
            else:
                checks = summarize_checks(store, code)
                _write_rows(store, "analysis_checks", checks.assign(run_id=run_id), code)
                failed = checks[(checks.failed > 0)
                                & ~checks.family.isin(DIAGNOSTIC_FAMILIES)].family.tolist()
                counts["ok"] += 1
                _log(store, {**row, "status": "ok", "check_failures": ",".join(failed) or None,
                             "seconds": time.time() - t0, "finished_at": _now()})
        if i % progress_every == 0 or i == total:
            elapsed = time.time() - started
            eta = elapsed / i * (total - i)
            log.info("%d/%d  ok %d · failed %d · skipped %d · unchanged %d  "
                     "(%.0f s elapsed, ~%.0f min left)", i, total, counts["ok"],
                     counts["failed"], counts["skipped"], counts["unchanged"],
                     elapsed, eta / 60)
    export_company_index(store, params.out_dir)
    try:  # cross-company screens read every ok company's tables, not just this run's
        export_screens(store, params.out_dir)
    except Exception:
        log.exception("screens export failed; company bundles and index are unaffected")
    return BatchResult(run_id=run_id, counts=counts, seconds=time.time() - started)


def write_reports(store: Store, out_dir: Path) -> dict[str, Path]:
    """CSV reports next to the database: status counts, failures, check failures."""
    out_dir.mkdir(parents=True, exist_ok=True)
    latest = latest_log(store)
    paths = {}
    summary = (latest.groupby(["status", "reason"], dropna=False).size()
               .rename("companies").reset_index())
    paths["summary"] = out_dir / "analysis_summary.csv"
    summary.to_csv(paths["summary"], index=False)
    failures = latest[latest.status == "failed"][["ts_code", "step", "error", "finished_at"]]
    paths["failures"] = out_dir / "analysis_failures.csv"
    failures.to_csv(paths["failures"], index=False)
    if _exists(store, "analysis_checks"):
        checks = store.con.execute("""
            SELECT family, count(*) FILTER (WHERE failed > 0) AS companies_failed,
                   sum(failed) AS rows_failed, sum(checked) AS rows_checked
            FROM analysis_checks GROUP BY family ORDER BY family""").df()
        detail = store.con.execute(
            "SELECT * FROM analysis_checks WHERE failed > 0 ORDER BY family, ts_code").df()
    else:
        checks = detail = pd.DataFrame()
    paths["checks"] = out_dir / "analysis_check_summary.csv"
    checks.to_csv(paths["checks"], index=False)
    paths["check_failures"] = out_dir / "analysis_check_failures.csv"
    detail.to_csv(paths["check_failures"], index=False)
    return paths
