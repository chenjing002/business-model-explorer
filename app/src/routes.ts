export const VIEW_PATHS = {
  home: "/", overview: "/overview", map: "/map", tree: "/drivers", capital: "/capital",
  value: "/value", valuation: "/valuation", knowledge: "/knowledge", cases: "/cases",
} as const;

export type View = keyof typeof VIEW_PATHS;

/** Analysis pages of one company; the home page (好生意榜单), knowledge base
 *  and cases are site-level. */
export const COMPANY_VIEWS = ["overview", "map", "tree", "capital", "value", "valuation"] as const satisfies readonly View[];
export type CompanyView = typeof COMPANY_VIEWS[number];
export const isCompanyView = (view: View | undefined): view is CompanyView =>
  (COMPANY_VIEWS as readonly string[]).includes(view ?? "");

/** Pure URL parsing, shared by direct entry, navigation and browser history. */
export function parseRoute(pathname: string, search: string) {
  const path = pathname.replace(/\/+$/, "") || "/";
  const knowledge = path === "/knowledge" || path.startsWith("/knowledge/");
  const cases = path === "/cases" || path.startsWith("/cases/");
  const view = knowledge ? "knowledge" : cases ? "cases" :
    (Object.keys(VIEW_PATHS) as View[]).find((key) => VIEW_PATHS[key] === path);
  const params = new URLSearchParams(search);
  const rawYear = params.get("year") ?? "";
  const year = /^\d{4}$/.test(rawYear) ? rawYear : "";
  const rawCompany = params.get("company")?.toUpperCase() ?? "";
  const company = /^[A-Z0-9]{1,12}\.[A-Z0-9]{1,8}$/.test(rawCompany) ? rawCompany : "";
  // Slugs are deliberately ASCII, so malformed percent-encoding cannot throw.
  const concept = knowledge ? path.slice("/knowledge/".length) : "";
  return { view, concept, year, ...(company ? { company } : {}),
    ...(cases ? { caseId: path.slice("/cases/".length) } : {}) };
}

export function withYear(path: string, year: string) {
  return year ? `${path}?year=${encodeURIComponent(year)}` : path;
}

export function withCompany(href: string, company: string) {
  if (!company || /^\/cases(?:\/|[?#]|$)/.test(href)) return href;
  const [location, fragment] = href.split("#", 2);
  return `${location}${location.includes("?") ? "&" : "?"}company=${encodeURIComponent(company)}${fragment == null ? "" : `#${fragment}`}`;
}
