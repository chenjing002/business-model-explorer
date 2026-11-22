# GitHub Pages publication

Publishes the static website — the built app plus the exported company
bundles — never the DuckDB store, raw data or `.env`.

- App: https://chenjing002.github.io/business-model-explorer/
- Source: `main` of https://github.com/chenjing002/business-model-explorer

## Why two Pages sites

A Pages site is capped at 1 GB; the 5,479 exported bundles are ~1.8 GB. The
published site is split by exchange across two project sites of the same
owner, which share the origin `chenjing002.github.io`, so every fetch stays
same-origin (no CORS):

| Pages site (repo, `gh-pages` branch) | Contents |
|---|---|
| `business-model-explorer` | app, `data/companies.json`, knowledge PDF, SH + BJ bundles |
| `business-model-explorer-data` | SZ bundles |

Published bundles keep every value. Only `calculation_details` is stored
code-major with the fields identical across years kept once per code
(`format: "by_code_v1"`), which halves the gzip size (~0.86 GB in total,
~0.4–0.5 GB per site). `pipeline/pages.py` checks that each bundle expands
back exactly before writing it; the app expands it on load
(`expandCalculationDetails`, `app/src/calculationDetails.ts`). The shared
fixture `tests/fixtures/calculation_details_compact.json` pins the format for
both languages. Local bundles in `app/public/data/` stay in the exported form.

## Commands

```
.venv/bin/python -m pipeline.cli pages             # build + stage + verify into build/pages/
.venv/bin/python -m pipeline.cli pages --publish   # … then force-push both gh-pages branches
```

`--publish` creates a missing repo, force-pushes each staged site as one
orphan commit (old bundles do not pile up in history) and enables Pages on
`gh-pages` the first time. Run it after `analyze-all` so the published
bundles and `companies.json` agree. A site over 950 MB stops the run.

## App under a sub-path

`app/src/site.ts` holds the deployment layout, injected at build time
(`BME_SITE` → Vite `define` `__SITE__`; `base` for asset URLs). App code keeps
site paths (`/map?year=2025`); `siteUrl` adds the prefix for anchors and
`pushState`, `appPath` strips it from `location.pathname`, `bundleUrl` picks
the site by exchange suffix. Locally nothing changes (base `/`). Deep links
work through `404.html`, a copy of `index.html` (Pages answers with status 404
but the app renders the route). Pages serves `.json.gz` as
`application/gzip` without `Content-Encoding`; the loader decompresses by
gzip magic bytes.
