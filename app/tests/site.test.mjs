import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { loadTs } from "./load-ts.mjs";

const { makeSite, siteUrl, appPath, bundleUrl } = loadTs("site.ts");
const { expandCalculationDetails } = loadTs("calculationDetails.ts");
const fixture = JSON.parse(readFileSync(new URL("../../tests/fixtures/calculation_details_compact.json", import.meta.url)));

test("本地开发站点位于根路径，数据包均在 /data/", () => {
  assert.equal(siteUrl("/map?year=2025"), "/map?year=2025");
  assert.equal(appPath("/knowledge/ccc"), "/knowledge/ccc");
  assert.equal(bundleUrl("000651.SZ"), "/data/000651.SZ.json.gz");
});

test("GitHub Pages 子路径：站内路径加前缀，浏览器路径去前缀，深证数据包取自数据站点", () => {
  const site = makeSite({ base: "/business-model-explorer/",
    bundleBases: { SZ: "/business-model-explorer-data/data/" } });
  assert.equal(site.siteUrl("/"), "/business-model-explorer/");
  assert.equal(site.siteUrl("/knowledge/ccc?year=2025&company=600519.SH"),
    "/business-model-explorer/knowledge/ccc?year=2025&company=600519.SH");
  assert.equal(site.siteUrl("#cash"), "#cash");
  assert.equal(site.appPath("/business-model-explorer"), "/");
  assert.equal(site.appPath("/business-model-explorer/"), "/");
  assert.equal(site.appPath("/business-model-explorer/drivers"), "/drivers");
  assert.equal(site.appPath("/business-model-explorer-data/x"), "/business-model-explorer-data/x");
  assert.equal(site.bundleUrl("600519.SH"), "/business-model-explorer/data/600519.SH.json.gz");
  assert.equal(site.bundleUrl("430047.BJ"), "/business-model-explorer/data/430047.BJ.json.gz");
  assert.equal(site.bundleUrl("000651.SZ"), "/business-model-explorer-data/data/000651.SZ.json.gz");
});

test("发布版计算明细按科目压缩，前端展开后与导出索引完全一致", () => {
  assert.deepEqual(expandCalculationDetails(fixture.compact), fixture.expanded);
  assert.equal(expandCalculationDetails(fixture.expanded), fixture.expanded);
  assert.equal(expandCalculationDetails(undefined), undefined);
});
