# Module 13: Financial concepts knowledge base

**Status: done (2026-11-19).**

The `/knowledge` page explains the conventions behind the existing analysis,
with 35 entries in six topics: capital/classification, profitability, working
capital, cash/reinvestment, value/valuation and data conventions.

Each entry has a definition, formula, interpretation, app-specific convention,
caveat, related concepts and links back to the relevant analysis views.
Stephen H. Penman's 2002 paper is the primary valuation reference. The
knowledge page links to the included paper and to the relevant published
page ranges. The Nissim–Penman ratio paper, ACCA and SEC references supplement
the operating ratio, working capital and statement-based FCF entries.

## Files

- `app/src/knowledge/concepts.json`: editable concept content, aliases and links.
- `app/src/knowledge/links.json`: explicit metric/map/tree-to-concept mappings.
- `app/src/knowledge.ts`: typed catalog, reference metadata and search.
- `app/src/KnowledgeView.tsx`: searchable index and article reader.
- `app/src/KnowledgeLink.tsx`: contextual links and chart concept lists.
- `app/src/routes.ts` / `Navigation.tsx`: URL parsing and native anchor navigation.
- `app/tests/knowledge.test.mjs`: eight offline frontend tests.
- `docs/module-13-knowledge.png`: browser-verified page screenshot.

## Navigation and discovery

The app now has real URLs, with client-side navigation and browser
Back/Forward support:

| URL | View |
| --- | --- |
| `/` | Overview |
| `/map` | Economics Map |
| `/drivers` | Driver Tree |
| `/capital` | Capital |
| `/value` | Value Creation |
| `/valuation` | Valuation |
| `/knowledge` | Knowledge home, initially showing the Penman paper guide |
| `/knowledge/rnoa` | An individually addressable concept |

`?year=2020` preserves the selected year through view changes, contextual
links and return links. Unknown routes and unknown concept slugs show a
recovery link. Direct entry and refresh work through Vite's SPA fallback;
future static hosting must also route these paths to `index.html`.

Search is case-insensitive, matches all whitespace-separated terms, and
includes acronyms, explanations, formulas and Chinese aliases. Topic and
search filters combine; zero results offer a clear-filters action. Filters
stay while reading another article and reset when leaving the knowledge view.
The reader uses a sidebar on wide screens and a bounded index above the
article on narrow screens. Deep-linked article headings receive keyboard
focus and scroll into view when needed.

## Integration and conventions

All six analysis views link to relevant concepts. Every exported Economics
Map node and Driver Tree node has an explicit concept mapping; related-metric
labels link directly to their definitions. The tests check coverage against
the current exported bundle and every declared shared metric.

Entries preserve the analytical distinctions made in Modules 1–12:

- Average versus opening capital; total equity versus parent equity.
- Product-revenue gross margin versus total-revenue operating margin.
- After-tax operating/financing reformulation and explicit tax assumptions.
- Purchase-estimate DPO versus COGS DPO; customer advances separate from CCC.
- Statement-based versus reformulated FCF and their reported differences.
- Residual earnings, perpetual-growth assumptions and hindsight price anchors.
- Missing disclosure, suppression and formula-specific absent-component rules.

Knowledge rendering does not require a company bundle to load successfully.
The annual bundle includes an optional `calculation_details` index for formulas, operands and source field metadata. See the [financial review](penman-financial-review.md).
The website and knowledge text default to Simplified Chinese, with English
abbreviations and bilingual search aliases. A dedicated units entry explains
元/万元/亿元 and the distinction between aggregate money and 元/股. See
`docs/chinese-display-and-units.md` for the full presentation convention.

## Validation

- `cd app && npm test`: **17/17 pass**. Content completeness; connected related
  concepts; valid source/view targets; complete map/tree/metric coverage;
  bilingual and multi-term search; combined filters; rendering all 34 articles
  without company data; unknown-article recovery; URL/year round trips and
  malformed inputs.
- `.venv/bin/pytest tests/ -q`: **101/101 pass**.
- `cd app && npm run build`: strict TypeScript and production build pass.
  The existing ECharts bundle-size warning remains (~427 KB gzip total JS).
- Browser checks: direct article refresh, Chinese search, topic filter,
  zero-result recovery, inspector-to-article navigation, Back/Forward,
  year changes, all six analysis views, unknown-article recovery, narrow
  layout and 1280px wide layout. No browser console errors observed.

Local preview: `cd app && npm run dev`, then open `/knowledge` on the
printed local URL. The temporary QA server was stopped after validation.
