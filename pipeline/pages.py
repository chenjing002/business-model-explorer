"""Publish the static website to GitHub Pages.

One Pages site is capped at 1 GB and the company bundles alone are ~1.8 GB,
so the published site is split across Pages sites of the same owner. They
share the origin <owner>.github.io, so the app fetches every bundle
same-origin:

- `business-model-explorer`: the app, company index, reference cases, the
  knowledge PDF and the SH / BJ bundles;
- `business-model-explorer-data`: the SZ bundles.

Published bundles keep every value. Only `calculation_details` is regrouped
code-major with the fields identical across years stored once per code
(format `by_code_v1`, expanded by `app/src/calculationDetails.ts`); this
roughly halves the gzip size. Each bundle is checked to expand back to the
exported index exactly before it is written.

Each site is force-pushed as a single commit to its `gh-pages` branch, so the
repositories do not accumulate old bundles. Source code goes to `main` by
ordinary commits; generated data never does.
"""
from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .config import PROJECT_ROOT
from .export import BUNDLE_SUFFIX

OWNER = "chenjing002"
APP_SITE = "business-model-explorer"
# Exchange suffix → Pages site holding those bundles; others stay with the app.
DATA_SITES = {"SZ": "business-model-explorer-data"}
COMPACT_FORMAT = "by_code_v1"
# GitHub Pages rejects sites over 1 GB; keep room for growth.
SITE_LIMIT_BYTES = 950_000_000

APP_DIR = PROJECT_ROOT / "app"
DEFAULT_OUT = PROJECT_ROOT / "build" / "pages"


def site_config() -> dict:
    """Layout handed to the Vite build (`BME_SITE`, read by app/src/site.ts)."""
    return {"base": f"/{APP_SITE}/",
            "bundleBases": {ex: f"/{site}/data/" for ex, site in DATA_SITES.items()}}


def site_for(ts_code: str) -> str:
    return DATA_SITES.get(ts_code.rsplit(".", 1)[-1], APP_SITE)


def _same(a, b) -> bool:
    # Type-exact, so 0 and 0.0 or 1 and True are never merged.
    return type(a) is type(b) and a == b


def compact_calculation_details(index: dict) -> dict:
    """Year-major index → code-major, shared fields stored once per code."""
    by_code: dict[str, dict[str, dict]] = {}
    for year, codes in index.items():
        for code, detail in codes.items():
            by_code.setdefault(code, {})[year] = detail
    shared, values = {}, {}
    for code, years in by_code.items():
        first, *rest = years.values()
        common = {key: value for key, value in first.items()
                  if all(key in other and _same(other[key], value) for other in rest)}
        shared[code] = common
        values[code] = {year: {k: v for k, v in detail.items() if k not in common}
                        for year, detail in years.items()}
    return {"format": COMPACT_FORMAT, "years": list(index), "shared": shared, "values": values}


def expand_calculation_details(compact: dict) -> dict:
    """Python mirror of app/src/calculationDetails.ts `expandCalculationDetails`."""
    if compact.get("format") != COMPACT_FORMAT:
        return compact
    index: dict[str, dict] = {year: {} for year in compact["years"]}
    for code, by_year in compact["values"].items():
        for year, own in by_year.items():
            index[year][code] = {**compact["shared"][code], **own}
    return index


def _canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def compact_bundle(source: Path, target: Path) -> tuple[int, int]:
    """Write the published form of one bundle; returns (source, target) bytes."""
    bundle = json.loads(gzip.decompress(source.read_bytes()))
    details = bundle.get("calculation_details")
    if details is not None:
        compact = compact_calculation_details(details)
        if _canonical(expand_calculation_details(compact)) != _canonical(details):
            raise ValueError(f"{source.name}: compact calculation_details does not expand back exactly")
        bundle["calculation_details"] = compact
    text = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    target.write_bytes(gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0))
    return source.stat().st_size, target.stat().st_size


def _compact_job(job: tuple[str, str]) -> tuple[int, int]:
    return compact_bundle(Path(job[0]), Path(job[1]))


def _dir_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and ".git" not in f.parts)


def _reset(path: Path, out_root: Path) -> None:
    if out_root.resolve() not in path.resolve().parents:
        raise ValueError(f"refusing to clear {path} outside {out_root}")
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)


def stage(out_root: Path = DEFAULT_OUT, build: bool = True, workers: int = 6) -> dict[str, dict]:
    """Build the app and lay out every Pages site under out_root/<site>/."""
    public = APP_DIR / "public"
    sites = {APP_SITE: out_root / APP_SITE, **{s: out_root / s for s in DATA_SITES.values()}}
    out_root.mkdir(parents=True, exist_ok=True)
    for path in sites.values():
        _reset(path, out_root)
    if build:
        env = {**os.environ, "BME_SITE": json.dumps(site_config())}
        subprocess.run(["npm", "run", "build", "--", "--outDir", str(sites[APP_SITE]), "--emptyOutDir"],
                       cwd=APP_DIR, env=env, check=True)
    app = sites[APP_SITE]
    index_html = app / "index.html"
    if not index_html.exists():
        raise FileNotFoundError(f"{index_html} missing; run without --skip-build")
    # Deep links (/business-model-explorer/knowledge/ccc) reach the app via Pages' 404 page.
    shutil.copyfile(index_html, app / "404.html")

    bundles = sorted((public / "data").glob(f"*{BUNDLE_SUFFIX}"))
    bundle_set = set(bundles)
    for path in public.rglob("*"):
        if path.is_file() and path not in bundle_set and path.name != ".DS_Store":
            target = app / path.relative_to(public)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    jobs = []
    for path in bundles:
        target = sites[site_for(path.name.removesuffix(BUNDLE_SUFFIX))] / "data" / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        jobs.append((str(path), str(target)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        sizes = list(pool.map(_compact_job, jobs, chunksize=32))

    for name, path in sites.items():
        (path / ".nojekyll").touch()
        if name != APP_SITE:
            (path / "index.html").write_text(
                f'<!doctype html><meta charset="utf-8"><title>商业模式探索器 · 数据</title>'
                f'<p>本站仅存放公司数据包，请访问 <a href="/{APP_SITE}/">商业模式探索器</a>。</p>\n',
                encoding="utf-8")
    report = {name: {"path": str(path), "bundles": len(list((path / "data").glob(f"*{BUNDLE_SUFFIX}"))),
                     "bytes": _dir_bytes(path)} for name, path in sites.items()}
    report["_bundles"] = {"count": len(sizes), "source_bytes": sum(s for s, _ in sizes),
                          "published_bytes": sum(t for _, t in sizes)}
    over = [name for name, r in report.items() if not name.startswith("_") and r["bytes"] > SITE_LIMIT_BYTES]
    if over:
        raise RuntimeError(f"Pages site over {SITE_LIMIT_BYTES:,} bytes: {', '.join(over)}")
    return report


def _gh(*args: str, input: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], input=input, text=True, capture_output=True, check=check)


def publish(out_root: Path = DEFAULT_OUT) -> list[str]:
    """Force-push each staged site to its gh-pages branch and enable Pages."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    urls = []
    for name in [APP_SITE, *DATA_SITES.values()]:
        path, repo = out_root / name, f"{OWNER}/{name}"
        if not (path / "index.html").exists():
            raise FileNotFoundError(f"{path} is not staged")
        if _gh("repo", "view", repo, "--json", "name", check=False).returncode != 0:
            _gh("repo", "create", repo, "--public",
                "--description", "商业模式探索器 · GitHub Pages 公司数据包（自动发布）")
        shutil.rmtree(path / ".git", ignore_errors=True)
        for command in (["init", "-q", "-b", "gh-pages"], ["add", "-A"],
                        ["commit", "-q", "-m", f"Publish site {stamp}"],
                        ["push", "-f", f"git@github.com:{repo}.git", "gh-pages"]):
            subprocess.run(["git", *command], cwd=path, check=True)
        if _gh("api", f"repos/{repo}/pages", check=False).returncode != 0:
            _gh("api", "-X", "POST", f"repos/{repo}/pages", "--input", "-",
                input=json.dumps({"source": {"branch": "gh-pages", "path": "/"}}))
        urls.append(f"https://{OWNER}.github.io/{name}/")
    return urls
