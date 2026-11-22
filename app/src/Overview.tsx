import { useContext, useState, type ReactNode } from "react";
import { AuditValue, CalculationContext } from "./CalculationPopover";
import { CapitalChart } from "./charts/CapitalChart";
import { HistoryChart } from "./charts/HistoryChart";
import { ReturnsChart } from "./charts/ReturnsChart";
import { WaterfallChart } from "./charts/WaterfallChart";
import { WcDaysChart } from "./charts/WcDaysChart";
import { palette } from "./charts/theme";
import { annualYears } from "./data";
import { formatAmount, formatAmountNumber, formatNumber, formatPrice } from "./format";
import { ConceptLinks } from "./KnowledgeLink";
import { flagText, textZh } from "./locale";
import { fmtMetric } from "./metrics";
import { AppLink } from "./Navigation";
import { VIEW_PATHS, withYear } from "./routes";
import type { Bundle, CapitalSummaryRow, CashSummaryRow, ReformulatedIsRow, WorkingCapitalRow } from "./types";

type Format = "money" | "yi" | "price" | "pct" | "pct2" | "pp" | "x" | "days";
type ValueProps = {
  value: number | null | undefined;
  date?: string;
  code?: string;
  fmt?: Format;
  signed?: boolean;
  missing?: string;
};

function Value({ value, date, code, fmt = "money", signed, missing = "未披露" }: ValueProps) {
  const index = useContext(CalculationContext);
  const detail = date && code ? index?.[date]?.[code] : undefined;
  if (value == null || !Number.isFinite(value)) {
    return <span className="overview__missing">{detail?.reason ? flagText(detail.reason) : missing}</span>;
  }
  const formatted = fmt === "money" ? formatAmount(value)
    : fmt === "yi" ? formatAmountNumber(value)
    : fmt === "price" ? formatPrice(value)
    : fmt === "pct2" ? `${formatNumber(value * 100, 2)}%` : fmtMetric(value, fmt);
  const content = signed && value > 0 ? `+${formatted}` : formatted;
  return date && code && detail ? <AuditValue year={date} code={code}>{content}</AuditValue> : <span>{content}</span>;
}

function Metric({ label, children, context }: { label: string; children: ReactNode; context?: ReactNode }) {
  return <div className="overview__metric">
    <dt>{label}</dt>
    <dd>{children}</dd>
    {context && <dd className="overview__metric-context">{context}</dd>}
  </div>;
}

function Source({ source, page, children }: { source: string; page?: number; children: ReactNode }) {
  return <a className="overview__source" href={source} target="_blank" rel="noreferrer">
    {children}{page ? ` · 第 ${page} 页` : ""}
  </a>;
}

function Table({ label, heads, children }: { label: string; heads: string[]; children: ReactNode }) {
  return <div className="overview__scroll" role="region" aria-label={label} tabIndex={0}>
    <table className="overview__table" aria-label={label}>
      <thead><tr>{heads.map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead>
      <tbody>{children}</tbody>
    </table>
  </div>;
}

function Details({ label, children, charts, expanded }: {
  label: string; children: ReactNode; charts?: boolean; expanded?: boolean;
}) {
  const [open, setOpen] = useState(false);
  return <details className="overview__details" open={expanded} onToggle={charts ? (event) => setOpen(event.currentTarget.open) : undefined}>
    <summary>{label}</summary>
    {(!charts || open) && <div className="overview__details-content">{children}</div>}
  </details>;
}

const DUPONT = [
  { key: "roe", label: "合并净资产收益率（ROE）", unit: "%", fmt: "pct2", color: palette.equity },
  { key: "net_margin", label: "销售净利率", unit: "%", fmt: "pct2", color: palette.operating },
  { key: "asset_turnover", label: "总资产周转率", unit: "倍", fmt: "x", color: palette.financing },
  { key: "equity_multiplier", label: "权益乘数（财务杠杆）", unit: "倍", fmt: "x", color: palette.warn },
] as const;

type FlowYear = {
  year: string; date: string; netIncome?: number | null; income?: ReformulatedIsRow;
  cash?: CashSummaryRow; capital?: CapitalSummaryRow;
};
const FLOW_ROWS = [
  { label: "合并净利润", hint: "Net income · 含少数股东损益",
    code: "raw:net_income_total", color: palette.equity, missing: "未披露", pick: (row: FlowYear) => row.netIncome },
  { label: "归母净利润", hint: "Net income attributable to parent · 归属于母公司所有者的净利润",
    code: "raw:net_income_parent", color: palette.equity, missing: "未披露", pick: (row: FlowYear) => row.income?.ni_parent },
  { label: "折旧摊销（D&A）", hint: "Depreciation & amortization · 补充资料已披露折旧摊销项目之和",
    code: "da_total", color: palette.accent, missing: "补充资料未披露", pick: (row: FlowYear) => row.capital?.da_total },
  { label: "经营活动现金流量净额", hint: "Operating cash flow",
    code: "raw:cfo", color: palette.operating, missing: "未披露", pick: (row: FlowYear) => row.cash?.cfo },
  { label: "减：现金资本开支", hint: "Capital expenditures · 购建固定资产、无形资产和其他长期资产支付的现金",
    code: "raw:capex_paid", color: palette.warn, missing: "未披露", pick: (row: FlowYear) => row.cash?.capex_paid },
  { label: "自由现金流（FCF）", hint: "Free cash flow ＝ 经营活动现金流量净额 − 现金资本开支", total: true,
    code: "fcf_simple", color: palette.financing, missing: "缺少经营现金流或资本开支", pick: (row: FlowYear) => row.cash?.fcf_simple },
];

/** Years run across. Each row's bars scale to that row's largest magnitude,
 *  so they show the year-to-year trend; cross-row size is read from the
 *  numbers and the capex ÷ D&A row. Bars are display geometry only. */
function CashInvestmentTable({ rows, year }: { rows: FlowYear[]; year: string }) {
  const rowScale = (pick: (row: FlowYear) => number | null | undefined) => Math.max(0, ...rows.map(pick)
    .filter((value): value is number => value != null && Number.isFinite(value)).map(Math.abs));
  const current = (date: string) => date === `${year}1231` ? "overview__flow-current" : undefined;
  return <div className="overview__history-card overview__flow">
    <div className="overview__history-heading">
      <h4>净利润、折旧摊销、经营现金流与资本开支</h4>
      <span>单位：亿元（末行为倍数）· 条形按本行最大值缩放，显示逐年变化</span>
    </div>
    <div className="overview__scroll" role="region" aria-label="历年净利润、折旧摊销、经营现金流与资本开支" tabIndex={0}>
      <table className="overview__table overview__flow-table" aria-label="历年净利润、折旧摊销、经营现金流与资本开支">
        <thead><tr>
          <th scope="col">项目</th>
          {rows.map(({ year, date }) => <th scope="col" key={date} className={current(date)}>{year}</th>)}
        </tr></thead>
        <tbody>
          {FLOW_ROWS.map(({ label, hint, code, color, missing, pick, total }) => {
            const scale = rowScale(pick);
            return <tr key={code} className={total ? "overview__flow-total" : undefined}>
            <th scope="row">{label}<small>{hint}</small></th>
            {rows.map((row) => {
              const value = pick(row);
              const width = value != null && Number.isFinite(value) && scale > 0 ? Math.abs(value) / scale * 100 : 0;
              return <td key={row.date} className={[current(row.date), value != null && value < 0 ? "overview__decrease" : ""].filter(Boolean).join(" ") || undefined}>
                <Value value={value} date={row.date} code={code} fmt="yi" missing={missing} />
                {width > 0 && <i className="overview__flow-bar" aria-hidden="true"
                  style={{ width: `${width}%`, background: value != null && value < 0 ? palette.negative : color }} />}
              </td>;
            })}
          </tr>;
          })}
          <tr className="overview__flow-ratio">
            <th scope="row">资本开支／折旧摊销<small>Capex ÷ D&A，倍</small></th>
            {rows.map((row) => <td key={row.date} className={current(row.date)}>
              <Value value={row.capital?.capex_to_da} date={row.date} code="capex_to_da" fmt="x" missing="缺少折旧摊销或资本开支" />
            </td>)}
          </tr>
        </tbody>
      </table>
    </div>
  </div>;
}

const CCC_DAYS = [
  { key: "dio", label: "存货周转天数（DIO）" },
  { key: "dso", label: "应收款项周转天数（DSO）" },
  { key: "dpo", label: "应付款项周转天数（DPO）" },
  { key: "ccc", label: "现金循环周期（CCC）" },
  { key: "advance_days", label: "客户预收款天数" },
  { key: "ccc_net_advances", label: "扣除客户预收款后" },
] as const;

/** CCC < 0 is the cash-generative case: customers pay before suppliers are
 *  paid. The sign test only picks the tag; both day counts come from Python. */
function CccCard({ rows, year, hasNet }: {
  rows: { date: string; wc?: WorkingCapitalRow }[]; year: string; hasNet: boolean;
}) {
  const date = `${year}1231`;
  const latest = rows.find((row) => row.date === date)?.wc;
  const ccc = latest?.ccc;
  return <div className="overview__history-card overview__history-per-share overview__history-ccc">
    <h4>现金循环周期（CCC） <small>{year} 年 · 存货天数 ＋ 应收天数 − 应付天数</small></h4>
    <div className="overview__history-value overview__ccc-values">
      <Value date={date} code="ccc" value={ccc} fmt="days" missing={latest?.wc_flags || "缺少周转天数所需披露"} />
      {ccc != null && Number.isFinite(ccc) && (ccc < 0
        ? <span className="overview__ccc-tag overview__ccc-tag--cash">现金生成型：先收客户款，后付供应商款</span>
        : <span className="overview__ccc-tag overview__ccc-tag--uses">经营周期需垫付营运资金</span>)}
      {hasNet && <span className="overview__ccc-net">扣除客户预收款后 <Value date={date} code="ccc_net_advances"
        value={latest?.ccc_net_advances} fmt="days" missing={latest?.wc_flags || "缺少客户预收款或周转天数披露"} /></span>}
    </div>
    <HistoryChart label="现金循环周期" years={rows.map(({ date }) => date.slice(0, 4))} unit="天" series={[
      { label: "现金循环周期（CCC）", color: palette.operating, values: rows.map((row) => row.wc?.ccc ?? null) },
      ...(hasNet ? [{ label: "扣除客户预收款后", color: palette.warn,
        values: rows.map((row) => row.wc?.ccc_net_advances ?? null) }] : []),
    ]} />
  </div>;
}

function OverviewHistory({ bundle, year }: { bundle: Bundle; year: string }) {
  const end = Number(year);
  const first = Math.max(end - 9, Number(annualYears(bundle)[0] ?? year));
  const years = Array.from({ length: end - first + 1 }, (_, offset) => String(first + offset));
  const reports = new Map(bundle.overview?.years.map((row) => [row.end_date, row.history]));
  const income = new Map(bundle.reformulated_is.filter((row) => row.period_kind === "cumulative")
    .map((row) => [row.end_date, row]));
  const cash = new Map(bundle.cash_summary.map((row) => [row.end_date, row]));
  const capital = new Map(bundle.capital_summary.map((row) => [row.end_date, row]));
  const workingCapital = new Map(bundle.working_capital.map((row) => [row.end_date, row]));
  const rows = years.map((year) => {
    const date = `${year}1231`;
    return { year, date, income: income.get(date), cash: cash.get(date), capital: capital.get(date),
      wc: workingCapital.get(date), history: reports.get(date),
      netIncome: income.get(date)?.ni_total ?? cash.get(date)?.ni_total };
  });
  const latest = rows[rows.length - 1]?.history;
  const hasHistory = rows.some((row) => row.history != null);
  // Bundles exported before the netted CCC existed lack the key entirely.
  const hasNetCcc = bundle.working_capital.some((row) => row.ccc_net_advances !== undefined);
  const cccDays = CCC_DAYS.filter(({ key }) => hasNetCcc || key !== "ccc_net_advances");

  return <section id="historical-performance" className="overview__section overview__history" aria-labelledby="history-heading">
    <div className="overview__history-heading">
      <h3 id="history-heading">历年盈利、现金流与回报</h3>
      <span>{first === end ? year : `${first}–${year}`} 年 · 年度合并财报</span>
    </div>
    <CashInvestmentTable rows={rows} year={year} />
    <div className="overview__history-card overview__history-per-share">
      <h4>每股自由现金流 <small>{year} 年</small></h4>
      <div className="overview__history-value"><Value date={`${year}1231`} code="overview:fcf_per_share"
        value={latest?.fcf_per_share} fmt="price" missing="缺少 FCF 或可用的年末总股本" /></div>
      <HistoryChart label="每股自由现金流" years={years} unit="元/股" series={[
        { label: "每股自由现金流", color: palette.financing, values: rows.map((row) => row.history?.fcf_per_share ?? null) },
      ]} />
    </div>
    <p className="overview__note">
      自由现金流（FCF）＝经营活动现金流量净额 − 现金资本开支。现金资本开支取“购建固定资产、无形资产和其他长期资产支付的现金”，
      已包含资本化的软件及开发支出等无形资产，与亚马逊“购置固定资产（含资本化的内部使用软件和网站开发）”的扣减范围相近；
      未扣减资产处置回款和租赁负债本金。按企业会计准则，偿付利息列筹资活动，经营现金流不含利息支出，跨准则比较时须注意。
      折旧摊销取现金流量表补充资料中已披露的固定资产折旧、使用权资产折旧、无形资产摊销及长期待摊费用摊销之和。
      每股 FCF 以年末总股本计算。参考 <Source
        source="https://www.sec.gov/Archives/edgar/data/1018724/000119312505070440/dex991.htm">Bezos 的亚马逊 2004 年度股东信</Source>。
    </p>
    <ConceptLinks ids={["fcf", "capex", "cfo"]} year={year} />
    <CccCard rows={rows} year={year} hasNet={hasNetCcc} />
    <p className="overview__note">
      现金循环周期（CCC）＝存货周转天数 ＋ 应收款项周转天数 − 应付款项周转天数，即亚马逊股东信中的 operating cycle。
      为负值表示向客户收款早于向供应商付款，经营周期本身产生现金。各项天数取期初与期末平均余额、按 365 天计算：
      存货天数以营业成本为分母（非营业收入），应收天数以营业收入为分母，应付天数以估算采购额（营业成本 ＋ 存货增加额）为分母。
      客户预收款（预收款项 ＋ 合同负债）不计入 CCC；另列扣除客户预收款天数后的口径，用以区分供应商信用与客户预付。
      {!hasNetCcc && " 重新导出数据包后可查看扣除客户预收款后的现金循环周期。"}
    </p>
    <ConceptLinks ids={["ccc", "dio", "dso", "dpo", "advances"]} year={year} />
    <div className="overview__history-heading overview__history-heading--dupont">
      <h4>杜邦三因素拆分</h4>
      <span>ROE ＝ 销售净利率 × 总资产周转率 × 权益乘数</span>
    </div>
    <div className="overview__history-dupont">
      {DUPONT.map(({ key, label, unit, fmt, color }) => <div className="overview__history-card" key={key}>
        <h5>{label}</h5>
        <div className="overview__history-value"><Value date={`${year}1231`} code={`overview:${key}`}
          value={latest?.[key]} fmt={fmt} missing="缺少所需披露或有效分母" /></div>
        <HistoryChart label={label} years={years} unit={unit} series={[
          { label, color, values: rows.map((row) => row.history?.[key] ?? null) },
        ]} />
      </div>)}
    </div>
    <p className="overview__note">
      使用合并净利润和营业总收入。总资产及股东权益（含少数股东）取期初与期末平均值。各图纵轴独立。
    </p>
    {!hasHistory && <p className="overview__note">重新导出数据包后可查看每股自由现金流和杜邦分析。</p>}
    <Details label="查看逐年明细与计算口径">
      <Table label="历年盈利与自由现金流" heads={["年度", "合并净利润", "经营活动现金流量净额", "现金资本开支", "自由现金流（FCF）", "每股自由现金流"]}>
        {rows.map(({ year, date, cash, history, netIncome }) => <tr key={date}>
          <th scope="row">{year} 年</th>
          <td><Value value={netIncome} date={date} code="raw:net_income_total" /></td>
          <td><Value value={cash?.cfo} date={date} code="raw:cfo" /></td>
          <td><Value value={cash?.capex_paid} date={date} code="raw:capex_paid" /></td>
          <td><Value value={cash?.fcf_simple} date={date} code="fcf_simple" missing="缺少经营现金流或资本开支" /></td>
          <td><Value value={history?.fcf_per_share} date={date} code="overview:fcf_per_share" fmt="price"
            missing="缺少 FCF 或可用的年末总股本" /></td>
        </tr>)}
      </Table>
      <Table label="历年现金循环周期" heads={["年度", ...cccDays.map(({ label }) => label)]}>
        {rows.map(({ year, date, wc }) => <tr key={date}>
          <th scope="row">{year} 年</th>
          {cccDays.map(({ key }) => <td key={key}>
            <Value value={wc?.[key]} date={date} code={key} fmt="days" missing="未披露或无法计算" />
          </td>)}
        </tr>)}
      </Table>
      {hasHistory && <Table label="历年杜邦分析" heads={["年度", ...DUPONT.map(({ label }) => label)]}>
        {rows.map(({ year, date, history }) => <tr key={date}>
          <th scope="row">{year} 年</th>
          {DUPONT.map(({ key, fmt }) => <td key={key}><Value value={history?.[key]} date={date}
            code={`overview:${key}`} fmt={fmt} missing="缺少所需披露或有效分母" /></td>)}
        </tr>)}
      </Table>}
    </Details>
  </section>;
}

const CHANGE_HEADERS = ["科目", "期初", "期末", "变动额"];
const magnitude = (value: number | null) => value == null ? -1 : Math.abs(value);

export function Overview({ bundle, year }: { bundle: Bundle; year: string }) {
  const date = `${year}1231`;
  const prior = `${Number(year) - 1}1231`;
  const report = bundle.overview?.years.find((row) => row.end_date === date);
  const disclosure = report?.disclosure;
  const product = disclosure?.products;
  const inventory = disclosure?.inventory;
  const balance = bundle.reformulated_bs.find((row) => row.end_date === date);
  const income = bundle.reformulated_is.find((row) => row.end_date === date && row.period_kind === "cumulative");
  const ratio = bundle.ratios.find((row) => row.end_date === date && row.basis === "average");
  const priorRatio = bundle.ratios.find((row) => row.end_date === prior && row.basis === "average");
  const cash = bundle.cash_summary.find((row) => row.end_date === date);
  const priorCash = bundle.cash_summary.find((row) => row.end_date === prior);
  const capital = bundle.capital_summary.find((row) => row.end_date === date);
  const workingCapital = bundle.working_capital.find((row) => row.end_date === date);
  const cashSteps = bundle.cash_bridge.filter((row) => row.end_date === date);
  const raw = (key: string, asOf = date) => bundle.calculation_details?.[asOf]?.[`raw:${key}`]?.value;
  const v = (value: ValueProps["value"], code?: string, props?: Omit<ValueProps, "value" | "code">) =>
    <Value date={date} value={value} code={code} {...props} />;
  const movements = bundle.econ_evolution_groups.filter((row) => row.end_date === date)
    .sort((a, b) => magnitude(b.delta) - magnitude(a.delta));
  const largestOperatingAsset = bundle.econ_map_nodes.filter((row) => row.end_date === date &&
    row.layer === 2 && row.node_id !== "financial_assets" && row.value != null && row.value > 0)
    .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))[0];
  const movementRow = (row: typeof movements[number]) => <tr key={row.group_id}>
    <th scope="row">{textZh(row.label)}</th>
    <td>{v(row.begin_value, undefined, { missing: "缺少期初余额" })}</td>
    <td>{v(row.end_value, `map:${row.group_id}`)}</td>
    <td className={row.delta == null ? "" : row.delta < 0 ? "overview__decrease" : "overview__increase"}>
      {v(row.delta, `delta:${row.group_id}`, { signed: true, missing: row.evo_flags || "缺少可比余额" })}
    </td>
  </tr>;
  const oe = report?.oa_share;
  const fe = report?.fa_share;
  const distribution = disclosure?.shareholder_distribution;
  const repurchase = disclosure?.share_repurchase;
  const revenueGrowth = report?.revenue_yoy;
  const capitalChange = capital?.delta_noa;
  const opposingTrends = revenueGrowth != null && capitalChange != null &&
    (revenueGrowth < 0 && capitalChange > 0 || revenueGrowth > 0 && capitalChange < 0);
  const cashComparisons = [
    { label: "经营活动现金流量净额", code: "cfo", current: cash?.cfo, prior: priorCash?.cfo },
    { label: "销售商品、提供劳务收到的现金", code: "cash_received_from_sales",
      current: raw("cash_received_from_sales"), prior: raw("cash_received_from_sales", prior) },
  ];
  const bridge = [
    ["经营活动现金流量净额", "cfo", cash?.cfo],
    ["投资活动现金流量净额", "cfi", raw("cfi")],
    ["筹资活动现金流量净额", "cff", raw("cff")],
    ["汇率变动对现金及现金等价物的影响", "fx_effect_on_cash", raw("fx_effect_on_cash")],
    ["现金及现金等价物净增加额", "net_increase_in_cash", raw("net_increase_in_cash")],
  ] as const;

  return <main className="overview" aria-label={`${year} 年经营总览`}>
    <OverviewHistory bundle={bundle} year={year} />

    <section id="business-model" className="overview__section" aria-labelledby="business-heading">
      <h3 id="business-heading">这是一门什么样的生意？</h3>
      <div className="overview__columns">
        <div>
          <h4>收入与盈利来源</h4>
          <dl className="overview__metrics">
            <Metric label="营业收入">{v(income?.revenue, "raw:revenue")}</Metric>
            <Metric label="毛利率">{v(ratio?.gross_margin, "gross_margin", { fmt: "pct", missing: "未披露或无法计算" })}</Metric>
          </dl>
          {product?.rows.length ? <>
            <Table label="分产品或业务的收入和毛利率" heads={["产品或业务", "收入", "毛利率"]}>
              {product.rows.map((row) => <tr key={row.label}>
                <th scope="row">{row.label}</th><td>{v(row.revenue)}</td><td>{v(row.gross_margin, undefined, { fmt: "pct2" })}</td>
              </tr>)}
            </Table>
            <Source {...product}>年报 · 分产品或业务</Source>
          </> : <p className="overview__note">数据包暂无本年分产品或业务的收入与毛利率。</p>}
        </div>
        <div>
          <h4>资产结构与资本占用 <small>年末余额</small></h4>
          {oe != null && fe != null && oe >= 0 && fe >= 0 && oe + fe > 0 &&
            <div className="overview__asset-bar" aria-hidden="true">
              <span style={{ flexGrow: oe }} /><span style={{ flexGrow: fe }} />
            </div>}
          <dl className="overview__ledger overview__assets">
            <div><dt>经营资产 {oe != null && v(oe, "overview:oa_share", { fmt: "pct" })}</dt><dd>{v(balance?.oa, "oa")}</dd></div>
            <div><dt>金融资产 {fe != null && v(fe, "overview:fa_share", { fmt: "pct" })}</dt><dd>{v(balance?.fa, "fa")}</dd></div>
            <div><dt>经营负债</dt><dd>{v(balance?.ol, "ol")}</dd></div>
            <div className="overview__total"><dt>净经营资产</dt><dd>{v(balance?.noa, "noa")}</dd></div>
          </dl>
          {largestOperatingAsset && <p className="overview__note">
            经营资产中金额最大的是{textZh(largestOperatingAsset.label)}，{v(largestOperatingAsset.value, `map:${largestOperatingAsset.node_id}`)}。
            {largestOperatingAsset.node_id === "inventory" && workingCapital?.dio != null && <> 存货周转天数为 {fmtMetric(workingCapital.dio, "days")}。</>}
          </p>}
          <p className="overview__note">净经营资产为经营资产扣除经营负债后的余额。金融资产中可动用的金额取决于资产性质与使用限制。</p>
        </div>
      </div>
      <div className="overview__return">
        <h4>经营回报由什么驱动</h4>
        <dl className="overview__metrics">
          <Metric label="净经营资产收益率（RNOA）">{v(ratio?.rnoa, "rnoa", { fmt: "pct", missing: ratio?.ratio_flags || "缺少可用的平均净经营资产" })}</Metric>
          <Metric label="税后经营利润率（OPM）">{v(ratio?.opm, "opm", { fmt: "pct", missing: "缺少可用的税后经营收益或营业总收入" })}</Metric>
          <Metric label="净经营资产周转率（ATO）">{v(ratio?.ato, "ato", { fmt: "x", missing: ratio?.ratio_flags || "缺少可用的平均净经营资产" })}</Metric>
          <Metric label="合并净资产收益率（ROTCE）">{v(ratio?.rotce_direct, "rotce_direct", { fmt: "pct", missing: "缺少可用的平均合并净资产" })}</Metric>
        </dl>
        <p className="overview__note">RNOA ＝ OPM × ATO。毛利率以营业收入为分母，OPM 和 ATO 使用营业总收入。税后经营收益采用财报重构口径，资本采用期初和期末平均值。</p>
      </div>
      <div className="overview__links">
        <AppLink href={withYear(VIEW_PATHS.tree, year)}>查看盈利驱动树 →</AppLink>
        <AppLink href={withYear(VIEW_PATHS.map, year)}>查看商业经济地图 →</AppLink>
      </div>
      <Details label="查看经营回报与资本占用的多年趋势" charts>
        <div className="overview__columns">
          <div>
            <h4>经营回报与权益回报</h4><ReturnsChart ratios={bundle.ratios} year={year} />
            <ConceptLinks ids={["rnoa", "rotce", "roce"]} year={year} />
          </div>
          <div>
            <h4>经营资本占用</h4><CapitalChart bs={bundle.reformulated_bs} year={year} />
            <ConceptLinks ids={["noa", "nfo"]} year={year} />
          </div>
        </div>
      </Details>
    </section>

    <section id="annual-changes" className="overview__section" aria-labelledby="change-heading">
      <h3 id="change-heading">当年这门生意发生了什么变化？</h3>
      <dl className="overview__metrics overview__metrics--change">
        <Metric label="营业收入同比">{v(report?.revenue_yoy, "overview:revenue_yoy", { fmt: "pct2", signed: true, missing: "缺少可用的收入对比基数" })}</Metric>
        <Metric label="净经营资产变动">{v(capital?.delta_noa, "delta_noa", { signed: true, missing: "缺少可比余额" })}</Metric>
        <Metric label="净经营资产收益率变动">{v(report?.rnoa_change, "overview:rnoa_change", { fmt: "pp", signed: true, missing: "缺少可比回报率" })}</Metric>
        <Metric label="净经营资产周转率" context={priorRatio?.ato != null && <>上年 {v(priorRatio.ato, "ato", { date: prior, fmt: "x" })}</>}>
          {v(ratio?.ato, "ato", { fmt: "x", missing: "缺少本年周转率" })}
        </Metric>
      </dl>
      {opposingTrends && <p className="overview__callout">
        {capitalChange > 0 ? "营业收入下降，净经营资产占用增加。" : "营业收入增加，净经营资产占用减少。"}
        {ratio?.ato != null && priorRatio?.ato != null && <> 同期净经营资产周转率从 {v(priorRatio.ato, "ato", { date: prior, fmt: "x" })} 变为 {v(ratio.ato, "ato", { fmt: "x" })}。</>}
      </p>}
      <h4>主要余额变动</h4>
      {movements.length ? <>
        <p className="overview__note">按变动金额的绝对值排序。这里显示资产和资金来源的账面余额变化。</p>
        <Table label="主要余额变动" heads={CHANGE_HEADERS}>{movements.slice(0, 6).map(movementRow)}</Table>
        {movements.length > 6 && <Details label="查看其余余额变动">
          <Table label="其余余额变动" heads={CHANGE_HEADERS}>{movements.slice(6).map(movementRow)}</Table>
        </Details>}
      </> : <p className="overview__note">数据包暂无本年资产及资金来源的分组余额。</p>}
      {inventory?.rows.length ? <Details label="存货构成与变动" expanded>
        <Table label="存货构成与变动" heads={CHANGE_HEADERS}>{inventory.rows.map((row) => <tr key={row.label}>
          <th scope="row">{row.label}</th><td>{v(row.begin)}</td><td>{v(row.end)}</td><td>{v(row.delta, undefined, { signed: true, missing: "缺少可比余额" })}</td>
        </tr>)}</Table>
        <Source {...inventory}>年报 · 存货附注</Source>
      </Details> : <p className="overview__note">数据包暂无本年存货构成附注。</p>}
      <div className="overview__links"><AppLink href={withYear(VIEW_PATHS.capital, year)}>查看资本与再投资 →</AppLink></div>
      <Details label="查看营运资本周转天数趋势" charts>
        <p className="overview__note">存货周转天数使用独立纵轴。应付天数以营业成本加存货增加额估算采购额。</p>
        <WcDaysChart wc={bundle.working_capital} year={year} />
        <ConceptLinks ids={["ccc", "dio", "dso", "dpo", "advances"]} year={year} />
      </Details>
    </section>

    <section id="cash-allocation" className="overview__section" aria-labelledby="cash-heading">
      <h3 id="cash-heading">创造出来的利润最终去了哪里？</h3>
      <dl className="overview__metrics overview__metrics--cash">
        <Metric label="合并净利润">{v(cash?.ni_total ?? income?.ni_total, "raw:net_income_total")}</Metric>
        <Metric label="经营活动现金流量净额" context={report?.cfo_yoy != null && <>同比 {v(report.cfo_yoy, "overview:cfo_yoy", { fmt: "pct2", signed: true })}</>}>
          {v(cash?.cfo, "raw:cfo")}
        </Metric>
        <Metric label="经营现金流／净利润">{v(cash?.cash_conversion, "cash_conversion", { fmt: "pct", missing: cash?.cf_flags || "缺少可用的净利润或经营现金流" })}</Metric>
      </dl>
      <Table label="经营现金流与销售收现对比" heads={["科目", `${prior.slice(0, 4)} 年`, `${year} 年`]}>
        {cashComparisons.map((row) => <tr key={row.code}>
          <th scope="row">{row.label}</th>
          <td>{v(row.prior, `raw:${row.code}`, { date: prior, missing: "无上年数据" })}</td>
          <td>{v(row.current, `raw:${row.code}`)}</td>
        </tr>)}
      </Table>
      {disclosure?.cash_explanation && <aside className="overview__callout">
        <p>{disclosure.cash_explanation.text}</p>
        <Source {...disclosure.cash_explanation}>年报 · 现金流量变动说明</Source>
      </aside>}
      <div className="overview__columns overview__allocation">
        <div>
          <h4>资金用在哪里</h4>
          <dl className="overview__ledger">
            <div><dt>购建固定资产、无形资产和其他长期资产支付的现金</dt><dd>{v(cash?.capex_paid ?? raw("capex_paid"), "raw:capex_paid")}</dd></div>
            <div><dt>投资支付的现金</dt><dd>{v(raw("cash_paid_for_investments"), "raw:cash_paid_for_investments")}</dd></div>
            <div><dt>收回投资收到的现金</dt><dd>{v(raw("cash_from_investment_disposals"), "raw:cash_from_investment_disposals")}</dd></div>
            <div><dt>投资收付净流出（负值为净流入）</dt><dd>{v(report?.investment_net_outflow, "overview:investment_net_outflow", { missing: "缺少投资收付明细" })}</dd></div>
            <div>
              <dt>{distribution?.value != null ? "向股东分配利润（含少数股东）" : "分配股利、利润或偿付利息支付的现金"}
                {distribution?.value != null && <Source {...distribution}>权益变动表</Source>}
              </dt>
              <dd>{distribution?.value != null ? v(distribution.value) : v(raw("dividends_and_interest_paid"), "raw:dividends_and_interest_paid")}</dd>
            </div>
            <div>
              <dt>回购股份支付的现金 {repurchase && <Source {...repurchase}>年报附注</Source>}</dt>
              <dd>{v(repurchase?.value, undefined, { missing: "缺少单项披露" })}</dd>
            </div>
          </dl>
          <p className="overview__note">本年净经营资产变动 {v(capital?.delta_noa, "delta_noa", { signed: true, missing: "缺少可比余额" })}。存货及其他经营资本的余额变动提供额外的再投资线索。</p>
        </div>
        <div>
          <h4>现金及现金等价物如何变化</h4>
          <dl className="overview__ledger">
            {bridge.map(([label, code, value]) => <div key={code} className={code === "net_increase_in_cash" ? "overview__total" : undefined}>
              <dt>{label}</dt><dd>{v(value, `raw:${code}`, { signed: true })}</dd>
            </div>)}
          </dl>
          <p className="overview__note">经营、投资及筹资现金流量净额加汇率影响，对应全年现金及现金等价物净变动。</p>
        </div>
      </div>
      <Details label="查看净利润到经营现金流的调节明细" charts>
        {cashSteps.length > 0 ? <><p className="overview__note">根据现金流量表补充资料列示当年披露的调整项目。{cash?.cf_flags && ` ${cash.cf_flags}`}</p>
          <WaterfallChart steps={cashSteps} />
          <ConceptLinks ids={["cfo", "fcf"]} year={year} />
        </> : <p className="overview__note">本年暂无现金流调节数据。</p>}
      </Details>
    </section>
  </main>;
}
