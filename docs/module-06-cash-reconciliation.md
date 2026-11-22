# Module 6 — Earnings-to-Cash Reconciliation

`pipeline/cash_reconciliation.py`; CLI `python -m pipeline.cli cash 600519.SH`.
Tables: `cash_bridge_annual` (ordered long steps for waterfall rendering:
step_order, concept, label, value, step_kind ∈ start/adjustment/total) and
`cash_summary_annual` (CFO/FCF variants, conversion, check residuals).

## Conventions

- Bridge built ONLY from the reported indirect-method supplemental block
  (supp_* concepts). Tushare stores add-backs cash-positive (decrease in
  receivables positive, inventory build negative, etc.) — convention verified
  empirically: C1 residual ≈ 0 for all 12 annual years of 600519.SH.
- Undisclosed step → no bar (never a fabricated zero). Years without the
  supplemental block → flag `supplemental_not_disclosed`, no bridge; FCF
  still computed from direct-method figures.
- CAS treatment preserved, not adjusted: interest received is investing;
  interest + dividends paid are financing. Chinese CFO already excludes
  financing interest. Finance-subsidiary deposit flows sit INSIDE operating
  CFO (客户存款净增加额) — affects Moutai CFO volatility.
- FCF definitions carried as text columns: fcf_simple = CFO − cash capex;
  fcf_after_disposals adds disposal proceeds. No good/bad labeling of FCF.
- Checks: C0 supp NI vs IS NI; C1 bridge sum vs reported indirect CFO;
  C2 indirect vs direct CFO. Residuals reported, never forced.
- cash_conversion = CFO/NI, suppressed when |NI| < 2% of CFO scale.

## Results — 600519.SH (2026-11-19)

- C0 = C1 = C2 ≈ 0 for all years; supplemental disclosed every annual year.
- Cash conversion averages ~1.0 but swings: 2016 2.09 (deposit inflows at the
  finance sub, advances build), 2022 0.56, 2025 0.72. The 2025 bridge:
  NI ¥85.3B → CFO ¥61.5B, with ¥7.1B inventory build, ¥11.0B receivables
  increase and ¥6.8B payables decrease absorbing ~¥25B into working capital —
  consistent with Module 5's rising DIO and eroding advance days.
- Capex tiny (¥1–5B vs CFO ¥37–92B): FCF ≈ CFO — the opposite pole from the
  transportation-machine example.
- Tests 54/54.

## Open issues

- H1 supplemental rows exist (33 CF rows total incl. half-years) — bridge is
  annual-only for now; interim bridges deferred with other quarterly work.
- SBC is not separately disclosed in CAS supplemental; it is inside other
  lines (no separate bar possible without notes data).
