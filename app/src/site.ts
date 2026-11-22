/** Where the site and its data files are served.
 *
 *  Locally everything sits at "/". The GitHub Pages build (`pipeline/pages.py`)
 *  sets `__SITE__` through Vite `define`: the app lives under
 *  /business-model-explorer/ and the company bundles are split by exchange
 *  across Pages sites on the same origin, because one Pages site is capped at
 *  1 GB. App code keeps using site-relative paths ("/map?year=2025"); only
 *  this module knows the prefix.
 */
export interface SiteConfig {
  base: string;
  /** Exchange suffix ("SZ") → directory holding that exchange's bundles. */
  bundleBases?: Record<string, string>;
}

declare const __SITE__: SiteConfig | undefined;

export function makeSite({ base, bundleBases = {} }: SiteConfig) {
  const root = base.endsWith("/") ? base : `${base}/`;
  /** Site path → browser URL. Anything not starting with "/" is left alone. */
  const siteUrl = (path: string) => path.startsWith("/") ? root + path.slice(1) : path;
  /** Browser pathname → site path. Paths outside the base are returned as is
   *  and fall through to the 页面不存在 view. */
  const appPath = (pathname: string) =>
    root !== "/" && `${pathname}/`.startsWith(root) ? `/${pathname.slice(root.length)}` : pathname;
  const bundleUrl = (tsCode: string) =>
    `${bundleBases[tsCode.split(".").pop() ?? ""] ?? siteUrl("/data/")}${encodeURIComponent(tsCode)}.json.gz`;
  return { base: root, siteUrl, appPath, bundleUrl };
}

export const { siteUrl, appPath, bundleUrl } = makeSite(
  typeof __SITE__ === "undefined" ? { base: "/" } : __SITE__);
