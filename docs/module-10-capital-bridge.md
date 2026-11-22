# Module 10 — Capital employed & reinvestment (Capital Investment Bridge)

**Status: done (2026-11-19).** `pipeline/capital_bridge.py` →
`capital_bridge_annual` / `capital_summary_annual` / `capital_bridge_checks`;
frontend tab `app/src/CapitalView.tsx` (charts `GrowthChart`, `CapexDaChart`,
`FcfChart`, reused `WaterfallChart`). CLI: `python -m pipeline.cli capital
<ts_code>`.

## Objective

Answer, per year and with exact identities: where did the year's capital go
(investment side), what funded it (funding side), and how much of operating
income was reinvested. All values computed in Python from Module 3/4/6
outputs; the frontend only renders.

## Investment side — the bridge (waterfall-ready)

```
NOA_begin
  + Δ Inventory                      (INVENTORY concepts)
  + Δ Receivables & prepayments      (RECEIVABLES_PREPAY)
  + Δ PP&E & construction            (PPE_GROUP)
  + Δ Intangibles & other LT         (INTANGIBLES_GROUP)
  + Δ Other operating assets         (residual: OA − known groups)
  − Δ Supplier credit                (SUPPLIER_CREDIT)
  − Δ Customer advances              (CUSTOMER_ADVANCES)
  − Δ Other operating liabilities    (residual: OL − known groups)
= NOA_end
```

- Concept sets are **imported from Module 8** (`economics_map.py`) so group
  definitions stay identical across the Map and the Bridge; group ids match
  Module 8 node ids.
- Sums are restricted to the operating `effective_class` — a concept that was
  classified financial for some period is never summed into an operating
  group (test-covered).
- The two residual groups absorb undisclosed/unmapped components, so the
  bridge is **exact by construction**; residuals are visible as their own
  steps, never hidden.
- Schema mirrors `cash_bridge_annual` (`step_order`, `concept`, `label`,
  `value`, `step_kind`) so the existing waterfall geometry/chart is reused
  unchanged. Step values are signed contributions to ΔNOA.
- First year: no opening balance → no bridge rows, summary row flagged
  `no_opening_balance` (levels still reported).

## Funding side

From Module 3's exact NOA = CSE + MI + NFO:

    ΔNOA = ΔCSE + ΔMI + ΔNFO

`delta_cse` / `delta_mi` / `delta_nfo` are summary columns. For Moutai,
ΔNFO is strongly negative most years: operating profits funded both NOA
growth and a growing pile of net financial assets.

## Checks (reported, never forced)

- **B1_bridge_additive**: NOA_begin + Σ steps − NOA_end
- **B2_delta_noa_vs_oa_ol**: ΔNOA − (ΔOA − ΔOL)
- **B3_funding_identity**: ΔNOA − (ΔCSE + ΔMI + ΔNFO)

All ≈ 0 (float noise only, max 5.7e−5 yuan on ¥60B magnitudes).

## Reinvestment metrics (`capital_summary_annual`)

- `reinvestment_rate` = ΔNOA / OI_after_tax — guarded: |OI| < 5% of revenue
  → NaN + `oi_near_zero_suppressed`.
- `noa_growth` vs `revenue_growth` — NOA growth persistently above revenue
  growth is the falling-ATO story (Module 4). Guards: |NOA_begin| < 5% of
  revenue → `noa_base_near_zero_suppressed`; negative base →
  `negative_noa_base` (a growth % on a negative base misleads).
- `capex_paid` vs `da_total` (= sum of the **disclosed** supp_* lines:
  depreciation, ROU depreciation, intangible + LT-deferred amortization;
  none disclosed → NaN + `da_not_disclosed`), `capex_to_da`.
  Maintenance-vs-growth capex split is NOT knowable from statements —
  carried as `capex_split_note`, never estimated.
- `fcf_from_oi` = OI_after_tax − ΔNOA (Penman free-cash-flow identity
  C − I = OI − ΔNOA), compared with Module 6's cash-statement `fcf_simple`;
  `fcf_articulation_diff` is **expected to be nonzero** (CAS interest
  classification, FX/dirty-surplus/M&A items that move NOA without passing
  through OI, cash-vs-accrual timing) — reported with `articulation_note`,
  never reconciled away.

## Frontend

"Capital" tab, shared year selector. Four panels: ΔNOA waterfall for the
selected year (reused `WaterfallChart`; flags surfaced), growth &
reinvestment lines (%), capex vs D&A bars (single axis; the precomputed
capex/D&A ratio is shown in the tooltip — no frontend math), and the two
FCF measures with the articulation gap in the tooltip. New-series palette
(blue/teal/amber) validated for CVD separation and contrast.

## Acceptance criteria

- [x] B1–B3 exact for all 11 bridge years of 600519.SH (float noise only)
- [x] Residual groups absorb undisclosed components; identity stays exact
      (test-covered, incl. a misclassified-component case)
- [x] Guards: first year, OI near zero, negative/near-zero NOA base,
      D&A undisclosed — NaN + flag, never a misleading number
- [x] fcf_from_oi vs fcf_simple both carried with definitions as text
- [x] 80/80 pipeline tests; tsc strict + vite build clean; preview 200;
      bundle 545 KB with 110 bridge steps / 12 summary rows / 33 checks

## Key findings (600519.SH)

- 2016–2018 ΔNOA was **negative** (reinvestment rate −0.90 in 2016): the
  advance-payment boom made customers fund more than the whole asset build;
  the operating engine ran on negative incremental capital.
- Since 2019, NOA grows 10–36%/yr vs revenue 10–18% (2025: +21% NOA on
  −1% revenue) — reinvestment rate 5–19% buys capital intensity, not
  growth; this is the ATO-decline mechanism from Modules 4/9 in stock form.
- Capex/D&A ≈ 1.0–3.1 — the physical plant grows modestly; the capital
  build is inventory (2025 bridge: +¥7.1B of +¥13.0B ΔNOA).
- fcf_from_oi tracks fcf_simple within ¥2–24B; the largest gap is 2022
  (¥24B), the year Module 6 flagged cash conversion at 0.56 — the two
  measures disagree exactly when accrual OI and cash CFO diverge, which is
  the point of showing both.

## Browser visual pass

Still pending together with Modules 7–9 (`cd app && npm run dev`).
