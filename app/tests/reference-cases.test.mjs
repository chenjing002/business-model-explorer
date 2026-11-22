import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadTs } from "./load-ts.mjs";

const routes = loadTs("routes.ts");
const cases = loadTs("referenceCases.ts");
const { ReferenceCasesContent } = loadTs("ReferenceCasesView.tsx");

test("案例深链接保留分析年度，并独立识别未知案例", () => {
  for (const entry of cases.CASES) {
    const route = routes.parseRoute(`/cases/${entry.id}/`, "?year=2020");
    assert.equal(route.view, "cases");
    assert.equal(route.caseId, entry.id);
    assert.equal(route.year, "2020");
  }
  assert.equal(routes.parseRoute("/cases", "").caseId, "");
  assert.equal(routes.parseRoute("/cases/unknown", "").caseId, "unknown");
  assert.equal(routes.parseRoute("/cases-other", "").view, undefined);
});

test("参考案例只显示贵州茅台，旧案例链接显示未找到", () => {
  assert.deepEqual(cases.CASES.map((entry) => entry.id), ["moutai-600519"]);
  const index = renderToStaticMarkup(createElement(ReferenceCasesContent,
    { caseId: "", year: "2020", bundle }));
  assert.ok(index.includes("贵州茅台 600519：六步读商业实质"));
  assert.ok(index.includes("第一步 · 总览"));
  assert.ok(!index.includes("Amazon 2004：周转与现金"));
  assert.ok(!index.includes("运输设备：增长的资本代价"));
  for (const caseId of ["amazon-2004", "transport-machine", "unknown"]) {
    const html = renderToStaticMarkup(createElement(ReferenceCasesContent,
      { caseId, year: "2020", bundle }));
    assert.ok(html.includes("未找到该参考案例"));
    assert.ok(html.includes('href="/cases?year=2020"'));
    assert.ok(!html.includes("第一步 · 总览"));
  }
});

const bundle = JSON.parse(gunzipSync(readFileSync(new URL("../public/data/600519.SH.json.gz", import.meta.url))));

test("茅台案例按六步渲染公司数据包，金额为亿元，深链接锚定最新年度", () => {
  const html = renderToStaticMarkup(createElement(ReferenceCasesContent,
    { data: null, caseId: "moutai-600519", year: "2020", bundle }));
  for (const step of ["第一步 · 总览", "第二步 · 商业经济地图", "第三步 · 盈利驱动树",
    "第四步 · 资本与再投资", "第五步 · 价值创造", "第六步 · 估值与反向分析", "商业实质小结与口径"]) {
    assert.ok(html.includes(step), step);
  }
  // 数据包中的已算结果按中文口径展示（2025 年锚定）。
  for (const text of ["1,720.54 亿元", "-1,785.37 亿元", "122.8%", "34.4%", "4.58 倍",
    "70.84 亿元", "1419 天", "121 天", "19 天", "796.46 亿元", "1,377.18 元/股", "2.5%"]) {
    assert.ok(html.includes(text), text);
  }
  // 六步深链接到各分析页并锚定数据包最新年度；知识库链接全部有效。
  for (const path of ["/overview?year=2025", "/map?year=2025", "/drivers?year=2025",
    "/capital?year=2025", "/value?year=2025", "/valuation?year=2025"]) {
    assert.ok(html.includes(`href="${path}"`), path);
  }
  for (const id of [...html.matchAll(/href="\/knowledge\/([a-z-]+)/g)].map((m) => m[1])) {
    assert.ok(loadTs("knowledge.ts").CONCEPT_BY_ID.has(id), id);
  }
  assert.ok(html.includes("不等同于报表“营业利润”"));
  assert.ok(html.includes('href="/data/600519.SH.json.gz"'));
  assert.ok(!html.includes("8.2768"), "公司案例不应出现翻译案例的汇率说明");
});

test("茅台案例在公司数据缺失、加载失败或代码不符时给出可读状态", () => {
  const loading = renderToStaticMarkup(createElement(ReferenceCasesContent,
    { data: null, caseId: "moutai-600519", year: "2020", bundle: null }));
  assert.ok(loading.includes("正在加载公司数据"));
  const failed = renderToStaticMarkup(createElement(ReferenceCasesContent,
    { data: null, caseId: "moutai-600519", year: "2020", bundle: null, bundleError: "网络 404" }));
  assert.ok(failed.includes("公司数据加载失败") && failed.includes("网络 404"));
  const mismatch = renderToStaticMarkup(createElement(ReferenceCasesContent,
    { data: null, caseId: "moutai-600519", year: "2020", bundle: { ...bundle, ts_code: "000001.SZ" } }));
  assert.ok(mismatch.includes("案例与当前数据包不匹配") && mismatch.includes("000001.SZ"));
});

