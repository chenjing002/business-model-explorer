# Module 9 — Profitability Driver Tree

**Status: done (2026-11-19).** `pipeline/driver_tree.py` →
`driver_tree_nodes` / `driver_tree_checks`; frontend tab
`app/src/DriverTree.tsx`.

## Objective

Hierarchical, expandable Nissim–Penman decomposition of ROTCE/RNOA where
every parent–child relation is an accounting identity or definition, every
additive level carries explicit signed weights plus a reported residual node
(so sums are exact without forcing), and every node links to its 12-year
time series and declared related metrics. Tree structure and all values are
assembled in Python from `ratios_annual` (Module 4); the frontend renders
and joins — it computes nothing.

## Tree (per year × capital basis, 21 nodes)

```
rotce                     ROTCE = RNOA + FLEV × Spread     (identity terms)
├─ rnoa                   RNOA = OPM × ATO                 (identity terms)
│  ├─ opm                 OI after tax / revenue
│  │  ├─ opm_core   (+1)  additive
│  │  ├─ opm_unusual(+1)  additive residual = OPM − core
│  │  └─ gross_margin     context (product-business proxy)
│  └─ ato                 revenue / NOA
│     ├─ noa_to_sales     reciprocal = 1 / ATO
│     │  ├─ inventory/receivables/prepayments/ppe/cip/intangibles _to_sales (+1)
│     │  ├─ op_payables/customer_advances _to_sales (−1)
│     │  └─ other_net_to_sales (+1)  residual (incl. undisclosed components)
│     └─ ollev            context: OL / NOA
├─ flev                   NFO / TE
└─ spread                 RNOA − NBC
   └─ nbc                 NFE after tax / NFO
```

Node columns: `parent_id`, `depth`, `sort_order` (depth-first — renders the
tree top-to-bottom), `relation` (root / identity_term / component / residual
/ reciprocal / context), `weight` (sign in the parent's additive sum, null
when not additive), `fmt` (pct / x), `formula`, `related_json` (declared
keys into working_capital/ratios tables: dio, dso, dpo, dpo_cogs,
advance_days, roce_parent), `note`, `node_flags` (ratio_flags carried).

## Identity checks (`driver_tree_checks`, per year × basis)

- T1 ROTCE identity vs direct computation
- T2 RNOA − OPM × ATO
- T3 OPM − (core + unusual)
- T4 Spread − (RNOA − NBC)
- T5 NOA/sales − Σ(signed components + other_net)

Residual null (not fabricated) when inputs are suppressed by Module 4
guards or in the first year (no opening balance). A component missing for a
year is absorbed into `other_net_to_sales` (noted) so T5 stays exact.

## Decisions

- ROTCE node shows the **direct** computation (NI_total / TE); the identity
  version is relegated to check T1 — the displayed number is never the
  output of its own decomposition.
- Operating liabilities enter NOA/sales with weight −1; the frontend shows a
  minus badge rather than negated values, so numbers match Module 4 output.
- Only the average-capital basis is rendered (both bases exported).
- ROCE (parent) appears solely as a related metric on the root: minority
  interests prevent the clean decomposition at parent level (Module 4 rule).

## Frontend

`DriverTree.tsx`: expandable rows (default: root + RNOA open), minus badge
for negative-weight children, relation tags (residual / context / = 1/parent),
inspector with formula, note, flags, full-history line chart (% or ×),
related-metrics join, and the year's max |check residual|. Shared
related-metric lookup extracted from EconMap into `app/src/metrics.ts`
(single source for both tabs).

## Test results (2026-11-19)

- 70/70 pipeline tests (8 new in `tests/test_driver_tree.py`): structure/
  depths, exact identities, signed-sum exactness via residual node,
  suppression → NaN propagation, first-year NaN + flag, missing-component
  absorption, both bases.
- Live 600519.SH: 504 node rows (12y × 2 bases × 21 nodes); all 120 checks
  |residual| ≤ 1e-12, 10 null (first year / suppressed). 2025 average basis:
  ROTCE 34.4% = f(RNOA 122.8%, FLEV −0.72, Spread 122.4%); NOA/sales 0.40
  of which inventory 0.34, payables −0.10, advances −0.05.
- `tsc` strict + `vite build` clean; preview smoke test 200; bundle 510 KB;
  all declared related keys resolve in `metrics.ts`.
- Browser interaction pass still pending (`cd app && npm run dev`).
