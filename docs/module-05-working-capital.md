# Module 5 — Working Capital & Cash Conversion

`pipeline/working_capital.py`; CLI `python -m pipeline.cli wc 600519.SH`.
Table `working_capital_annual`. Simulations are pure functions (UI later).

## Definitions (average balances, 365 days)

- DIO = 365·avg inventory/COGS; DSO = 365·avg TRADE receivables/revenue
  (notes+accounts+combined+receivables_financing+contract assets;
  other_receivables excluded — not trade)
- DPO = 365·avg trade payables/purchases, **purchases ≈ COGS + ΔInventory**
  (disclosed in `dpo_method`); `dpo_cogs` variant also reported — they
  diverge materially when inventory grows (Moutai: 62 vs 92 days in 2025)
- CCC = DIO + DSO − DPO. Customer advances (预收+合同负债) reported as
  `advance_days`, NOT netted into CCC (customer financing ≠ supplier financing)
- OWC = inventory + trade receivables + prepayments − trade payables −
  other op payables (salaries/taxes/other) − customer advances
- `incr_owc_per_incr_revenue` guarded: |Δrevenue| < 5% of revenue → NaN + flag
- A missing beginning or ending balance leaves the affected turnover metrics null.
  The OWC bridge excludes groups absent at both ends. A group disclosed at only one
  end leaves the other end's OWC, the average and the change null.

## Simulations (pure, tested)

- `simulate_efficiency_change`: same sales/cost, different days → capital
  released. Operating income is deliberately NOT an output: turns move
  capital, not accounting profit (Amazon 2004 lesson, test-asserted).
- `simulate_growth`: constant days, growing revenue → annual ΔOWC cash
  absorption; zero growth ⇒ zero investment (tested).

## Results — 600519.SH (2026-11-19)

- DIO 1,200–2,400 days: 3.5–6.5 YEARS of inventory at COGS cost — aging
  baijiu with a 92% gross margin; recently rising again (1,419d in 2025).
- DSO ≈ 0–7 days (cash/prepay business); CCC still >1,200 days — Moutai is
  the ANTI-Amazon on inventory, yet OWC ≈ 0–40% of sales because customer
  advances + payables + salary/tax payables finance nearly all of it.
- Advance days fell 121 (2016) → 19 (2025): steadily shrinking reliance on
  distributor prepayments (channel reform / direct-sales shift) — a real
  deterioration in customer financing worth watching.
- 2021–22 CCC honestly NaN (no receivable line disclosed those years).
- Tests 48/48.

## Open issues

- Purchases approximation ignores inventory write-offs/reclassifications
  (none material for Moutai; flag would come from Module 1 checks).
- Quarterly/trailing metrics deferred with Module 4's.
