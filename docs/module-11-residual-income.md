# Module 11 — Growth quality & residual income (Value Creation Bridge)

**Status: done (2026-11-19).** `pipeline/residual_income.py` →
`residual_income_annual` / `value_bridge_annual` / `residual_income_checks`;
frontend tab `app/src/ValueView.tsx` ("Value Creation"; charts
`ResidualChart`, `SpreadChart`, `DriverEffectsChart`, reused
`WaterfallChart`). CLI: `python -m pipeline.cli residual <ts_code>
[--r-op 0.08] [--r-e 0.08]`.

## Objective

Does growth create value? Charge each year's income for the capital in place
at the start of the year, at an explicit required return, and explain the
year-on-year change in residual income with exact identities. All values
computed in Python from Module 3/4 outputs; the frontend only renders.

## Definitions (opening capital, Penman convention)

    ReOI_t = OI_t − r_op × NOA_{t−1}          residual operating income
    ReOI_core_t = OI_core_t − r_op × NOA_{t−1}
    RE_t   = CI_parent_t − r_e × CSE_{t−1}    common-equity residual earnings

- `r_op` and `r_e` are **assumptions** (default 8% / 8%), stored on every row
  as `r_op_assumed` / `r_e_assumed` and shown in the UI. No beta, no market
  data, no estimation. Module 12 adds sensitivity.
- RE uses parent comprehensive income per Penman (2002), pp. 14–15.
  Parent ROCE continues to use parent net income. Missing comprehensive
  income leaves RE null.
- Negative or tiny NOA base: ReOI is still well defined (the charge becomes
  a credit), but RNOA / ATO / spread are suppressed (`negative_noa_base`,
  `noa_base_near_zero_suppressed`, 5%-of-revenue floor as in Module 4).

## Value Creation Bridge (waterfall; schema mirrors cash_bridge_annual)

With PM = OI / revenue and PM = PM_core + PM_unusual:

```
ReOI_{t−1}
  + Sales growth        ΔRev × PM_{t−1}           (at last year's margin)
  + Core margin         Rev_t × ΔPM_core
  + Unusual items       Rev_t × ΔPM_unusual
  + Charge on new NOA   −r_op × (NOA_{t−1} − NOA_{t−2})
= ReOI_t
```

Exact by construction (ΔReOI = ΔOI − r_op·ΔNOA_begin), and it needs no RNOA,
so it works for negative NOA too. Sequential splits depend on order; "sales
first, at the prior margin" is the stated convention. The "unusual items"
step is the growth-quality signal: ReOI growth that comes from non-recurring
items is not core growth.

Needs two years of opening capital → first bridge year is the third balance
sheet year (`no_prior_reoi` otherwise).

## Penman drivers (summary columns)

    ReOI = (RNOA − r_op) × NOA_begin,  RNOA = PM × ATO,  s = RNOA − r_op
    ΔReOI = ΔPM × ATO_{t−1} × NOA_{t−1}       margin effect
          + PM_t × ΔATO × NOA_{t−1}           turnover effect
          + s_{t−1} × (NOA_{t−1} − NOA_{t−2})  NOA growth effect

Only where RNOA is meaningful on both opening bases (`drivers_available`,
else `drivers_suppressed`). The growth effect prices new capital at **last
year's** spread; when the new capital brings no revenue, the turnover effect
takes it back. Read the two together.

## Growth metrics

`oi_growth`, `reoi_growth` (suppressed when the prior base is ≤ 0 or below
5% of revenue: `reoi_base_not_positive_suppressed`); `delta_reoi` is always
reported when both levels exist.

## Checks (reported, never forced)

- **RI1_bridge_additive**: ReOI_{t−1} + Σ steps − ReOI_t
- **RI2_driver_split_additive**: ReOI_{t−1} + margin + turnover + growth − ReOI_t
- **RI3_rnoa_vs_module4**: local opening RNOA − ratios_annual (opening) RNOA
- **RI4_roce_vs_module4**: local opening ROCE − ratios_annual (opening) roce_parent

600519.SH: 42 checks; money checks max 1.5e−5 yuan (float noise), ratio
cross-checks exactly 0.

## Acceptance criteria

- [x] RI1–RI4 within tolerance for all years (¥1 money / 1e−12 ratio)
- [x] Rates carried as explicit assumption columns; ReOI moves exactly by
      Δr × NOA_begin when the rate changes (test-covered)
- [x] Guards: first year, no prior ReOI, negative NOA base (bridge kept,
      drivers suppressed), non-positive / tiny ReOI base: NaN + flag
- [x] A Module-4 disagreement surfaces in RI3 (test-covered)
- [x] 88/88 pipeline tests; tsc strict + vite build clean; preview 200;
      bundle 575 KB (60 bridge steps, 12 summary rows, 42 checks)
- [x] Headless-Chrome visual pass of the Value Creation tab (2020, 2025)

## Key findings (600519.SH, r = 8%)

- The capital charge is small: ¥1.3–5.0B against OI of ¥16–88B, so ReOI is
  close to OI. Moutai's value creation barely depends on the rate assumption
  at the operating level. RNOA − r is 43–260 points.
- ReOI rose every year 2016–2024 and **fell ¥4.85B in 2025** (84.5 → 79.7):
  sales −¥1.06B, core margin −¥2.51B, charge on new NOA −¥1.31B.
- Penman drivers 2025: NOA growth effect +¥30.1B, turnover effect −¥31.6B.
  The new capital (mostly inventory, per Module 10) earned nothing at the
  margin, so the growth effect is cancelled by the turnover decline.
  2023–24 show the same pattern at smaller scale (+18.5/−7.6, +17.4/−6.2).
  By contrast, 2017–19 growth was turnover-led with shrinking NOA (the
  advance-payment boom).
- Equity RE runs ¥2.7–16B below ReOI, and the gap widens as the cash pile
  grows. ROCE − r_e is 18–32 points vs RNOA − r_op of 43–260: net financial
  assets of ~¥180B earn far less than operations. Whether r_e should be lower
  than r_op for a cash-cushioned equity is a Module 12 question; here both
  rates are plain assumptions.
