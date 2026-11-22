import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { createRequire } from "node:module";
import test from "node:test";
import { loadTs } from "./load-ts.mjs";

const require = createRequire(import.meta.url);
const routes = loadTs("routes.ts");
const knowledge = loadTs("knowledge.ts", { "./routes": routes });
const metrics = loadTs("metrics.ts", { "./data": loadTs("data.ts") });
const { CONCEPTS, CONCEPT_BY_ID, REFERENCES, conceptFor, searchConcepts } = knowledge;
const bundle = JSON.parse(gunzipSync(readFileSync(new URL("../public/data/600519.SH.json.gz", import.meta.url))));

test("concepts have unique stable slugs and complete explanations", () => {
  assert.equal(CONCEPTS.length, CONCEPT_BY_ID.size);
  for (const entry of CONCEPTS) {
    assert.match(entry.id, /^[a-z]+(?:-[a-z]+)*$/);
    for (const key of ["title", "category", "definition", "formula", "interpretation", "convention", "caveat"]) {
      assert.ok(entry[key].trim(), `${entry.id}: missing ${key}`);
    }
    assert.ok(entry.aliases.length && entry.related.length && entry.views.length, entry.id);
  }
});

test("related concepts, sources and application destinations resolve", () => {
  for (const entry of CONCEPTS) {
    for (const id of entry.related) assert.ok(CONCEPT_BY_ID.has(id), `${entry.id} -> ${id}`);
    for (const view of entry.views) assert.ok(routes.VIEW_PATHS[view], view);
    for (const source of entry.sources) {
      const href = REFERENCES[source]?.href ?? "";
      if (source === "penman-valuation") {
        assert.ok(readFileSync(new URL(`../public${href}`, import.meta.url)).subarray(0, 4).equals(Buffer.from("%PDF")));
      } else {
        assert.match(href, /^https:\/\//);
      }
    }
  }
  // No isolated articles: every concept is discoverable through related reading.
  const reached = new Set();
  const pending = ["noa"];
  while (pending.length) {
    const id = pending.pop();
    if (reached.has(id)) continue;
    reached.add(id);
    pending.push(...CONCEPT_BY_ID.get(id).related);
  }
  assert.equal(reached.size, CONCEPTS.length);
});

test("every exported map node, tree node and related metric has a concept", () => {
  for (const key of Object.keys(metrics.METRIC_SOURCES)) {
    assert.ok(CONCEPT_BY_ID.has(conceptFor("metrics", key)), `declared metric: ${key}`);
  }
  for (const [kind, table] of [["map", "econ_map_nodes"], ["tree", "driver_tree_nodes"]]) {
    for (const node of bundle[table]) {
      assert.ok(CONCEPT_BY_ID.has(conceptFor(kind, node.node_id)), `${kind}: ${node.node_id}`);
      for (const key of JSON.parse(node.related_json)) {
        assert.ok(CONCEPT_BY_ID.has(conceptFor("metrics", key)), `metric: ${key}`);
      }
    }
  }
  assert.equal(conceptFor("metrics", "unknown"), undefined);
});

test("search handles acronyms, Chinese aliases, multiple terms and whitespace", () => {
  for (const [query, id] of [["  rNoA  ", "rnoa"], ["营运资本", "owc"], ["net operating assets", "noa"], ["dirty surplus", "equity-re"]]) {
    assert.ok(searchConcepts(query, "").some((entry) => entry.id === id), query);
  }
  assert.equal(searchConcepts("   ", "").length, CONCEPTS.length);
  assert.deepEqual(searchConcepts("no-such-concept-123", ""), []);
});

test("topic and search filters combine without hiding all-results recovery", () => {
  assert.equal(knowledge.CATEGORIES.length, 6);
  const results = searchConcepts("天数", "营运资本");
  assert.ok(results.length >= 4);
  assert.ok(results.every((entry) => entry.category === "营运资本"));
  assert.deepEqual(searchConcepts("RNOA", "营运资本"), []);
  assert.equal(searchConcepts("", "").length, CONCEPTS.length);
});

test("knowledge articles render without company data and recover invalid slugs", () => {
  const navigation = loadTs("Navigation.tsx");
  const knowledgeLinks = loadTs("KnowledgeLink.tsx", { "./Navigation": navigation, "./routes": routes, "./knowledge": knowledge });
  const { KnowledgeView } = loadTs("KnowledgeView.tsx", {
    "./Navigation": navigation, "./KnowledgeLink": knowledgeLinks, "./knowledge": knowledge, "./routes": routes,
  });
  const { createElement } = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  for (const entry of CONCEPTS) {
    const html = renderToStaticMarkup(createElement(KnowledgeView, { concept: entry.id, year: "2020" }));
    assert.ok(html.includes('id="concept-title"'), entry.id);
    assert.ok(html.includes("如何解读") && html.includes("注意事项"), entry.id);
    assert.ok(html.includes("?year=2020"), entry.id);
  }
  const html = renderToStaticMarkup(createElement(KnowledgeView, { concept: "unknown", year: "2020" }));
  assert.ok(html.includes("未找到该概念") && html.includes("浏览财务知识库"));
});

test("direct article URLs round-trip year context and application routes", () => {
  for (const entry of CONCEPTS) {
    const url = new URL(routes.withYear(`/knowledge/${entry.id}`, "2020"), "http://localhost");
    assert.deepEqual(routes.parseRoute(url.pathname, url.search), { view: "knowledge", concept: entry.id, year: "2020" });
  }
  for (const [view, path] of Object.entries(routes.VIEW_PATHS)) {
    assert.equal(routes.parseRoute(path, "").view, view);
  }
  assert.equal(routes.withYear("/knowledge", ""), "/knowledge");
});

test("unknown URLs, trailing slashes and malformed year inputs are handled", () => {
  assert.deepEqual(routes.parseRoute("/knowledge/", "?year=2025"), { view: "knowledge", concept: "", year: "2025" });
  assert.equal(routes.parseRoute("/knowledge/unknown", "").concept, "unknown");
  assert.equal(routes.parseRoute("/unknown", "").view, undefined);
  assert.equal(routes.parseRoute("/knowledgeable", "").view, undefined);
  assert.equal(routes.parseRoute("/knowledge/%E0%A4%A", "?year=bad").year, "");
});
