# Module 4 — Ratio & Decomposition Engine

`pipeline/ratios.py`; CLI `python -m pipeline.cli ratios 600519.SH`.
Table `ratios_annual`: one row per (year, capital basis ∈ {average, opening}).

## Formulas (Nissim–Penman, total-equity level)

```
RNOA = OI_after_tax / NOA_cap = OPM × ATO
OPM  = OI_after_tax / total_revenue      ATO = total_revenue / NOA_cap
OLLEV = OL_cap / NOA_cap                 FLEV = NFO_cap / TE_cap
NBC  = NFE_after_tax / NFO_cap           Spread = RNOA − NBC
ROTCE = RNOA + FLEV × Spread   (TE = NOA − NFO = equity incl. minority;
                                identity EXACT at this level, verified 1e-16)
```

Parent ROCE = NI_parent / CSE_cap is a separate column with NO identity
(minority interests break the simplified decomposition). ATO decomposes as
component_to_sales columns (inverse turnover) from `reformulated_bs_components`
(the resolved post-coalesce line items persisted by Module 3's engine).
Gross margin = (revenue − COGS)/revenue — product-business proxy, noted.

## Guards (never emit a misleading percentage)

- First year: no opening balance → all NaN, flag `no_opening_balance`.
- |NOA_cap| < 5% of revenue → RNOA/ATO/OLLEV NaN, flag `noa_near_zero_suppressed`.
- |NFO_cap| < 5% of revenue → NBC/Spread/ROTCE-identity NaN (ROTCE_direct kept),
  flag `nfo_near_zero_suppressed`.
- NFO < 0 → informational flag `net_financial_assets`; NaN component ratios
  mean the line item was not disclosed that year (missing ≠ zero).
- Column is `ratio_flags` (pandas shadows `.flags`, like `.diff` earlier).

## Results — 600519.SH (2026-11-19, average basis)

- K1 and K2 identities exact to machine precision across all years.
- RNOA: 49% (2015) → peak 227% (2019) → 123% (2025). Margin stable ~50%
  after tax; the decline is ALL asset turnover (ATO 4.6 → 2.5): NOA growing
  faster than revenue — the Module 6 growth-quality question.
- ROTCE 25–38% vs RNOA 120–230%: FLEV ≈ −0.72..−0.85 with NBC ≈ 0 — the
  giant net financial asset position earns nothing and drags equity returns
  far below operating returns (classic cash drag; parent ROE ~30-36% matches
  external sources).
- Components: inventory 28–34% of sales; receivables ≈ 0 (distributors
  prepay); customer advances 5–14% of sales falling; PPE 12–16%.
- Tests 40/40.

## Open issues

- Multi-company `ratios_annual` inserts use BY NAME; a company introducing a
  new component column after table creation would need ALTER — revisit at
  Module 15 (all-A-share crawl).
- Trailing-4Q / quarterly ratios deferred (annualization conventions needed).
