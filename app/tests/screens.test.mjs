import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadTs } from "./load-ts.mjs";

// Pinned by tests/test_screens.py (synthetic companies, not real data).
const sample = JSON.parse(readFileSync(new URL("../../tests/fixtures/screens_sample.json", import.meta.url)));
const { ScreensPage } = loadTs("ScreensView.tsx");
const { formatScreenValue } = loadTs("screens.ts");
const { CONCEPT_BY_ID } = loadTs("knowledge.ts");
const { parseRoute, VIEW_PATHS } = loadTs("routes.ts");
const render = (initial) => renderToStaticMarkup(createElement(ScreensPage, { data: sample, initial }));

test("首页为好生意榜单，公司总览移至 /overview", () => {
  assert.equal(parseRoute("/", "").view, "home");
  assert.equal(parseRoute("/overview", "?company=600519.SH").view, "overview");
  assert.equal(VIEW_PATHS.overview, "/overview");
});

test("榜单页说明口径与剔除数量，六个榜单卡片带入选家数和前几名", () => {
  const html = render();
  for (const text of ["好生意榜单", "2021–2025 年", "不构成投资建议", "参与排名 <strong>3</strong> 家",
    "低于 10.00 亿元 的 1 家", "多项入选", "自由现金流持续增长", "高且稳定的净资产收益率",
    "经营资产回报高", "先收款后付款", "利润含金量高", "示例丙、示例甲、示例乙"]) assert.ok(html.includes(text), text);
  assert.equal((html.match(/class="screens__card"/g) ?? []).length, 6);
  assert.match(html, /aria-pressed="true"[^>]*><span class="screens__card-head"><strong>多项入选/);
});

test("默认展示多项入选：公司链接到所选财年总览，金额按亿元，缺失值不显示为零", () => {
  const html = render();
  assert.match(html, /href="\/overview\?year=2025&amp;company=T00003\.SZ"/);
  assert.match(html, /自由现金流持续增长、高且稳定的净资产收益率/);
  assert.match(html, /900\.00 亿元/);
  // T00003 has no year-end price: the market-cap cell is "—", never 0.
  assert.match(html, /<td>25\.8%<\/td><td>—<\/td><td><svg/);
  assert.match(html, /<svg class="screens__spark"[^>]*aria-label="归母净资产收益率：2021 年 25\.0%/);
});

test("各榜单按自身单位展示：天数、倍数、百分比", () => {
  const cycle = render("cash_cycle");
  assert.match(cycle, /先收款后付款/);
  assert.match(cycle, /-10 天/);
  assert.match(cycle, /-30 天/);
  assert.match(render("high_rnoa"), /3\.00 倍/);
  assert.equal(formatScreenValue(null, "pct"), "—");
  assert.equal(formatScreenValue(0.1234, "pct"), "12.3%");
  assert.equal(formatScreenValue(4, "count"), "4");
  assert.equal(formatScreenValue(1.5e9, "CNY_yuan"), "15.00 亿元");
});

test("榜单引用的知识库概念都存在", () => {
  for (const list of sample.lists) for (const id of list.concepts) assert.ok(CONCEPT_BY_ID.has(id), id);
});
