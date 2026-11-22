# Module 3 — Penman Reformulation Engine

## Core identities

```
NOA = OA − OL          NFO = FO − FA (negative = net financial assets)
CSE = NOA − NFO − MI   (checked against reported parent equity, R3)
NFE_after_tax = NFE_pretax × (1 − t)      t = statutory-rate ASSUMPTION (default 25%)
OI_after_tax  = NI_total + NFE_after_tax  (consolidated level, incl. minority claims)
```

`pipeline/reformulate.py`; CLI `python -m pipeline.cli reformulate 600519.SH [--tax-rate 0.25]`.
Tables: `reformulated_bs`, `reformulated_is`, `reclass_decisions` (audit trail).

## Classification resolution (in order)

1. Default class per concept from `config/mapping_tushare.yml`.
2. Per-company override from `config/overrides.yml` (class + reason; recorded
   in reclass_decisions). Company and period-specific income sign rules are also supported.
3. Coalesce groups: Tushare combined fields (受收票据及应收账款 etc.) vs granular.
   Per period: granular used when it sums to combined or combined absent;
   otherwise the combined lump is used under the group's class (mixed-class
   judgment) — every choice recorded with reason.

Conventions: all cash = financial_asset (no invented operating-cash split);
Moutai finance-subsidiary deposits/interbank items = financing by default
(flagged judgmental). IS memo lines are excluded from sums. When disclosed and classified as operating,
associate/JV earnings are moved out of total investment income into operating income.

## Sign conventions (empirically verified on 600519.SH)

- `assets_impair_loss` (old standard, ≤2018): expense-signed (+ = loss).
- `credit_impa_loss`, `oth_impair_loss_assets` (post-2019 lines): stored with
  the NEW CAS display sign (negative = loss) → income-signed contributions.
- Violations at any company surface in R4 — never silently absorbed.

## Reconciliations (reported, never forced)

R1 OA+FA vs total_assets; R2 OL+FO vs total_liabilities;
R3 NOA−NFO−MI vs parent equity; R4 (OI_pretax − NFE_pretax) vs pretax profit.

## Critical lesson: explicit API fields

The gateway's default responses OMIT newer CAS fields (receiv_financing
¥4.5B for Moutai FY2025, use_right_assets, lease_liab, contract_assets,
oth_eq_invest, oth_income, asset_disp_income, credit_impa_loss). This caused
R1 residuals up to ¥8.8B. Fix: `pipeline/fields.py` passes explicit full
field lists for balancesheet/income (cashflow default is complete).
**Any new statement API call must specify fields explicitly.**

## 600519.SH 复核

- 2019 年一季报的信用减值损失列在营业总成本内，负值为转回，作为减项。公司与期间规则记录在 `config/overrides.yml`，原始披露值保留。 [2019 年一季报第 13–14 页](https://www.moutaichina.com/uploadfile/2019/0425/20190425082635188.pdf)
- 单季重构按相邻累计重构结果差分，首季取累计值。原始单季科目仍要求两期都有对应披露。
- R4 的 48 条累计记录、47 条单季记录最大绝对差额均小于 0.01 元。逐项核对结果见 [财务复核记录](penman-financial-review.md)。
