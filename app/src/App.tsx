import { useEffect, useMemo, useState } from "react";
import { CapitalView } from "./CapitalView";
import { annualYears, loadBundle } from "./data";
import { DriverTree } from "./DriverTree";
import { EconMap } from "./EconMap";
import { ValuationView } from "./ValuationView";
import { ValueView } from "./ValueView";
import type { Bundle } from "./types";
import { AppLink, CompanyContext, NavigationContext } from "./Navigation";
import { appPath, siteUrl } from "./site";
import { COMPANY_VIEWS, isCompanyView, parseRoute, VIEW_PATHS, withCompany, withYear } from "./routes";
import { VIEW_LABELS, CONCEPT_BY_ID } from "./knowledge";
import { Overview } from "./Overview";
import { KnowledgeView } from "./KnowledgeView";
import { ReferenceCasesView } from "./ReferenceCasesView";
import { ScreensView } from "./ScreensView";
import { CalculationProvider } from "./CalculationPopover";
import { CASES } from "./referenceCases";
import { CompanyPicker } from "./CompanyPicker";
import { adjacentCompany, availability, CHECK_FAMILY_LABELS, companyOrder, loadCompanyIndex, type CompanyIndex } from "./companies";

const DEFAULT_COMPANY = "600519.SH";
/** Site path + query of the current page, without the deployment base. */
const currentLocation = () => appPath(window.location.pathname) + window.location.search;
/** Focus inside these keeps ←/→ for itself instead of switching company. */
const ARROW_KEY_OWNERS = "input, textarea, select, [contenteditable]:not([contenteditable='false']), " +
  "[role='listbox'], [role='slider'], [role='radiogroup'], [role='tablist'], [role='tree'], [role='grid'], [role='menu']";

export default function App() {
  const [data, setData] = useState<{ company: string; bundle: Bundle | null; error: string | null } | null>(null);
  const [location, setLocation] = useState(currentLocation);
  const route = useMemo(() => {
    const url = new URL(location, window.location.origin);
    return parseRoute(url.pathname, url.search);
  }, [location]);
  const view = route.view;
  const companyView = isCompanyView(view);
  const companyParam = view === "cases" ? "" : route.company ?? "";
  const company = companyParam || DEFAULT_COMPANY;
  const bundle = data?.company === company ? data.bundle : null;
  const error = data?.company === company ? data.error : null;
  const navigate = (href: string) => {
    const previousPath = window.location.pathname;
    window.history.pushState(null, "", siteUrl(href));
    setLocation(currentLocation());
    if (window.location.pathname !== previousPath) window.scrollTo(0, 0);
  };
  useEffect(() => {
    const onPopState = () => setLocation(currentLocation());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  // The home page lists every company and needs no single-company bundle.
  const needBundle = view !== "home";
  useEffect(() => {
    if (!needBundle) return;
    const controller = new AbortController();
    loadBundle(company, controller.signal)
      .then((bundle) => {
        if (!controller.signal.aborted) setData({ company, bundle, error: null });
      })
      .catch((error: Error) => {
        if (!controller.signal.aborted) setData({ company, bundle: null, error: error.message });
      });
    return () => controller.abort();
  }, [company, needBundle]);

  const [companies, setCompanies] = useState<{ index: CompanyIndex | null; error: string | null }>({ index: null, error: null });
  const needCompanies = companyView && !companies.index && !companies.error;
  useEffect(() => {
    if (!needCompanies) return;
    const controller = new AbortController();
    loadCompanyIndex(controller.signal)
      .then((index) => setCompanies({ index, error: null }))
      .catch((error: Error) => { if (!controller.signal.aborted) setCompanies({ index: null, error: error.message }); });
    return () => controller.abort();
  }, [needCompanies]);

  // ←/→ step to the previous/next analysed company, keeping the tab and year.
  const companyIndex = companies.index;
  const order = useMemo(() => companyIndex ? companyOrder(companyIndex) : [], [companyIndex]);
  useEffect(() => {
    if (!companyView || !companyIndex) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (event.target instanceof Element && event.target.closest(ARROW_KEY_OWNERS)) return;
      const next = adjacentCompany(companyIndex, order, company, event.key === "ArrowRight" ? 1 : -1);
      if (!next) return;
      event.preventDefault();
      navigate(withCompany(withYear(appPath(window.location.pathname), route.year), next));
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [companyView, companyIndex, order, company, route.year]);

  const years = useMemo(() => bundle ? annualYears(bundle) : [], [bundle]);
  const year = years.includes(route.year) ? route.year : years[years.length - 1] ?? route.year;
  const entry = companies.index?.byCode.get(company);
  // Every listed company is in the picker; only exported bundles can be analysed.
  const unavailable = companies.index ? availability(companies.index, company) : null;
  const notAnalyzed = !!unavailable;
  const checkFailures = companies.index?.checkFailures.get(company) ?? [];
  // A missing bundle is explained by the index; wait for it rather than flash a 404.
  const indexPending = companyView && !companies.index && !companies.error;
  const companyName = bundle?.overview?.company_name || entry?.name || null;

  useEffect(() => {
    const title = view === "knowledge" ? CONCEPT_BY_ID.get(route.concept)?.title ?? "财务知识库" :
      view === "cases" ? CASES.find((c) => c.id === (route.caseId || CASES[0].id))?.title ?? "参考案例" :
      view ? VIEW_LABELS[view] : "页面不存在";
    document.title = `${title}${companyView && companyName ? ` · ${companyName}` : ""} · 商业模式探索器`;
  }, [view, route.concept, route.caseId, companyView, companyName]);

  return (
    <NavigationContext.Provider value={navigate}>
    <CompanyContext.Provider value={companyParam}>
    <CalculationProvider index={bundle?.calculation_details}>
    <div className="layout">
      <header className="sitebar">
        <AppLink className="sitebar__brand" href={VIEW_PATHS.home}>
          <h1>商业模式探索器</h1>
          <span>Penman 框架 · A 股年度财务分析</span>
        </AppLink>
        <nav className="sitenav" aria-label="网站导航">
          <AppLink className={view === "home" ? "sitenav__link sitenav__link--active" : "sitenav__link"}
            href={VIEW_PATHS.home} aria-current={view === "home" ? "page" : undefined}>{VIEW_LABELS.home}</AppLink>
          <AppLink className={companyView ? "sitenav__link sitenav__link--active" : "sitenav__link"}
            href={withYear(VIEW_PATHS.overview, year)} aria-current={companyView ? "page" : undefined}>公司分析</AppLink>
          {(["knowledge", "cases"] as const).map((key) => <AppLink key={key}
            className={view === key ? "sitenav__link sitenav__link--active" : "sitenav__link"}
            href={withYear(VIEW_PATHS[key], year)} aria-current={view === key ? "page" : undefined}>
            {VIEW_LABELS[key]}
          </AppLink>)}
        </nav>
      </header>

      {companyView && <section className="companybar" aria-label="公司分析">
        <div className="companybar__identity">
          <CompanyPicker index={companies.index} error={companies.error} current={company} currentName={companyName}
            onSelect={(code) => navigate(withCompany(withYear(appPath(window.location.pathname), route.year), code))} />
          <span className="companybar__sub">
            {bundle ? `年度合并财报 · 人民币（金额：亿元） · 数据导出 ${bundle.exported_at.slice(0, 10)}` :
              notAnalyzed ? `暂无分析（${unavailable.tag}）` : error && !indexPending ? "数据加载失败" : "正在加载…"}
            {bundle && checkFailures.length > 0 && <> · <AppLink className="companybar__flag"
              href={withYear("/knowledge/data-quality", year)}
              title="恒等式校验未通过的项目如实列示，不强制轧平；详见各页面的校验差额">
              恒等式校验未通过：{checkFailures.map((family) => CHECK_FAMILY_LABELS[family] ?? family).join("、")}
            </AppLink></>}
          </span>
        </div>
        <div className="companybar__controls">
          <nav className="tabs" aria-label="公司分析页面">
            {COMPANY_VIEWS.map((key) => <AppLink key={key}
              className={view === key ? "tab tab--active" : "tab"}
              href={withYear(VIEW_PATHS[key], year)} aria-current={view === key ? "page" : undefined}>
              {VIEW_LABELS[key]}
            </AppLink>)}
          </nav>
          {years.length > 0 && <label className="yearpick">
            年度{" "}
            <select value={year} onChange={(e) => navigate(withCompany(withYear(appPath(window.location.pathname), e.target.value), companyParam))}>
              {years.map((y) => (
                <option key={y} value={y}>{y}年</option>
              ))}
            </select>
          </label>}
        </div>
      </section>}

      {view === "home" && <ScreensView />}
      {view === "knowledge" && <KnowledgeView concept={route.concept} year={year} />}
      {view === "cases" && <ReferenceCasesView caseId={route.caseId ?? ""} year={year} bundle={bundle} bundleError={error} />}
      {!view && <main className="status"><h2>页面不存在</h2><AppLink href={VIEW_PATHS.home}>返回首页</AppLink></main>}
      {companyView && (!bundle || error) && (notAnalyzed ? <main className="status">
        <h2>{companyName ?? company}（{company}）暂无分析数据</h2>
        <p>{unavailable.step ? `分析流程在“${unavailable.step}”步骤失败。` : ""}{unavailable.text}</p>
        <p>目前已分析 {companies.index?.analyzed.size.toLocaleString("zh-CN") ?? 0} 家公司；切换公司列表中未分析的公司会标注原因。</p>
      </main> : <main className={`status ${error ? "status--error" : ""}`}>
        {error && !indexPending ? `数据加载失败：${error}` : "正在加载…"}
        <p><AppLink href={withYear("/knowledge", year)}>浏览财务知识库</AppLink></p>
      </main>)}
      {bundle && <>
      {view === "map" && <EconMap bundle={bundle} year={year} />}
      {view === "tree" && <DriverTree bundle={bundle} year={year} />}
      {view === "capital" && <CapitalView bundle={bundle} year={year} />}
      {view === "value" && <ValueView bundle={bundle} year={year} />}
      {view === "valuation" && <ValuationView bundle={bundle} year={year} />}

      {view === "overview" && <Overview bundle={bundle} year={year} />}
      </>}

      <footer className="foot">
        金额原值为人民币元，图表及科目明细按亿元展示；股价和每股估值单位为元/股。
        空值表示未披露或无法计算，请结合各指标口径与提示阅读。
        {bundle && view !== "cases" && <> 分析口径：{Object.values(bundle.conventions).join(" · ")}</>}
        {" "}<AppLink href={withYear("/knowledge/data-quality", year)}>数据口径</AppLink>
        {" · "}<AppLink href={withYear("/knowledge/units", year)}>金额单位说明</AppLink>
      </footer>
    </div>
    </CalculationProvider>
    </CompanyContext.Provider>
    </NavigationContext.Provider>
  );
}
