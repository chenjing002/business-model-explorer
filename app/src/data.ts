/** Bundle loading and presentational reshaping.
 *  NO financial math here — only fetching, filtering, unit scaling for
 *  display (人民币元 → 亿元) and waterfall cumulative positioning (chart geometry).
 */
import type { Bundle, CashBridgeStep } from "./types";
import { expandCalculationDetails } from "./calculationDetails";
import { toYiYuan } from "./format";
import { localizeBundle } from "./locale";
import { bundleUrl } from "./site";
export { toYiYuan } from "./format";
export { bundleUrl } from "./site";

/** Bundles are stored gzipped. A server may also decode them on the way
 *  (Content-Encoding: gzip), so the gzip magic bytes decide, not the URL. */
export async function parseBundleBytes(bytes: ArrayBuffer): Promise<unknown> {
  const head = new Uint8Array(bytes, 0, Math.min(2, bytes.byteLength));
  if (head[0] !== 0x1f || head[1] !== 0x8b) return JSON.parse(new TextDecoder().decode(bytes));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Response(stream).json();
}

export async function loadBundle(tsCode: string, signal?: AbortSignal): Promise<Bundle> {
  const res = await fetch(bundleUrl(tsCode), { signal });
  if (!res.ok) throw new Error(`无法加载 ${tsCode} 的数据：${res.status}`);
  // Static hosts answer a missing file with the SPA page (200, text/html).
  if (res.headers.get("content-type")?.includes("text/html")) {
    throw new Error(`尚未生成 ${tsCode} 的分析数据包`);
  }
  const bundle = (await parseBundleBytes(await res.arrayBuffer())) as Bundle;
  if (bundle.schema_version !== 1) {
    throw new Error(`不支持的数据版本：${bundle.schema_version}`);
  }
  if (bundle.unit !== "CNY_yuan") throw new Error(`金额单位应为人民币元（CNY_yuan），收到：${bundle.unit}`);
  if (bundle.ts_code !== tsCode) throw new Error(`公司代码与数据包不符：${tsCode}`);
  return localizeBundle({ ...bundle, calculation_details: expandCalculationDetails(bundle.calculation_details) });
}

export const toPercent = (v: number | null): number | null =>
  v === null ? null : v * 100;

export const yearOf = (endDate: string): string => endDate.slice(0, 4);

export function annualYears(bundle: Bundle): string[] {
  return [...new Set(bundle.reformulated_bs.filter((r) => r.end_date.endsWith("1231"))
    .map((r) => yearOf(r.end_date)))].sort();
}

/** Waterfall geometry: each bar needs an invisible base + a visible span. */
export interface WaterfallBar {
  label: string;
  base: number; // invisible support (display units)
  span: number; // visible bar height (display units, signed)
  kind: CashBridgeStep["step_kind"];
}

export function waterfallBars(steps: CashBridgeStep[]): WaterfallBar[] {
  const ordered = [...steps].sort((a, b) => a.step_order - b.step_order);
  const bars: WaterfallBar[] = [];
  let running = 0;
  for (const s of ordered) {
    const v = (toYiYuan(s.value) ?? 0);
    if (s.step_kind === "adjustment") {
      bars.push({
        label: s.label,
        base: Math.min(running, running + v),
        span: v,
        kind: s.step_kind,
      });
      running += v;
    } else {
      // start and reported total are absolute columns from zero
      bars.push({ label: s.label, base: 0, span: v, kind: s.step_kind });
      if (s.step_kind === "start") running = v;
    }
  }
  return bars;
}
