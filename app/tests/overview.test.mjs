import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { loadTs } from "./load-ts.mjs";

const bundle = JSON.parse(gunzipSync(readFileSync(new URL("../public/data/600519.SH.json.gz", import.meta.url))));
const { Overview } = loadTs("Overview.tsx");
const { localizeBundle } = loadTs("locale.ts");
const { CompanyContext } = loadTs("Navigation.tsx");
const { parseRoute } = loadTs("routes.ts");

function render(company, year, companyParam = "") {
  return renderToStaticMarkup(createElement(CompanyContext.Provider, { value: companyParam },
    createElement(Overview, { bundle: localizeBundle(company), year })));
}

test("总览串联业务、年度变化与现金用途，年报披露附来源页码", () => {
  const html = render(bundle, "2025");
  for (const text of [
    "这是一门什么样的生意？", "当年这门生意发生了什么变化？", "创造出来的利润最终去了哪里？",
    "其他系列酒", "93.53%", "64.8%", "754.22 亿元", "122.8%", "-39.8 个百分点",
    "-1.21%", "+129.78 亿元", "自制半成品", "+39.32 亿元", "1,839.90 亿元",
    "615.22 亿元", "72.1%", "286.42 亿元", "672.42 亿元", "61.21 亿元", "-435.44 亿元",
    "#page=10", "#page=91", "#page=114",
  ]) assert.ok(html.includes(text), text);
});

test("报告期切换不复用其他年份的年报披露，首年展示缺少期初余额", () => {
  const earlier = render(bundle, "2014");
  assert.match(earlier, /aria-label="2014 年经营总览"/);
  // The banner (company line, title, section shortcuts, report link) was removed.
  assert.doesNotMatch(earlier, /overview__header|总览章节/);
  assert.match(earlier, /缺少期初余额/);
  assert.match(earlier, /缺少单项披露/);
  assert.doesNotMatch(earlier, /其他系列酒|61\.21 亿元|不可随时支取|#page=/);
});

test("总览前部展示截至所选财年的十年趋势及可查的逐年明细", () => {
  const latest = render(bundle, "2025");
  const history = latest.slice(latest.indexOf('<section id="historical-performance"'), latest.indexOf('<section id="business-model"'));
  for (const text of ["2016–2025 年", "853.10 亿元", "583.95 亿元", "46.63 元/股", "34.40%",
    "销售净利率", "总资产周转率", "权益乘数（财务杠杆）", "历年杜邦分析", "dex991.htm"]) {
    assert.ok(history.includes(text), text);
  }
  assert.doesNotMatch(history, /2015 年/);

  const earlier = render(bundle, "2018");
  assert.match(earlier, /2014–2018 年/);
  assert.doesNotMatch(earlier, /2019 年|2025 年/);
});

test("历年净利润、折旧摊销、经营现金流与资本开支按年份横向列示，表头统一亿元单位", () => {
  const html = render(bundle, "2025");
  const start = html.indexOf('aria-label="历年净利润、折旧摊销、经营现金流与资本开支"');
  assert.ok(start > 0);
  const table = html.slice(start, html.indexOf("</table>", start));
  assert.match(html, /单位：亿元（末行为倍数）· 条形按本行最大值缩放/);
  const labels = ["合并净利润", "归母净利润", "折旧摊销（D&amp;A）", "经营活动现金流量净额", "减：现金资本开支",
    "自由现金流（FCF）", "资本开支／折旧摊销"];
  // Profit rows open the table, in this order.
  const positions = labels.map((label) => table.indexOf(label));
  assert.ok(positions.every((at, i) => at > 0 && (i === 0 || at > positions[i - 1])), positions.join(","));
  for (const text of ["<th scope=\"col\" class=\"overview__flow-current\">2025</th>",
    // 2016 and 2025: NI, parent NI, D&A, CFO, capex, FCF in 亿元 without a per-cell unit, then the multiple.
    ">179.31<", ">167.18<", ">9.34<", ">374.51<", ">10.19<", ">364.32<", "1.09 倍",
    ">853.10<", ">823.20<", ">22.59<", ">615.22<", ">31.28<", ">583.95<", "1.38 倍"]) {
    assert.ok(table.includes(text), text);
  }
  assert.doesNotMatch(table, /2015|亿元/);
  // The net income / FCF chart card is replaced by the table's profit rows.
  assert.doesNotMatch(html, /<h4>净利润与自由现金流<\/h4>/);
  assert.match(html, /每股自由现金流/);

  const missing = render({ ...bundle, capital_summary: [] }, "2025");
  assert.match(missing, /补充资料未披露/);
  assert.match(missing, /缺少折旧摊销或资本开支/);
});

test("每股自由现金流下方展示现金循环周期卡片、扣除预收款口径及逐年天数", () => {
  const html = render(bundle, "2025");
  const history = html.slice(html.indexOf('<section id="historical-performance"'), html.indexOf('<section id="business-model"'));
  const card = history.slice(history.indexOf("overview__history-ccc"), history.indexOf("杜邦三因素拆分"));
  assert.ok(history.indexOf("每股自由现金流") < history.indexOf("overview__history-ccc"));
  // 2025: CCC = 1418.7 + 7.0 − 62.5; netting 19.0 advance days.
  for (const text of ["现金循环周期（CCC）", "1363 天", "扣除客户预收款后", "1344 天", "经营周期需垫付营运资金",
    "存货天数以营业成本为分母", "/knowledge/ccc"]) assert.ok(card.includes(text), text);
  assert.doesNotMatch(card, /现金生成型/);
  const table = history.slice(history.indexOf('aria-label="历年现金循环周期"'));
  for (const text of ["客户预收款天数", "1419 天", "63 天", "19 天", "2016 年"]) assert.ok(table.includes(text), text);
  // 2021–22 disclose no receivables: CCC stays missing with the reason, never zero.
  const gap = render(bundle, "2022");
  const gapCard = gap.slice(gap.indexOf("overview__history-ccc"), gap.indexOf("杜邦三因素拆分"));
  assert.match(gapCard, /未披露应收款项数据/);
  assert.doesNotMatch(gapCard, /现金生成型|需垫付/);

  const negative = render({ ...bundle, working_capital: bundle.working_capital.map((row) =>
    row.end_date === "20251231" ? { ...row, ccc: -35, ccc_net_advances: -54 } : row) }, "2025");
  assert.match(negative, /-35 天/);
  assert.match(negative, /现金生成型：先收客户款，后付供应商款/);

  const legacy = render({ ...bundle, working_capital: bundle.working_capital.map(({ ccc_net_advances, ...row }) => row) }, "2025");
  assert.match(legacy, /重新导出数据包后可查看扣除客户预收款后的现金循环周期/);
  assert.match(legacy, /1363 天/);
  assert.doesNotMatch(legacy, /扣除客户预收款后 </);
});

test("没有附注的新公司和旧版数据包共用总览，详情链接携带公司与年度", () => {
  const code = "002000.SZ";
  const html = render({
    ...bundle, ts_code: code, overview: undefined, calculation_details: undefined,
    reformulated_is: [{ end_date: "20251231", period_kind: "cumulative", revenue: 1.2e9 }],
  }, "2025", code);
  assert.match(html, /002000\.SZ/);
  assert.match(html, /12\.00 亿元/);
  assert.match(html, /暂无本年分产品或业务/);
  assert.match(html, /重新导出数据包后可查看每股自由现金流和杜邦分析/);
  assert.match(html, /583\.95 亿元/);
  assert.match(html, /href="\/capital\?year=2025&amp;company=002000\.SZ"/);
  assert.doesNotMatch(html, /贵州茅台|其他系列酒|#page=/);
  assert.equal(parseRoute("/", "?company=002000.sz&year=2025").company, code);
  assert.equal(parseRoute("/", "?company=..%2Fdata").company, undefined);
});
