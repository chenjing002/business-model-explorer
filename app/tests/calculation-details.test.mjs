import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import test from "node:test";
import { loadTs } from "./load-ts.mjs";

const bundle = JSON.parse(gunzipSync(readFileSync(new URL("../public/data/600519.SH.json.gz", import.meta.url))));
const index = bundle.calculation_details;
const { calculationHtml, calculationValue } = loadTs("calculationDetails.ts");

test("原始计算项可追溯到跨年余额、原始字段和归母综合收益", () => {
  const date = "20251231";
  const rnoa = calculationHtml(index, date, "rnoa");
  assert.match(rnoa, /2024年 净经营资产/);
  assert.match(rnoa, /balancesheet.inventories/);
  assert.match(rnoa, /income.n_income/);
  const re = calculationHtml(index, date, "re_0");
  assert.match(re, /income.compr_inc_attr_p/);
  assert.match(re, /82,324,204,482\.75 元/);
  assert.equal(index[date].rnoa.value, bundle.ratios.find((r) => r.end_date === date && r.basis === "average").rnoa);
});

test("估值、价差、未披露输入及行情原值各保留单位与口径", () => {
  const date = "20251231";
  const perShare = calculationHtml(index, date, "v_per_share");
  assert.match(perShare, /1,505\.54 元\/股/);
  assert.match(perShare, /1,252,270,215 股/);
  assert.match(perShare, /125,227\.0215 万股/);
  assert.match(perShare, /daily_basic.total_share/);
  assert.match(calculationValue(index[date]["tree:spread"]), /个百分点$/);
  assert.match(calculationHtml(index, "20211231", "dso"), /未披露应收款项数据/);
  assert.equal(index["20211231"].dso.value, null);
});
