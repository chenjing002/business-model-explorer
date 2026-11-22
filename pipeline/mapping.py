"""Standardized mapping layer: raw wide Tushare rows -> long std_facts table.

Rules:
- Driven by config/mapping_tushare.yml (editable; carries default Penman
  classes that Module 3 consumes — judgmental items are noted, not truth).
- One fact per non-null mapped field on the *preferred* row per
  (ts_code, end_date, report_type). Nulls emit nothing (never imputed).
- Preferred row = highest update_flag, then latest f_ann_date, then latest
  fetch. Superseded rows remain untouched in raw_* tables.
- Income/cashflow are cumulative YTD; single-quarter values are DERIVED
  facts (value_type='calculated'), per-share fields excluded.
- std_facts is deterministic from raw + config: rebuilt with CREATE OR REPLACE.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from .config import PROJECT_ROOT
from .store import Store

DEFAULT_MAPPING_PATH = PROJECT_ROOT / "config" / "mapping_tushare.yml"

ID_FIELDS = {
    "ts_code", "ann_date", "f_ann_date", "end_date", "report_type",
    "comp_type", "end_type", "update_flag",
}

FACT_COLUMNS = [
    "ts_code", "end_date", "report_type", "statement", "concept",
    "raw_field", "label_zh", "penman_class", "note", "value",
    "value_type", "period_kind", "basis", "unit",
    "f_ann_date", "update_flag", "source_row_hash", "mapping_version",
]


def load_mapping(path: Path | str = DEFAULT_MAPPING_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for stmt in ("balancesheet", "income", "cashflow"):
        if stmt not in cfg:
            raise ValueError(f"Mapping config missing statement: {stmt}")
        concepts: dict[str, str] = {}
        for field, spec in cfg[stmt]["fields"].items():
            if "concept" not in spec or "class" not in spec:
                raise ValueError(f"{stmt}.{field}: needs 'concept' and 'class'")
            if spec["concept"] in concepts:
                raise ValueError(
                    f"{stmt}: concept '{spec['concept']}' mapped from both "
                    f"'{concepts[spec['concept']]}' and '{field}'"
                )
            concepts[spec["concept"]] = field
    return cfg


def select_preferred(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (ts_code, end_date, report_type): the latest disclosure.

    Order: update_flag desc, f_ann_date desc, _fetched_at desc.
    """
    if df.empty:
        return df
    d = df.copy()
    d["_uf"] = pd.to_numeric(d.get("update_flag"), errors="coerce").fillna(-1)
    d["_fad"] = d.get("f_ann_date", pd.Series(index=d.index)).fillna("")
    d["_fat"] = d.get("_fetched_at", pd.Series(index=d.index)).fillna("")
    d = d.sort_values(["_uf", "_fad", "_fat"], ascending=False)
    d = d.drop_duplicates(subset=["ts_code", "end_date", "report_type"], keep="first")
    return d.drop(columns=["_uf", "_fad", "_fat"]).sort_values("end_date").reset_index(drop=True)


def build_facts(raw_df: pd.DataFrame, cfg: dict, statement: str) -> pd.DataFrame:
    """Wide preferred rows -> long facts. Only non-null mapped fields emit."""
    if raw_df.empty:
        return pd.DataFrame(columns=FACT_COLUMNS)
    stmt_cfg = cfg[statement]
    period_kind = stmt_cfg["period_kind"]
    preferred = select_preferred(raw_df)
    records = []
    for _, row in preferred.iterrows():
        for field, spec in stmt_cfg["fields"].items():
            val = row.get(field)
            if pd.isna(val):
                continue
            records.append(dict(
                ts_code=row["ts_code"],
                end_date=str(row["end_date"]),
                report_type=str(row["report_type"]),
                statement=statement,
                concept=spec["concept"],
                raw_field=field,
                label_zh=spec.get("label_zh", ""),
                penman_class=spec["class"],
                note=spec.get("note", ""),
                value=float(val),
                value_type="reported",
                period_kind=period_kind,
                basis="consolidated" if str(row["report_type"]) == "1" else "parent",
                unit=("CNY_yuan_per_share" if spec["class"] == "per_share"
                      else cfg.get("unit", "CNY_yuan")),
                f_ann_date=str(row.get("f_ann_date", "")),
                update_flag=str(row.get("update_flag", "")),
                source_row_hash=row.get("_row_hash", ""),
                mapping_version=str(cfg.get("version", "")),
            ))
    return pd.DataFrame(records, columns=FACT_COLUMNS)


QUARTER_ORDER = ["0331", "0630", "0930", "1231"]


def derive_single_quarters(facts: pd.DataFrame) -> pd.DataFrame:
    """Qn single = cum(Qn) - cum(Qn-1); Q1 single = cum(Q1).

    Only for cumulative facts with both periods reported; per_share excluded
    (not additive). Output value_type='calculated', period_kind='single_quarter'.
    """
    cum = facts[
        (facts.period_kind == "cumulative") & (facts.penman_class != "per_share")
    ]
    if cum.empty:
        return pd.DataFrame(columns=FACT_COLUMNS)
    records = []
    keys = ["ts_code", "report_type", "statement", "concept"]
    for _, g in cum.groupby(keys):
        by_period = {r.end_date: r for r in g.itertuples()}
        for end_date, row in by_period.items():
            year, mmdd = end_date[:4], end_date[4:]
            if mmdd not in QUARTER_ORDER:
                continue
            qi = QUARTER_ORDER.index(mmdd)
            if qi == 0:
                sq_value = row.value
            else:
                prev = by_period.get(year + QUARTER_ORDER[qi - 1])
                if prev is None:
                    continue  # prior cumulative missing -> no derived fact
                sq_value = row.value - prev.value
            rec = {c: getattr(row, c) for c in FACT_COLUMNS}
            rec.update(value=sq_value, value_type="calculated",
                       period_kind="single_quarter")
            records.append(rec)
    return pd.DataFrame(records, columns=FACT_COLUMNS)


def mapping_coverage(raw_df: pd.DataFrame, cfg: dict, statement: str) -> pd.DataFrame:
    """Populated raw fields not covered by the mapping (report, not error)."""
    mapped = set(cfg[statement]["fields"].keys())
    rows = []
    for col in raw_df.columns:
        if col.startswith("_") or col in ID_FIELDS or col in mapped:
            continue
        n = int(raw_df[col].notna().sum())
        if n > 0:
            rows.append((statement, col, n))
    return pd.DataFrame(rows, columns=["statement", "unmapped_field", "nonnull_rows"])


def build_std_facts(
    store: Store, ts_code: str, mapping_path: Path | str = DEFAULT_MAPPING_PATH
) -> dict:
    """Rebuild std_facts for a company from raw + config. Returns summary."""
    cfg = load_mapping(mapping_path)
    all_facts, coverage = [], []
    for stmt in ("balancesheet", "income", "cashflow"):
        raw = store.load_raw(stmt, ts_code)
        facts = build_facts(raw, cfg, stmt)
        all_facts.append(facts)
        all_facts.append(derive_single_quarters(facts))
        coverage.append(mapping_coverage(raw, cfg, stmt))
    facts_df = pd.concat(all_facts, ignore_index=True)
    coverage_df = pd.concat(coverage, ignore_index=True)

    store.con.register("_facts", facts_df)
    if _table_exists(store, "std_facts"):
        store.con.execute("DELETE FROM std_facts WHERE ts_code = ?", [ts_code])
        store.con.execute("INSERT INTO std_facts SELECT * FROM _facts")
    else:
        store.con.execute("CREATE TABLE std_facts AS SELECT * FROM _facts")
    store.con.unregister("_facts")
    return {
        "facts": len(facts_df),
        "reported": int((facts_df.value_type == "reported").sum()),
        "calculated": int((facts_df.value_type == "calculated").sum()),
        "coverage": coverage_df,
    }


def _table_exists(store: Store, table: str) -> bool:
    return bool(store.con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
        [table],
    ).fetchall()[0][0])
