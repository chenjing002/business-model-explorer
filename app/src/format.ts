/** Presentation only: financial inputs are CNY yuan, never 万元 or billions. */
export const MONEY_DIVISORS = { "元": 1, "万元": 10_000, "亿元": 100_000_000 } as const;
export type MoneyUnit = keyof typeof MONEY_DIVISORS;

export function formatNumber(value: number, digits = 2): string {
  return new Intl.NumberFormat("zh-CN", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

const valid = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);

export const toYiYuan = (yuan: number | null): number | null => valid(yuan) ? yuan / MONEY_DIVISORS.亿元 : null;

/** Raw CNY yuan → scaled number without the unit, for tables that state the
 *  unit once in the header. Tiny nonzero values keep scientific notation. */
export function formatAmountNumber(yuan: number | null, unit: MoneyUnit = "亿元", digits = 2): string {
  if (!valid(yuan)) return "—";
  const scaled = yuan / MONEY_DIVISORS[unit];
  return scaled !== 0 && Number(scaled.toFixed(digits)) === 0
    ? scaled.toExponential(2) : formatNumber(scaled, digits);
}

/** Raw CNY yuan → explicitly labeled Chinese unit. */
export function formatAmount(yuan: number | null, unit: MoneyUnit = "亿元", digits = 2): string {
  return valid(yuan) ? `${formatAmountNumber(yuan, unit, digits)} ${unit}` : "—";
}

/** A chart value already scaled to 亿元. Never apply the divisor twice. */
export function formatYiValue(yiYuan: unknown, digits = 2): string {
  return valid(yiYuan) ? `${formatNumber(yiYuan, digits)} 亿元` : "—";
}

export function formatPrice(yuanPerShare: number | null, digits = 2): string {
  return valid(yuanPerShare) ? `${formatNumber(yuanPerShare, digits)} 元/股` : "—";
}

export function formatResidual(yuan: number): string {
  if (!valid(yuan)) return "—";
  const absolute = Math.abs(yuan);
  if (absolute > 0 && absolute < 0.01) {
    // Prefer a readable decimal while preserving small nonzero discrepancies.
    if (absolute < 1e-12) return `${yuan.toExponential(2)} 元（绝对值不足 1 分）`;
    let digits = 2 - Math.floor(Math.log10(absolute));
    while (Number(absolute.toFixed(digits)) >= 0.01) digits += 1;
    const decimal = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: digits }).format(yuan);
    return `${decimal} 元（绝对值不足 1 分）`;
  }
  return formatAmount(yuan, "元", 2);
}
