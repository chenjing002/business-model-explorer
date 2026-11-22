import { formatAmount, formatNumber, formatPrice, formatResidual } from "./format";
import { flagText, textZh } from "./locale";

export interface CalculationDetail {
  label: string;
  value: number | null;
  unit: string;
  formula: string;
  inputs?: string[];
  source?: string;
  ann_date?: string;
  trade_date?: string;
  row_hash?: string;
  reason?: string;
  note?: string;
}

export type CalculationIndex = Record<string, Record<string, CalculationDetail>>;

/** Published (GitHub Pages) bundles store the index code-major, with the
 *  fields identical across years kept once per code (`pipeline/pages.py`);
 *  ~half the gzip size. Expanding is pure regrouping — no values change. */
export interface CompactCalculationIndex {
  format: "by_code_v1";
  years: string[];
  shared: Record<string, Partial<CalculationDetail>>;
  values: Record<string, Record<string, Partial<CalculationDetail>>>;
}

export function expandCalculationDetails(
  details: CalculationIndex | CompactCalculationIndex | undefined,
): CalculationIndex | undefined {
  if (details?.format !== "by_code_v1") return details as CalculationIndex | undefined;
  const { years, shared, values } = details as CompactCalculationIndex;
  const index: CalculationIndex = Object.fromEntries(years.map((year) => [year, {}]));
  for (const [code, byYear] of Object.entries(values)) {
    for (const [year, own] of Object.entries(byYear)) {
      index[year][code] = { ...shared[code], ...own } as CalculationDetail;
    }
  }
  return index;
}

export function auditTarget(year: string, code: string) {
  return { "data-calculation": `${year.slice(0, 4)}1231 ${code}` };
}

export function calculationValue(detail: CalculationDetail): string {
  const { value, unit } = detail;
  if (value == null) return detail.source ? "未披露" : "无法计算";
  switch (unit) {
    case "CNY_yuan": return formatAmount(value);
    case "residual": return formatResidual(value);
    case "price": return formatPrice(value);
    case "pct": return `${formatNumber(value * 100, 2)}%`;
    case "pp": return `${formatNumber(value * 100, 2)} 个百分点`;
    case "days": return `${formatNumber(value, 2)} 天`;
    case "x": return `${formatNumber(value, 2)} 倍`;
    case "shares": return `${formatNumber(value, 0)} 股`;
    case "wan_shares": return `${formatNumber(value, 4)} 万股`;
    case "wan_yuan": return `${formatNumber(value, 4)} 万元`;
    default: return formatNumber(value);
  }
}

export function escapeTooltip(value: string): string {
  return value.replace(/[&<>"']/g, (char) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char] ?? char
  ));
}

export function calculationHtml(
  index: CalculationIndex, date: string, code: string, override?: CalculationDetail,
): string {
  const root = override ?? index[date]?.[code];
  if (!root) return "";

  const esc = escapeTooltip;
  function render(detail: CalculationDetail, ed: string, depth: number): string {
    const period = detail.trade_date ?? detail.ann_date;
    const rawAmount = detail.source && detail.unit === "CNY_yuan" && detail.value != null
      ? ` · 原值 ${formatResidual(detail.value)}` : "";
    const source = detail.source
      ? `<div class="calc-source"><code>${esc(detail.source)}</code>${rawAmount}${period ? ` · ${esc(period)}` : ""}</div>`
      : "";
    const reason = detail.reason ? `<p>${esc(flagText(detail.reason))}</p>` : "";
    const note = detail.note ? `<p>${esc(textZh(detail.note))}</p>` : "";
    const rows = depth < 5
      ? (detail.inputs ?? []).map((item) => {
        const [, minus, offsets, ref] = /^(-?)(@*)(.+)$/.exec(item) ?? [];
        const inputDate = `${Number(ed.slice(0, 4)) - offsets.length}1231`;
        const input = index[inputDate]?.[ref];
        const year = inputDate === date ? "" : `${inputDate.slice(0, 4)}年 `;
        if (!input) {
          if (inputDate !== ed) return `<li>${year} · 缺少该年度输入</li>`;
          return "";
        }
        const line = `<span>${minus ? "− " : ""}${year}${esc(textZh(input.label))}</span><b>${esc(calculationValue(input))}</b>`;
        return input.inputs?.length && depth < 4
          ? `<li><details><summary>${line}</summary>${render(input, inputDate, depth + 1)}</details></li>`
          : `<li><div class="calc-line">${line}</div>${render(input, inputDate, depth + 1)}</li>`;
      }).join("")
      : "";
    return `<div class="calc-body"><p>${esc(detail.formula)}</p>${source}${reason}${note}${rows ? `<ul>${rows}</ul>` : ""}</div>`;
  }

  return `<div class="calc-line calc-title"><span>${esc(textZh(root.label))}</span><b>${esc(calculationValue(root))}</b></div>${render(root, date, 0)}`;
}

export interface ChartPoint {
  axisValueLabel?: string;
  seriesIndex: number;
  dataIndex: number;
}

export interface CalculationRef {
  date: string;
  code: string;
  override?: CalculationDetail;
}

export type ChartCalculation = readonly string[] | ((point: ChartPoint) => CalculationRef | undefined);

export function sensitivityRef(
  cell: { end_date: string; r: number; g: number; v_equity: number | null; v_to_p: number | null; v_per_share: number | null },
  index: CalculationIndex,
): CalculationRef {
  const code = "scenario:v_to_p";
  const date = cell.end_date;
  const scenario = index[date];
  // Scenario parameters and results are the cell's Python outputs.
  return {
    date, code,
    override: {
      label: "情景模型价值／总市值", value: cell.v_to_p, unit: "x",
      formula: "［NOA ＋（OI − r × 期初 NOA）×（1 ＋ g）÷（r − g）− NFO − 少数股东权益］÷ 总市值",
      inputs: ["noa", "oi_after_tax", "@noa", "nfo", "minority_interests", "market_cap", "shares"],
      note: [
        `r ${formatNumber(cell.r * 100, 2)}%，g ${formatNumber(cell.g * 100, 2)}%`,
        `股权价值 ${formatAmount(cell.v_equity)}，每股价值 ${formatPrice(cell.v_per_share)}`,
      ].join(" · "),
      reason: !scenario || cell.g >= cell.r ? "情景增长率须低于必要报酬率" : undefined,
    },
  };
}
