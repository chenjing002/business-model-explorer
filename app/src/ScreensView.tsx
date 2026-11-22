import { useEffect, useState } from "react";
import { palette } from "./charts/theme";
import { formatAmount } from "./format";
import { ConceptLinks } from "./KnowledgeLink";
import { AppLink, CompanyContext } from "./Navigation";
import { VIEW_PATHS, withCompany, withYear } from "./routes";
import { formatScreenValue, loadScreens, type ScreenList, type ScreenUnit, type Screens } from "./screens";

const PREVIEW = 5;
const PAGE = 30;

/** Home page: loads screens.json once and renders the lists. */
export function ScreensView() {
  const [state, setState] = useState<{ data: Screens | null; error: string | null }>({ data: null, error: null });
  useEffect(() => {
    const controller = new AbortController();
    loadScreens(controller.signal)
      .then((data) => setState({ data, error: null }))
      .catch((error: Error) => { if (!controller.signal.aborted) setState({ data: null, error: error.message }); });
    return () => controller.abort();
  }, []);
  if (state.error) return <main className="status status--error">{state.error}</main>;
  if (!state.data) return <main className="status">正在加载好生意榜单…</main>;
  return <ScreensPage data={state.data} />;
}

export function ScreensPage({ data, initial }: { data: Screens; initial?: string }) {
  const [selected, setSelected] = useState(initial ?? data.lists[0]?.id);
  const list = data.lists.find((item) => item.id === selected) ?? data.lists[0];
  const { universe: u, window, fiscal_year: year } = data;
  // Company links carry their own company; never inherit one from the home URL.
  return <CompanyContext.Provider value="">
    <main className="screens" aria-labelledby="screens-heading">
      <header className="screens__intro">
        <h2 id="screens-heading">好生意榜单</h2>
        <p>
          按 {window[0]}–{year} 年的年度合并财报，从自由现金流、净资产收益率、经营资产回报、现金循环周期和利润含金量五个角度，
          筛选经营记录持续出色的 A 股公司（不含金融类）。榜单只描述历史财务数据，不预测未来，也不构成投资建议。
        </p>
        <p className="screens__universe">
          参与排名 <strong>{u.ranked.toLocaleString("zh-CN")}</strong> 家：已分析的 {u.analyzed_ok.toLocaleString("zh-CN")} 家公司中，
          剔除恒等式校验未通过的 {u.excluded_check_failures.toLocaleString("zh-CN")} 家、
          {window[0]}–{year} 年营业总收入未逐年披露的 {u.excluded_incomplete_years.toLocaleString("zh-CN")} 家，
          以及 {year} 年营业总收入低于 {formatAmount(u.revenue_floor)} 的 {u.excluded_below_revenue_floor.toLocaleString("zh-CN")} 家。
          {" "}<AppLink href={withYear("/knowledge/data-quality", year)}>数据口径</AppLink>
        </p>
      </header>

      <div className="screens__cards" role="group" aria-label="选择榜单">
        {data.lists.map((item) => <button key={item.id} type="button" aria-pressed={item.id === list?.id}
          className="screens__card" onClick={() => setSelected(item.id)}>
          <span className="screens__card-head"><strong>{item.title}</strong><span>{item.count.toLocaleString("zh-CN")} 家</span></span>
          <span className="screens__card-summary">{item.summary}</span>
          <span className="screens__card-top">
            {item.rows.length ? item.rows.slice(0, PREVIEW).map((row) => row.name ?? row.ts_code).join("、") : "暂无公司满足条件"}
          </span>
        </button>)}
      </div>

      {list && <ScreenDetail key={list.id} list={list} window={window} year={year} />}
    </main>
  </CompanyContext.Provider>;
}

function ScreenDetail({ list, window, year }: { list: ScreenList; window: string[]; year: string }) {
  const [shown, setShown] = useState(PAGE);
  const rows = list.rows.slice(0, shown);
  return <section className="screens__detail" aria-labelledby="screen-title">
    <div className="screens__detail-head">
      <h3 id="screen-title">{list.title}</h3>
      <span>{list.count.toLocaleString("zh-CN")} 家 · {list.sort}</span>
    </div>
    <ul className="screens__criteria">{list.criteria.map((text) => <li key={text}>{text}</li>)}</ul>
    <ConceptLinks ids={list.concepts} year={year} />
    {list.rows.length ? <>
      <div className="screens__scroll" role="region" aria-label={`${list.title}榜单`} tabIndex={0}>
        <table className="screens__table">
          <thead><tr>
            <th scope="col">排名</th><th scope="col">公司</th><th scope="col">行业</th>
            {list.columns.map((column) => <th scope="col" key={column.key}
              className={column.unit === "text" ? "screens__text" : undefined}>{column.label}</th>)}
            <th scope="col">{list.trend.label} {window[0]}–{year}</th>
          </tr></thead>
          <tbody>{rows.map((row, i) => <tr key={row.ts_code}>
            <td>{i + 1}</td>
            <th scope="row">
              <AppLink href={withCompany(withYear(VIEW_PATHS.overview, year), row.ts_code)}>{row.name ?? row.ts_code}</AppLink>
              <small>{row.ts_code}</small>
            </th>
            <td>{row.industry ?? "—"}</td>
            {list.columns.map((column) => <td key={column.key} className={column.unit === "text" ? "screens__text" : undefined}>
              {formatScreenValue(row.values[column.key], column.unit)}
            </td>)}
            <td><Sparkline values={row.trend} years={window} unit={list.trend.unit} label={list.trend.label} /></td>
          </tr>)}</tbody>
        </table>
      </div>
      {list.count > shown && <button type="button" className="screens__more" onClick={() => setShown(list.count)}>
        显示全部 {list.count.toLocaleString("zh-CN")} 家
      </button>}
    </> : <p className="screens__empty">本期暂无公司同时满足以上条件。</p>}
  </section>;
}

/** Trend shape only: scaled to the row's own min–max, a dashed line marks
 *  zero when the range crosses it. Exact values are in the tooltip. */
function Sparkline({ values, years, unit, label }: {
  values: (number | null)[]; years: string[]; unit: ScreenUnit; label: string;
}) {
  const W = 104, H = 28, P = 3;
  const nums = values.filter((v): v is number => v != null && Number.isFinite(v));
  const text = values.map((v, i) => `${years[i]} 年 ${formatScreenValue(v, unit)}`).join("；");
  if (nums.length < 2) return <span title={text}>—</span>;
  const min = Math.min(...nums), max = Math.max(...nums);
  const x = (i: number) => P + i * (W - 2 * P) / Math.max(values.length - 1, 1);
  const y = (v: number) => max === min ? H / 2 : H - P - (v - min) / (max - min) * (H - 2 * P);
  let path = "", open = false;
  values.forEach((v, i) => {
    if (v == null || !Number.isFinite(v)) { open = false; return; }
    path += `${open ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    open = true;
  });
  const last = values.length - 1;
  const end = values[last];
  return <svg className="screens__spark" width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img"
    aria-label={`${label}：${text}`}>
    <title>{text}</title>
    {min < 0 && max > 0 && <line x1={P} x2={W - P} y1={y(0)} y2={y(0)} stroke={palette.grid} strokeDasharray="2 2" />}
    <path d={path} fill="none" stroke={palette.operating} strokeWidth={1.6} />
    {end != null && Number.isFinite(end) && <circle cx={x(last)} cy={y(end)} r={2.4} fill={palette.operating} />}
  </svg>;
}
