import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadTs } from "./load-ts.mjs";

const { adjacentCompany, availability, buildIndex, companyOrder, searchCompanies, CHECK_FAMILY_LABELS, STEP_LABELS, UNKNOWN_INDUSTRY } = loadTs("companies.ts");
const routes = loadTs("routes.ts");
const { CompanyPicker } = loadTs("CompanyPicker.tsx");

const index = buildIndex({
  analyzed: ["600519.SH"],
  companies: [
    { ts_code: "000001.SZ", name: "平安银行", industry: "银行", cnspell: "PAYH", market: "主板" },
    { ts_code: "000858.SZ", name: "五粮液", industry: "白酒", cnspell: "WLY", market: "主板" },
    { ts_code: "600519.SH", name: "贵州茅台", industry: "白酒", cnspell: "GZMT", market: "主板" },
    { ts_code: "600600.SH", name: "青岛啤酒", industry: "啤酒", cnspell: "QDPJ", market: "主板" },
    { ts_code: "688001.SH", name: "测试科技", industry: null, cnspell: "CSKJ", market: "科创板" },
  ],
});
const shape = (groups) => groups.map((g) => [g.industry, g.companies.map((c) => c.ts_code)]);

test("公司列表按行业分组：当前公司所在行业在前，未披露行业置后且不臆造", () => {
  assert.deepEqual(shape(searchCompanies(index, "", "600519.SH")), [
    ["白酒", ["600519.SH", "000858.SZ"]],
    ["啤酒", ["600600.SH"]],
    ["银行", ["000001.SZ"]],
    [UNKNOWN_INDUSTRY, ["688001.SH"]],
  ]);
  // 同一行业内已分析公司在前，其余按代码排序
  assert.equal(searchCompanies(index, "", "000001.SZ")[0].industry, "银行");
});

test("可按公司名称、代码、拼音首字母或行业搜索", () => {
  assert.deepEqual(shape(searchCompanies(index, "茅台")), [["白酒", ["600519.SH"]]]);
  assert.deepEqual(shape(searchCompanies(index, "600519")), [["白酒", ["600519.SH"]]]);
  assert.deepEqual(shape(searchCompanies(index, "000858.sz")), [["白酒", ["000858.SZ"]]]);
  assert.deepEqual(shape(searchCompanies(index, "wly")), [["白酒", ["000858.SZ"]]]);
  // 行业名命中整组；公司名直接命中（青岛啤酒）的行业排在仅行业命中之前，组内已分析在前
  assert.deepEqual(shape(searchCompanies(index, "酒")), [
    ["啤酒", ["600600.SH"]],
    ["白酒", ["600519.SH", "000858.SZ"]],
  ]);
  assert.deepEqual(shape(searchCompanies(index, "白酒 五")), [["白酒", ["000858.SZ"]]]);
  assert.deepEqual(searchCompanies(index, "不存在的公司"), []);
});

test("← → 按行业顺序切换上一家 / 下一家已分析公司，跳过未分析并首尾循环", () => {
  const browsing = buildIndex({ analyzed: ["600519.SH", "000858.SZ", "600600.SH"], companies: index.companies });
  const order = companyOrder(browsing);
  // 行业按中文排序（与当前公司无关），未披露行业置后
  assert.deepEqual(order, ["000858.SZ", "600519.SH", "600600.SH", "000001.SZ", "688001.SH"]);
  assert.equal(adjacentCompany(browsing, order, "000858.SZ", 1), "600519.SH");
  assert.equal(adjacentCompany(browsing, order, "600519.SH", 1), "600600.SH");
  // 跳过未分析的平安银行、测试科技，循环回到首家
  assert.equal(adjacentCompany(browsing, order, "600600.SH", 1), "000858.SZ");
  assert.equal(adjacentCompany(browsing, order, "000858.SZ", -1), "600600.SH");
  // 当前停在未分析公司上也能继续切换
  assert.equal(adjacentCompany(browsing, order, "000001.SZ", 1), "000858.SZ");
  assert.equal(adjacentCompany(browsing, order, "000001.SZ", -1), "600600.SH");
  // 列表外代码：→ 到首家，← 到末家
  assert.equal(adjacentCompany(browsing, order, "999999.SH", 1), "000858.SZ");
  assert.equal(adjacentCompany(browsing, order, "999999.SH", -1), "600600.SH");
  // 只有一家已分析时不切换
  assert.equal(adjacentCompany(index, companyOrder(index), "600519.SH", 1), null);
});

test("公司切换器显示名称、代码与行业，收起时不渲染完整列表", () => {
  const html = renderToStaticMarkup(createElement(CompanyPicker, {
    index, error: null, current: "600519.SH", currentName: "贵州茅台", onSelect: () => {},
  }));
  assert.ok(html.includes("贵州茅台"));
  assert.ok(html.includes("600519.SH · 白酒"));
  assert.ok(html.includes('aria-expanded="false"'));
  assert.ok(!html.includes('role="listbox"'));
});

test("财务知识库与参考案例为网站级导航，公司页面只含公司分析", () => {
  assert.deepEqual([...routes.COMPANY_VIEWS], ["overview", "map", "tree", "capital", "value", "valuation"]);
  for (const view of ["knowledge", "cases", undefined]) assert.equal(routes.isCompanyView(view), false);
  for (const view of routes.COMPANY_VIEWS) assert.equal(routes.isCompanyView(view), true);
  const app = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");
  assert.ok(app.includes('aria-label="网站导航"'));
  assert.ok(app.includes("{companyView && <section className=\"companybar\""));
});


test("未分析公司显示批量分析给出的原因，失败时注明中文步骤", () => {
  const withReasons = buildIndex({
    analyzed: ["600519.SH"],
    unavailable: {
      "000001.SZ": { reason: "financial", step: null },
      "000858.SZ": { reason: "error", step: "reformulate" },
      "688001.SH": { reason: "no_annual_report", step: null },
    },
    check_failures: { "600519.SH": ["R1", "L"] },
    companies: index.companies,
  });
  assert.equal(availability(withReasons, "600519.SH"), null);
  assert.equal(availability(withReasons, "000001.SZ").tag, "金融类");
  assert.match(availability(withReasons, "000001.SZ").text, /金融类科目映射/);
  assert.deepEqual([availability(withReasons, "000858.SZ").tag, availability(withReasons, "000858.SZ").step], ["分析失败", "报表重构"]);
  assert.equal(availability(withReasons, "688001.SH").tag, "无年报");
  // 不在任何列表中 = 尚未运行
  assert.equal(availability(withReasons, "600600.SH").tag, "未分析");
  assert.deepEqual(withReasons.checkFailures.get("600519.SH"), ["R1", "L"]);
  // 每个批量分析步骤与校验族都有中文名称
  const pipeline = readFileSync(new URL("../../pipeline/bulk_analyze.py", import.meta.url), "utf8");
  for (const step of pipeline.matchAll(/\("([a-z]+)", lambda: /g)) assert.ok(STEP_LABELS[step[1]], step[1]);
  const families = pipeline.slice(pipeline.indexOf("CHECK_FAMILIES = {"), pipeline.indexOf("INFORMATIONAL_CHECKS"));
  for (const family of families.matchAll(/^    "([A-Z0-9]+)":/gm)) {
    if (family[1] !== "L4") assert.ok(CHECK_FAMILY_LABELS[family[1]], family[1]);
  }
});
