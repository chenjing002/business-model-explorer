import { readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const require = createRequire(import.meta.url);
const sourceRoot = fileURLToPath(new URL("../src/", import.meta.url));
const cache = new Map();

/** Run real TS/TSX with the installed compiler and React server renderer.
 *  Small injected hooks allow inspection of chart options without a browser. */
export function loadTs(file, imports = {}) {
  const absolute = resolve(sourceRoot, file);
  if (!Object.keys(imports).length && cache.has(absolute)) return cache.get(absolute);
  const source = readFileSync(absolute, "utf8");
  const js = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
    esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText;
  const module = { exports: {} };
  new Function("require", "module", "exports", js)((specifier) => {
    if (Object.hasOwn(imports, specifier)) return imports[specifier];
    if (!specifier.startsWith(".")) return require(specifier);
    const path = resolve(dirname(absolute), specifier);
    if (path.endsWith(".json")) return require(path);
    const found = [`${path}.ts`, `${path}.tsx`, path].find(existsSync);
    if (!found) throw new Error(`Cannot resolve ${specifier} from ${file}`);
    return loadTs(found);
  }, module, module.exports);
  if (!Object.keys(imports).length) cache.set(absolute, module.exports);
  return module.exports;
}
