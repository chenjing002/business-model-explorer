import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { gunzipSync, gzipSync } from "node:zlib";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadTs } from "./load-ts.mjs";

const bundle = JSON.parse(gunzipSync(readFileSync(new URL("../public/data/600519.SH.json.gz", import.meta.url))));
const format = loadTs("format.ts");
const locale = loadTs("locale.ts");
const data = loadTs("data.ts");

function chartOptions(component, props) {
  let option;
  const module = loadTs(`charts/${component}.tsx`, {
    "../useECharts": { useECharts(value) { option = value; return null; } },
  });
  renderToStaticMarkup(createElement(module[component], props));
  return option;
}

test("人民币元、万元、亿元按十进制中文单位准确换算", () => {
  assert.equal(format.toYiYuan(1_000_000_000), 10);
  assert.equal(format.formatAmount(1_000_000_000), "10.00 亿元");
  assert.equal(format.formatAmount(100_000_000, "万元"), "10,000.00 万元");
  assert.equal(format.formatAmount(10_000, "元"), "10,000.00 元");
  assert.equal(format.formatAmount(-1_000_000_000), "-10.00 亿元");
  assert.equal(format.formatAmount(15_000), "1.50e-4 亿元");
  assert.equal(format.formatYiValue(10), "10.00 亿元");
  assert.equal(format.formatPrice(1411.12), "1,411.12 元/股");
  assert.equal(format.formatAmount(null), "—");
  assert.equal(format.toYiYuan(null), null);
  assert.equal(format.formatYiValue(NaN), "—");
});

test("元级校验差额保留小数精度，不将非零差额显示成零", () => {
  assert.equal(format.formatResidual(0), "0.00 元");
  assert.equal(format.formatResidual(0.0024), "0.0024 元（绝对值不足 1 分）");
  assert.equal(format.formatResidual(0.0000153), "0.0000153 元（绝对值不足 1 分）");
  assert.equal(format.formatResidual(-0.000057), "-0.000057 元（绝对值不足 1 分）");
  assert.equal(format.formatResidual(0.0099999), "0.0099999 元（绝对值不足 1 分）");
  assert.equal(format.formatResidual(1e-13), "1.00e-13 元（绝对值不足 1 分）");
  assert.equal(format.formatResidual(12.34), "12.34 元");
});

test("中文化仅复制展示文字，所有金额、比率、标识与原始导出保持不变", () => {
  const before = JSON.stringify(bundle);
  const translated = locale.localizeBundle(bundle);
  const textKeys = new Set(["label", "layer_name", "panel_label", "note", "formula", "dpo_method"]);
  for (const [table, rows] of Object.entries(bundle)) {
    if (!Array.isArray(rows)) continue;
    rows.forEach((row, i) => {
      for (const [key, value] of Object.entries(row)) {
        if (textKeys.has(key) || key.endsWith("_flags") || key.endsWith("_note")) continue;
        assert.deepEqual(translated[table][i][key], value, `${table}.${key}`);
      }
    });
  }
  assert.equal(JSON.stringify(bundle), before);
  assert.equal(translated.unit, "CNY_yuan");
});

test("当前所有图节点、瀑布步骤、说明与构成科目均有中文名称", () => {
  const translated = locale.localizeBundle(bundle);
  for (const table of ["cash_bridge", "capital_bridge", "value_bridge", "valuation_bridge", "econ_map_nodes", "driver_tree_nodes"]) {
    for (const row of translated[table]) {
      assert.match(row.label, /[\u4e00-\u9fff]/, row.label);
      for (const key of ["note", "formula", "layer_name"]) {
        if (row[key]) assert.match(row[key], /[\u4e00-\u9fff]/, row[key]);
      }
      for (const component of JSON.parse(row.components_json ?? "[]")) {
        assert.match(locale.accountLabel(component.concept), /[\u4e00-\u9fff]/, component.concept);
      }
    }
  }
  assert.equal(locale.accountLabel("cash_and_equivalents"), "货币资金");
  assert.equal(locale.accountLabel("contract_liabilities"), "合同负债");
});

test("金额图全部采用亿元数据与亿元坐标，无十倍或重复万元换算", () => {
  for (const [component, props, row, keys] of [
    ["CapitalChart", { bs: bundle.reformulated_bs }, bundle.reformulated_bs, ["noa", "nfo", "cse_calc"]],
    ["CapexDaChart", { summary: bundle.capital_summary }, bundle.capital_summary, ["capex_paid", "da_total"]],
    ["FcfChart", { summary: bundle.capital_summary }, bundle.capital_summary, ["fcf_simple", "fcf_from_oi"]],
    ["ResidualChart", { rows: bundle.residual_income }, bundle.residual_income, ["oi_after_tax", "reoi", "re_common"]],
    ["ModelVsMarketChart", { rows: bundle.valuation }, bundle.valuation, ["market_cap", "v_equity_reoi_g", "v_equity_reoi_flat", "v_equity_rnoa_g"]],
    ["DriverEffectsChart", { rows: bundle.residual_income }, bundle.residual_income.filter((r) => r.drivers_available), ["margin_effect", "turnover_effect", "growth_effect", "delta_reoi"]],
  ]) {
    const option = chartOptions(component, props);
    assert.equal(option.yAxis.name, "亿元", component);
    for (const [index, key] of keys.entries()) {
      assert.deepEqual(option.series[index].data, row.map((r) => r[key] === null ? null : r[key] / 100_000_000), `${component}.${key}`);
      assert.match(option.series[index].name, /[\u4e00-\u9fff]/, component);
    }
    const raw = row.at(-1)[keys[0]];
    const formatted = option.tooltip.valueFormatter ? option.tooltip.valueFormatter(raw / 1e8) :
      option.tooltip.formatter([{ dataIndex: row.length - 1, seriesName: "金额", value: raw / 1e8, marker: "" }]);
    assert.ok(formatted.includes("亿元") && !/\dB\b/.test(formatted), component);
  }
});

test("瀑布图正负变化与零值保持准确，数值与提示同为亿元", () => {
  const steps = [
    { label: "期初", concept: "start", value: 1e9, step_kind: "start", step_order: 0 },
    { label: "减少", concept: "change", value: -1e8, step_kind: "adjustment", step_order: 1 },
    { label: "零变动", concept: "zero", value: 0, step_kind: "adjustment", step_order: 2 },
    { label: "期末", concept: "end", value: 9e8, step_kind: "total", step_order: 3 },
  ];
  const bars = data.waterfallBars(steps);
  assert.deepEqual(bars.map((b) => b.span), [10, -1, 0, 9]);
  assert.equal(bars[1].base, 9);
  const option = chartOptions("WaterfallChart", { steps });
  assert.equal(option.yAxis.name, "亿元");
  assert.equal(option.series[1].data[2].value, 0);
  assert.ok(option.tooltip.formatter([{ dataIndex: 1 }, { dataIndex: 1 }]).includes("-1.00 亿元"));
});

test("每股估值保持元/股；敏感性提示与行情市值按已转换的元显示", () => {
  const cell = { r: 0.08, g: 0.03, v_equity: 1e9, v_per_share: 123.45, v_to_p: 1.1 };
  const option = chartOptions("SensitivityHeatmap", { cells: [cell], assumed: null });
  const tooltip = option.tooltip.formatter({ value: [0, 0, 0, 1.1] });
  assert.ok(tooltip.includes("10.00 亿元"));
  assert.ok(tooltip.includes("123.45 元/股"));
  for (const snapshot of bundle.market_snapshot) {
    assert.ok(Math.abs(snapshot.market_cap - snapshot.close * snapshot.shares) / snapshot.market_cap < 1e-8);
    assert.equal(format.toYiYuan(snapshot.market_cap), snapshot.market_cap / 1e8);
  }
});

test("百分比、百分点、周转天数和倍数使用各自单位", () => {
  const returns = chartOptions("ReturnsChart", { ratios: [{ basis: "average", end_date: "20251231", rnoa: 0.123, rotce_direct: 0.1, roce_parent: 0.09 }] });
  assert.equal(returns.series[0].data[0], 12.3);
  assert.equal(returns.tooltip.valueFormatter(12.3), "12.3%");
  const spreads = chartOptions("SpreadChart", { rows: [{ end_date: "20251231", spread_op: 0.01, spread_e: 0.02 }] });
  assert.equal(spreads.yAxis.name, "百分点");
  assert.equal(spreads.tooltip.valueFormatter(spreads.series[0].data[0]), "1.0 个百分点");
  const days = chartOptions("WcDaysChart", { wc: [{ end_date: "20251231", dio: 365, dso: null, dpo: 20, advance_days: 10 }] });
  assert.equal(days.series[0].data[0], 365);
  assert.equal(days.tooltip.valueFormatter(365), "365 天");
  assert.equal(days.series[1].data[0], null);
  const cycle = chartOptions("HistoryChart", { label: "现金循环周期", years: ["2024", "2025"], unit: "天",
    series: [{ label: "现金循环周期（CCC）", color: "#000", values: [-35.4, null] }] });
  assert.equal(cycle.yAxis.name, "天");
  assert.equal(cycle.yAxis.scale, false); // zero stays on the axis: the cash-generative boundary
  assert.deepEqual(cycle.series[0].data, [-35.4, null]);
  assert.equal(cycle.tooltip.valueFormatter(-35.4), "-35 天");
  assert.equal(loadTs("metrics.ts").fmtMetric(0.34, "x"), "0.34 倍");
});

test("数据加载拒绝非人民币元的输入单位，避免错误的重复换算", async () => {
  const originalFetch = globalThis.fetch;
  try {
    const respond = (body, type = "application/gzip") => async (url) => {
      assert.equal(url, "/data/600519.SH.json.gz");
      return new Response(body, { headers: { "content-type": type } });
    };
    globalThis.fetch = respond(gzipSync(JSON.stringify({ ...bundle, unit: "CNY_wan" })));
    await assert.rejects(data.loadBundle("600519.SH"), /金额单位应为人民币元/);
    globalThis.fetch = respond("<!doctype html>", "text/html");
    await assert.rejects(data.loadBundle("600519.SH"), /尚未生成 600519.SH 的分析数据包/);
    // a server that already decoded Content-Encoding: gzip hands over plain JSON
    globalThis.fetch = respond(JSON.stringify(bundle), "application/json");
    assert.equal((await data.loadBundle("600519.SH")).ts_code, "600519.SH");
    globalThis.fetch = respond(gzipSync(JSON.stringify(bundle)));
    const loaded = await data.loadBundle("600519.SH");
    assert.equal(loaded.valuation.at(-1).market_cap, bundle.valuation.at(-1).market_cap);
    assert.match(loaded.econ_map_nodes[0].label, /[\u4e00-\u9fff]/);
  } finally { globalThis.fetch = originalFetch; }
});

test("流水线可能产生的每个提示代码都有中文说明，不向页面输出英文代码", () => {
  const { flagText } = loadTs("locale.ts");
  const dir = new URL("../../pipeline/", import.meta.url);
  const codes = new Set();
  for (const file of readdirSync(dir).filter((name) => name.endsWith(".py"))) {
    const source = readFileSync(new URL(file, dir), "utf8");
    for (const call of source.matchAll(/flags\.append\(([^)]*)\)/g)) {
      for (const code of call[1].matchAll(/"([a-z_]+)"/g)) codes.add(code[1]);
    }
  }
  assert.ok(codes.size >= 30, `found ${codes.size} flag codes`);
  for (const code of codes) assert.match(flagText(code), /[一-鿿]/, code);
});
