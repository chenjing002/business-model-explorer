import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadTs } from "./load-ts.mjs";

const bundle = JSON.parse(gunzipSync(readFileSync(new URL("../public/data/600519.SH.json.gz", import.meta.url))));
const locale = loadTs("locale.ts");
const { EvolutionSection } = loadTs("EconEvolution.tsx");

const localized = locale.localizeBundle(bundle);
const years = [...new Set(bundle.econ_evolution_groups.map((g) => g.end_date.slice(0, 4)))].sort();

function render(year, selected = "inventory") {
  return renderToStaticMarkup(createElement(EvolutionSection, {
    bundle: localized, year, selected, onSelect: () => {},
  }));
}

test("年度演化：期初+披露流量+推算轧差=期末，披露与推算在导出数据中显式区分", () => {
  const latest = years[years.length - 1];
  const flows = bundle.econ_evolution_flows.filter((f) => f.end_date.startsWith(latest));
  const panels = [...new Set(flows.map((f) => f.panel_id))];
  assert.equal(panels.length, 9);
  for (const p of panels) {
    const steps = flows.filter((f) => f.panel_id === p).sort((a, b) => a.step_order - b.step_order);
    assert.equal(steps[0].step_kind, "start");
    assert.equal(steps.at(-1).step_kind, "total");
    // 每个面板恰有一条推算轧差；桥按构造精确可加
    const residuals = steps.filter((s) => s.basis === "inferred_residual");
    assert.equal(residuals.length, 1);
    const sum = steps[0].value + steps.filter((s) => s.step_kind === "adjustment")
      .reduce((acc, s) => acc + s.value, 0);
    assert.ok(Math.abs(sum - steps.at(-1).value) < 1e-3, `${p} additive`);
  }
  // 两端变动合计与报表总资产变动的恒等式校验在导出中为 0
  const checks = bundle.econ_evolution_checks.filter((c) => c.end_date.startsWith(latest));
  for (const prefix of ["E1", "E2"]) {
    const c = checks.find((x) => x.check.startsWith(prefix));
    assert.ok(Math.abs(c.residual) < 1e-3, c.check);
  }
});

test("年度演化渲染：发散变动行、勾稽桥与口径声明齐备", () => {
  const latest = years[years.length - 1];
  const html = render(latest);
  assert.match(html, /年度演化/);
  assert.match(html, /期初余额/);
  assert.match(html, /期末余额/);
  assert.match(html, /推算轧差/);
  assert.match(html, /不代表科目之间的直接转换/);
  assert.match(html, /占年初总资产/);
  // 选中存货 → 显示存货面板的补充资料披露项
  assert.match(html, /存货变动（补充资料披露）/);
  // 披露与推算的图例
  assert.match(html, /披露流量（现金流量表／补充资料／利润表）/);
});

test("首个年度缺少期初余额时如实说明，不虚构演化", () => {
  const html = render(years[0]);
  assert.match(html, /缺少期初余额，无法展示年度演化/);
  assert.doesNotMatch(html, /推算轧差/);
});
