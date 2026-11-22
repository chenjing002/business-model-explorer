# Module 12: Valuation & reverse analysis

**Status: done (2026-11-19).** Files:
- `pipeline/market.py`: `raw_daily_basic` and `market_snapshot_annual`
- `pipeline/valuation.py`: `valuation_annual` / `valuation_bridge_annual` /
  `valuation_grid` / `valuation_reverse_curve` / `valuation_checks`
- Frontend tab `app/src/ValuationView.tsx` ("Valuation"). Charts:
  `ModelVsMarketChart`, `ImpliedGrowthChart`, `SensitivityHeatmap`,
  `ReverseCurveChart`, `PeChart`, plus the reused `WaterfallChart`.

CLI:

    python -m pipeline.cli market 600519.SH [--start-year 2014 --end-year 2025]   # needs token
    python -m pipeline.cli valuation 600519.SH [--r-op 0.08 --r-e 0.08 --g 0.03]   # offline

## Market data (new input)

Tushare `daily_basic` through the gateway (it works there, unlike parent
statements). The module fetches December windows for each fiscal year and
stores the raw rows verbatim, with the same content-hash idempotency and
provenance as the statements. The snapshot is the **last trading day of
each fiscal year**. Units are converted from Tushare's 万 units:
`total_mv` (万元) × 1e4 gives market cap; `total_share` (万股) × 1e4 gives
shares.

**Hindsight anchor:** the model values year-end book at the year-end price.
That year's statements were published 3–4 months later. This is the textbook
convention, not a point-in-time trading signal. Check M2 confirms it
independently: Tushare's own year-end `pe` equals market cap / *prior-year*
NI (the latest published report then), to 2e−6 in every year.

## Models (all assumptions: r_op, r_e, g stored on every row)

Equity value is V_E = V_NOA − NFO_0 − MI_0, with NFO and MI at **book**.

| model | V_NOA |
|---|---|
| `book` (SF1) | NOA_0 |
| `reoi_flat` (SF2) | NOA_0 + ReOI_0 / r |
| `reoi_g` (**primary**) | NOA_0 + ReOI_0 (1+g) / (r − g) |
| `rnoa_g` (Penman SF3) | NOA_0 + (RNOA_0 − r) NOA_0 / (r − g) |

Definitions: ReOI_0 = OI_0 − r·NOA_{−1} (Module 11's definition, at this
module's r). RNOA_0 is the opening RNOA, suppressed as in Module 4.

`rnoa_g` earns last year's RNOA on the whole year-end NOA. It is the more
aggressive model whenever NOA grows faster than OI, which has been
Moutai's case since 2019. `reoi_g` only grows the residual income the
company actually earned. The primary model drives the bridge, the grid and
V/P.

**Equity level:** the RI value is CSE_0 + RE_0(1+g)/(r_e − g). The AEG
value uses the **same** forecast: Earn_1 = r_e·CSE_0 + RE_1 and
AEG_2 = g·RE_1. The two values are identical by algebra (check V1).
AEG adds the P/E reading: the normal forward P/E is 1/r_e.

**Historical AEG** = CI_t + r_e·d_{t−1} − (1+r_e)·CI_{t−1}, with parent
comprehensive income CI and implied payout d = CI − ΔCSE, including other
direct equity movements. Historical AEG equals ΔRE (check V9). The forward
multiples use forecast parent comprehensive income. The same-year historical
P/E uses parent net income.

## Reverse engineering (closed forms, all round-tripped)

Notation: P_NOA = market cap + NFO_0 + MI_0, X = P_NOA − NOA_0, and
Y = mcap − CSE_0.

- implied g, ReOI anchor = (rX − ReOI_0)/(X + ReOI_0)
- implied g, RNOA anchor = r − (RNOA_0 − r)·NOA_0 / X
- implied g, reverse DCF = (r·P_NOA − FCF_0)/(P_NOA + FCF_0), where
  FCF_0 = OI − ΔNOA (Module 10). It swings with working capital, so a single
  year is a noisy anchor.
- implied g, equity = (r_e·Y − RE_0)/(Y + RE_0)
- implied r_op at g = [OI_0(1+g) + gX] / [X + (1+g)NOA_{−1}]
- implied r_e at g = [CI_0(1+g) + gY] / [Y + (1+g)CSE_{−1}]

A non-positive anchor, or a solution that is not below r, gives NaN plus a
flag (`implied_g_*_undefined`). There is no perpetuity to report in those
cases.

## Rate sensitivity

- `valuation_grid`: the primary model over r ∈ 6–12% × g ∈ −2…5%. ReOI_0 is
  recharged at each r. The grid is shown as a heatmap of V/P, diverging
  around 1 (log2 colour scale, display only).
- `valuation_reverse_curve`: implied g for each anchor over r = 5–12% in
  0.5-point steps. It shows the (r, g) pairs that justify the price.

## Valuation bridge (waterfall, cash_bridge schema)

NOA (book) → ReOI flat / r → growth at g → net financial assets (−NFO) →
minority interests → **model equity** (total) → market premium →
**market cap** (total).

## Checks (reported, never forced)

M1 market cap vs close × shares (relative); M2 Tushare pe vs market cap /
prior-year NI (relative, informational); V1 AEG = RI equity; V2 bridge
additive; V3–V6 implied-g round trips; V7–V8 implied-r round trips; V9
historical AEG = ΔRE; V10 ReOI_0 vs Module 11 (only when the rates match).

600519.SH: 132 checks. Money max ¥2.4e−3 (on values of about ¥10¹²). M1
max 1.7e−13. M2 max 2.4e−6.

## Guards

- first year: `no_opening_balance`
- no market data: models still computed, no reverse analysis, grid or bridge
- g ≥ r: growth models NaN, `growth_not_below_rate`; the no-growth model
  survives
- negative or tiny NOA base: `rnoa_anchor_suppressed`; ReOI models survive
- market EV ≤ NOA: `market_ev_at_or_below_noa` (informational)

## Key findings (600519.SH, r = 8%, g = 3%)

- **2025:** market cap ¥1,725B vs primary model equity ¥1,885B, so V/P = 1.09.
  The price implies g = 2.5% at r = 8%, or r_op = 8.5% at g = 3%. The bridge
  is NOA 75 + ReOI-flat value 996 + growth 645 + net financial assets 179 −
  MI 9, minus a 161 market discount.
- **2020–21 peak:** market cap ¥2.5–2.6T vs model ¥1.1–1.3T (V/P 0.45–0.50).
  The implied perpetual growth was 5.9%, close to the 8% rate, and the
  market forward P/E was 50 vs a model P/E of 18. Since then the implied
  growth has fallen every year (5.7 → 4.7 → 4.1 → 2.8 → 2.5%). The price
  fell while value under fixed assumptions kept rising.
- RNOA anchor vs ReOI anchor: in 2024 the RNOA model is ¥550B higher,
  because last year's RNOA is applied to NOA that grew 36%. The two anchors
  disagree exactly where Modules 10–11 found capital growing without revenue.
- Equity-level RI (¥1,556B) < enterprise model (¥1,885B). The ~¥180B cash
  pile is charged r_e at equity level but enters at book in the enterprise
  view (same theme as Module 11).
- Historical AEG was positive in 2016–2024 (cum-payout comprehensive-income growth 10–66% vs
  8%). In 2025 it turned negative (−¥5.3B, growth 1.8%).
- All four implied-g series agree within about 1 point in most years. The
  reverse-DCF series is the outlier in 2016 (−1.2%, the advances-driven FCF
  spike).

## Not claimed / open

- No analyst forecasts, no beta, and no explicit forecast horizon. A single
  perpetual g is the crudest scheme.
- The market premium is what the assumptions leave unexplained, not an error.
- There is no "today's price" valuation: anchoring the latest annual
  statements to a later price needs value roll-forward (V × (1+r)^τ − dividends).
  Left for a later iteration.
