/** 贵州茅台（600519.SH）六步导览案例：按 总览 → 商业经济地图 → 盈利驱动树 →
 *  资本与再投资 → 价值创造 → 估值与反向分析 的顺序，引用公司数据包中已算好的
 *  结果，一步步说明这家公司的商业实质。本文件只做展示与格式化。
 */
import { AuditValue } from "./CalculationPopover";
import { formatAmount, formatNumber, formatPrice } from "./format";
import { ConceptLinks } from "./KnowledgeLink";
import { textZh } from "./locale";
import { buildMoutaiFacts, MOUTAI_TS_CODE, type MoutaiFacts } from "./moutaiFacts";
import { AppLink } from "./Navigation";
import { bundleUrl } from "./site";
import { VIEW_PATHS, withYear } from "./routes";
import type { Bundle } from "./types";

const pct = (v: number | null | undefined, dp = 1) =>
  typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(dp)}%` : "—";
const times = (v: number | null | undefined, dp = 2) =>
  typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(dp)} 倍` : "—";
const days = (v: number | null | undefined) =>
  typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(0)} 天` : "—";
const ratio = (v: number | null | undefined, dp = 2) =>
  typeof v === "number" && Number.isFinite(v) ? formatNumber(v, dp) : "—";

function StepLink({ view, label, year }: { view: keyof typeof VIEW_PATHS; label: string; year: string }) {
  return <p><AppLink href={withYear(VIEW_PATHS[view], year)}>打开{label} →</AppLink></p>;
}

function YearTable({ caption, years, rows }: {
  caption: string; years: string[];
  rows: { label: string; code: string; values: string[] }[];
}) {
  return <div className="cases__table-wrap" role="region" aria-label={`${caption}，可横向滚动`} tabIndex={0}>
    <table className="cases__table">
      <caption>{caption}</caption>
      <thead><tr><th scope="col">科目</th>{years.map((y) => <th scope="col" key={y}>{y}</th>)}</tr></thead>
      <tbody>{rows.map((row) => <tr key={row.label}>
        <th scope="row">{row.label}</th>{row.values.map((v, i) => <td key={years[i]}><AuditValue year={years[i]} code={row.code}>{v}</AuditValue></td>)}
      </tr>)}</tbody>
    </table>
  </div>;
}

function StepOverview({ facts, year }: { facts: MoutaiFacts; year: string }) {
  const o = facts.overview;
  return <section className="panel cases__section">
    <p className="cases__eyebrow">第一步 · 总览</p>
    <h3>这是一门什么生意？</h3>
    <p>{facts.latestYear}年，贵州茅台的营业总收入为 <AuditValue year={facts.latestYear} code="raw:total_revenue">{formatAmount(o.totalRevenue)}</AuditValue>，毛利率 <AuditValue year={facts.latestYear} code="gross_margin">{pct(o.grossMargin)}</AuditValue>，
      税后经营收益（OI）<AuditValue year={facts.latestYear} code="oi_after_tax">{formatAmount(o.oiAfterTax)}</AuditValue>，归母净利润 <AuditValue year={facts.latestYear} code="raw:net_income_parent">{formatAmount(o.niParent)}</AuditValue>。
      这是一门极高毛利的产品生意：收入减去营业成本后，九成以上留在公司。</p>
    <dl className="cases__results">
      <div><dt>净经营资产收益率（RNOA，平均资本）</dt><dd><AuditValue year={facts.latestYear} code="rnoa">{pct(o.rnoa)}</AuditValue></dd></div>
      <div><dt>合并净资产收益率（ROTCE，平均资本）</dt><dd><AuditValue year={facts.latestYear} code="rotce_direct">{pct(o.rotce)}</AuditValue></dd></div>
      <div><dt>年末净经营资产（NOA）</dt><dd><AuditValue year={facts.latestYear} code="noa">{formatAmount(o.noa)}</AuditValue></dd></div>
      <div><dt>年末净金融负债（NFO，负值为净金融资产）</dt><dd><AuditValue year={facts.latestYear} code="nfo">{formatAmount(o.nfo)}</AuditValue></dd></div>
      <div><dt>经营活动现金流量净额（CFO）</dt><dd><AuditValue year={facts.latestYear} code="raw:cfo">{formatAmount(o.cfo)}</AuditValue></dd></div>
      <div><dt>经营现金流量净额／净利润</dt><dd><AuditValue year={facts.latestYear} code="cash_conversion">{times(o.cashConversion)}</AuditValue></dd></div>
    </dl>
    <p>两个回报率的巨大差距是读懂报表的第一把钥匙：经营本身的回报（RNOA {pct(o.rnoa)}）远高于
      股东整体拿到的回报（ROTCE {pct(o.rotce)}）。差异来自资产负债表上巨额的净金融资产
      （NFO 为 {formatAmount(o.nfo)}，财务杠杆 FLEV {ratio(o.flev)}）：生意本身只占用
      {formatAmount(o.noa)} 净经营资产，其余权益以存款和理财形态趴在账上，按市场利率而非茅台的生意回报率生息，拉低了股东层面的平均回报。</p>
    <p className="cases__insight">本步结论：先把“生意的回报”与“账上现金的回报”分开。经营引擎极强、所需资本极少，
      公司的报表更像“一门小资本生意 + 一个大现金池”。后面五步分别回答：钱从哪来、投在哪里、回报由什么驱动、新增资本是否创造价值、市场怎么定价。</p>
    <StepLink view="overview" label="总览" year={facts.latestYear} />
    <ConceptLinks ids={["reformulation", "rnoa", "rotce", "noa", "nfo"]} year={year} />
  </section>;
}

function StepMap({ facts, year }: { facts: MoutaiFacts; year: string }) {
  return <section className="panel cases__section">
    <p className="cases__eyebrow">第二步 · 商业经济地图</p>
    <h3>钱从哪里来，用在了哪里？（{facts.latestYear}年末）</h3>
    <div className="cases__results">
      {facts.mapSources.map((n) => <div key={n.node_id}>
        <dt>来源 · {textZh(n.label)}</dt><dd><AuditValue year={n.end_date} code={`map:${n.node_id}`}>{formatAmount(n.value)}</AuditValue></dd>
      </div>)}
    </div>
    <div className="cases__results">
      {facts.mapUses.map((n) => <div key={n.node_id}>
        <dt>投向 · {textZh(n.label)}</dt><dd><AuditValue year={n.end_date} code={`map:${n.node_id}`}>{formatAmount(n.value)}</AuditValue></dd>
      </div>)}
    </div>
    <p>来源端几乎全部是股东自己的钱：归母权益远大于金融负债；供应商信用与客户预收合计只占小头。
      投向端则高度集中——金融资产（现金池）体量最大，经营资产中存货独大，厂房设备反而是配角。
      酿酒需要基酒长年陈放，存货是这门生意真正的“产能”。</p>
    <p>地图第五层（资本配置）给出同样的信号：{facts.latestYear}年分红及利息支出
      {formatAmount(facts.dividendsInterest)}，而购建长期资产仅支付 {formatAmount(facts.capexAlloc)}。
      赚到的现金绝大部分不需要投回生意，而是分掉或者继续堆在现金池里。</p>
    <p className="cases__insight">本步结论：这是一张“客户和供应商曾经出钱、如今股东自己出钱”的地图。
      经营所需资本集中在存货；现金池的去向（分红还是堆积）是股东回报的关键变量。</p>
    <StepLink view="map" label="商业经济地图" year={facts.latestYear} />
    <ConceptLinks ids={["equity", "advances", "owc"]} year={year} />
  </section>;
}

function StepTree({ facts, year }: { facts: MoutaiFacts; year: string }) {
  const years = facts.ratioRows.map((r) => r.end_date.slice(0, 4));
  const peak = facts.atoPeak;
  return <section className="panel cases__section">
    <p className="cases__eyebrow">第三步 · 盈利驱动树</p>
    <h3>高回报由什么驱动，又为何回落？</h3>
    <p>RNOA ＝ 税后经营利润率（OPM）× 净经营资产周转率（ATO）。沿年度看这两个驱动因素，
      答案非常干净：利润率相对稳定，周转率的波动更明显。</p>
    <YearTable caption="RNOA 分解（平均资本口径）；“—”表示缺少期初余额或不予展示。" years={years}
      rows={[
        { label: "净经营资产收益率（RNOA）", code: "rnoa", values: facts.ratioRows.map((r) => pct(r.rnoa)) },
        { label: "税后经营利润率（OPM）", code: "opm", values: facts.ratioRows.map((r) => pct(r.opm)) },
        { label: "净经营资产周转率（ATO）", code: "ato", values: facts.ratioRows.map((r) => times(r.ato)) },
        { label: "毛利率", code: "gross_margin", values: facts.ratioRows.map((r) => pct(r.gross_margin)) },
      ]} />
    <p>{peak ? `ATO 在 ${peak.end_date.slice(0, 4)}年达到 ${times(peak.ato)}的峰值，RNOA 同年为 ${pct(peak.rnoa)}；` : ""}
      到{facts.latestYear}年 ATO 回落至 {times(facts.ratioRows[facts.ratioRows.length - 1]?.ato ?? null)}。
      同期 OPM 始终在五成上下。换句话说，回报率的回落不是“卖得便宜了”，而是“每一元收入占用的资本变多了”。</p>
    <p>{facts.latestYear}年每 1 元营业总收入占用净经营资产 {ratio(facts.noaToSales)} 元，拆开看（减项为经营负债的抵减）：</p>
    <div className="cases__table-wrap" role="region" aria-label="资本密集度构成，可横向滚动" tabIndex={0}>
      <table className="cases__table">
        <caption>每元收入占用的净经营资产构成，{facts.latestYear}年（平均资本）。</caption>
        <thead><tr><th scope="col">构成项</th><th scope="col">每元收入占用</th></tr></thead>
        <tbody>{facts.intensity.map((c) => <tr key={c.nodeId}>
          <th scope="row">{textZh(c.label)}{(c.weight ?? 0) < 0 ? "（减项）" : ""}</th>
          <td><AuditValue year={facts.latestYear} code={`tree:${c.nodeId}`}>{ratio(c.value)}</AuditValue></td>
        </tr>)}</tbody>
      </table>
    </div>
    <p className="cases__insight">本步结论：驱动树把“回报回落”精确定位到周转，而周转的分母大头是存货。
      下一步去资本与再投资页面看：这些存货是哪几年、以什么速度堆起来的。</p>
    <StepLink view="tree" label="盈利驱动树" year={facts.latestYear} />
    <ConceptLinks ids={["opm", "ato", "gross-margin", "capital-basis"]} year={year} />
  </section>;
}

function StepCapital({ facts, year }: { facts: MoutaiFacts; year: string }) {
  const years = facts.capitalRows.map((r) => r.end_date.slice(0, 4));
  const rMin = facts.reinvestMin;
  const latest = facts.latestCapital;
  return <section className="panel cases__section">
    <p className="cases__eyebrow">第四步 · 资本与再投资</p>
    <h3>每年新增的资本去了哪里，是谁出的钱？</h3>
    <YearTable caption="净经营资产变动与再投资；再投资率 = ΔNOA ÷ 税后经营收益。" years={years}
      rows={[
        { label: "净经营资产变动（ΔNOA）", code: "delta_noa", values: facts.capitalRows.map((r) => formatAmount(r.delta_noa)) },
        { label: "再投资率", code: "reinvestment_rate", values: facts.capitalRows.map((r) => pct(r.reinvestment_rate)) },
        { label: "净经营资产增速", code: "noa_growth", values: facts.capitalRows.map((r) => pct(r.noa_growth)) },
        { label: "营业总收入增速", code: "revenue_growth", values: facts.capitalRows.map((r) => pct(r.revenue_growth)) },
        { label: "资本开支／折旧摊销（倍）", code: "capex_to_da", values: facts.capitalRows.map((r) => ratio(r.capex_to_da, 1)) },
      ]} />
    <p>表里藏着两段完全不同的历史。{rMin ? `${rMin.end_date.slice(0, 4)}年再投资率为 ${pct(rMin.reinvestment_rate)}：
      净经营资产不增反减，因为客户预收款大涨，相当于客户替公司出了全部经营资本还有富余。` : ""}
      客户预收款天数从{facts.advancesPeak ? `${facts.advancesPeak.year}年的 ${days(facts.advancesPeak.days)}` : "峰值"}一路降到
      {facts.advancesLatest ? `${facts.advancesLatest.year}年的 ${days(facts.advancesLatest.days)}` : "低位"}——
      这项“免费资金”正在持续消退。</p>
    <p>近年则相反：净经营资产增速持续高于收入增速{latest ? `，${facts.latestYear}年收入增速 ${pct(latest.revenue_growth)}，
      净经营资产却增长 ${pct(latest.noa_growth)}（ΔNOA ${formatAmount(latest.delta_noa)}）` : ""}。
      增量主要不是厂房——资本开支常年只有折旧摊销的一到三倍、金额很小——而是存货：
      {facts.latestYear}年存货增加 {formatAmount(facts.inventoryDelta)}，存货周转天数升至 {days(facts.dioLatest)}。
      这也解释了现金转化的波动{facts.cashConversionMin ? `（最低的${facts.cashConversionMin.year}年，经营现金流量净额只有净利润的 ${ratio(facts.cashConversionMin.value)} 倍）` : ""}：利润被暂时锁进了营运资本。</p>
    <p className="cases__insight">本步结论：再投资的形态是“存多几年的酒”，而不是“建更多的厂”。
      存货既可能是未来提价放量的蓄水池，也可能是收入放缓下的被动积压——报表只能识别事实，判断要留给使用者。
      同时，客户预付这台旧引擎在熄火，新增资本越来越要股东自己出。</p>
    <StepLink view="capital" label="资本与再投资" year={facts.latestYear} />
    <ConceptLinks ids={["reinvestment", "capex", "dio", "advances", "cfo"]} year={year} />
  </section>;
}

function StepValue({ facts, year }: { facts: MoutaiFacts; year: string }) {
  const v = facts.valueLatest;
  return <section className="panel cases__section">
    <p className="cases__eyebrow">第五步 · 价值创造</p>
    <h3>扣掉资本的机会成本，还剩多少收益？</h3>
    {v && <>
      <p>给期初净经营资产按必要报酬率 {pct(v.r_op_assumed)}（显式假设，可在价值创造页调整口径阅读）计提资本费用后：</p>
      <dl className="cases__results">
        <div><dt>税后经营收益（OI）</dt><dd><AuditValue year={facts.latestYear} code="oi_after_tax">{formatAmount(v.oi_after_tax)}</AuditValue></dd></div>
        <div><dt>资本费用（{pct(v.r_op_assumed)} × 期初 NOA）</dt><dd><AuditValue year={facts.latestYear} code="capital_charge">{formatAmount(v.capital_charge)}</AuditValue></dd></div>
        <div><dt>剩余经营收益（ReOI）</dt><dd><AuditValue year={facts.latestYear} code="reoi">{formatAmount(v.reoi)}</AuditValue></dd></div>
        <div><dt>普通股剩余收益（权益口径）</dt><dd><AuditValue year={facts.latestYear} code="re_common">{formatAmount(v.re_common)}</AuditValue></dd></div>
      </dl>
      <p>资本费用与收益相比微不足道，ReOI 几乎等于 OI——价值的来源不是报表上的资本，而是品牌与定价权这类
        不入账的资产。权益口径的剩余收益（{formatAmount(v.re_common)}）明显低于 ReOI，差额正是现金池：
        巨额净金融资产的收益低于权益必要报酬率 {pct(v.r_e_assumed)}，在股东层面持续“漏掉”价值。</p>
      <p>{facts.latestYear}年 ReOI 变动 {formatAmount(v.delta_reoi)}。佩曼驱动拆分给出同一故事的另一面：
        增长效应 {formatAmount(v.growth_effect)}（期初资本比上年多了），周转效应 {formatAmount(v.turnover_effect)}——
        两者几乎抵消。新投入的资本（主要是存货）在当年的边际上没有赚到钱。</p>
    </>}
    {!v && <p className="flag">最新年度的剩余收益数据不可用。</p>}
    <p className="cases__insight">本步结论：存量上，这仍是罕见的价值创造机器——ReOI 接近收益本身；
      边际上，{facts.latestYear}年的新增资本尚未产生回报，价值创造的增量引擎停了下来。
      这正是估值要回答的问题：市场为“未来重新开动”定了什么价？</p>
    <StepLink view="value" label="价值创造" year={facts.latestYear} />
    <ConceptLinks ids={["reoi", "equity-re", "required-return", "oi"]} year={year} />
  </section>;
}

function StepValuation({ facts, year }: { facts: MoutaiFacts; year: string }) {
  const years = facts.valuationRows.map((r) => r.end_date.slice(0, 4));
  const low = facts.vToPMin;
  const latest = facts.valuationLatest;
  return <section className="panel cases__section">
    <p className="cases__eyebrow">第六步 · 估值与反向分析</p>
    <h3>市场为什么样的未来定了价？</h3>
    <YearTable caption="模型价值为 ReOI 永续增长模型（必要报酬率与增长率为显式假设）；年末价格对照其后公布的年报账面值，存在后见偏差，口径见估值页。" years={years}
      rows={[
        { label: "年末市值", code: "market_cap", values: facts.valuationRows.map((r) => formatAmount(r.market_cap)) },
        { label: "模型权益价值", code: "v_equity_reoi_g", values: facts.valuationRows.map((r) => formatAmount(r.v_equity_reoi_g)) },
        { label: "价值／价格（V/P，倍）", code: "v_to_p", values: facts.valuationRows.map((r) => ratio(r.v_to_p)) },
        { label: "价格隐含的永续增长率", code: "implied_g_reoi", values: facts.valuationRows.map((r) => pct(r.implied_g_reoi)) },
        { label: "远期市盈率（市场，倍）", code: "forward_pe_market", values: facts.valuationRows.map((r) => ratio(r.forward_pe_market, 1)) },
        { label: "远期市盈率（模型，倍）", code: "forward_pe_model", values: facts.valuationRows.map((r) => ratio(r.forward_pe_model, 1)) },
      ]} />
    <p>反向分析不预测，只翻译价格。{low ? `${low.end_date.slice(0, 4)}年末 V/P 低至 ${ratio(low.v_to_p)}：
      市值 ${formatAmount(low.market_cap)}，是模型价值的两倍多；当时价格隐含的永续增长率为 ${pct(low.implied_g_reoi)}，
      市场远期市盈率 ${ratio(low.forward_pe_market, 1)} 倍，而模型给出的只有 ${ratio(low.forward_pe_model, 1)} 倍。` : ""}
      此后隐含增长率逐年回落。</p>
    {latest && <p>{facts.latestYear}年末（收盘价 {formatPrice(latest.price)}）V/P 为 {ratio(latest.v_to_p)}，
      模型价值 {formatAmount(latest.v_equity_reoi_g)} 高于当年市值 {formatAmount(latest.market_cap)}。
      价格隐含的永续增长率降到 {pct(latest.implied_g_reoi)}（低于模型假设的 {pct(latest.g_assumed)}），
      等价地，在 {pct(latest.g_assumed)} 增长下价格隐含的经营必要报酬率为 {pct(latest.implied_r_op)}。
      同年历史异常盈利增长（AEG）为 {formatAmount(latest.aeg_actual)}，印证了第五步的边际减速。</p>}
    <p className="cases__insight">本步结论：十年间市场对茅台的定价从“高增长信仰”（隐含增长远高于假设、远期市盈率约
      {low ? ` ${ratio(low.forward_pe_market, 0)}` : ""} 倍）回落到隐含增长低于 {latest ? pct(latest.g_assumed) : "假设"}。
      当下的分歧不再是利润率，而是第四步的那堆存货与消退的预收：如果周转修复，现价隐含的要求并不高；
      如果存货是积压，模型假设本身就要下调。结论依赖 r 与 g 的假设，请到估值页查看敏感性网格后再下判断。</p>
    <StepLink view="valuation" label="估值与反向分析" year={facts.latestYear} />
    <ConceptLinks ids={["valuation", "reverse-valuation", "aeg"]} year={year} />
  </section>;
}

export function MoutaiCase({ bundle, error, year }: { bundle: Bundle | null; error: string | null; year: string }) {
  if (error) return <section className="panel cases__section">
    <h3>公司数据加载失败</h3>
    <p className="flag">{error}</p>
    <p>本案例依赖 {MOUTAI_TS_CODE} 的公司数据包；其余参考案例不受影响。</p>
  </section>;
  if (!bundle) return <section className="panel cases__section"><p>正在加载公司数据…</p></section>;
  if (bundle.ts_code !== MOUTAI_TS_CODE) return <section className="panel cases__section">
    <h3>案例与当前数据包不匹配</h3>
    <p>本案例基于贵州茅台（{MOUTAI_TS_CODE}），当前加载的数据包为 {bundle.ts_code}。</p>
  </section>;
  const facts = buildMoutaiFacts(bundle);
  return <>
    <section className="panel cases__section">
      <p className="cases__eyebrow">公司案例 · 以{facts.latestYear}年为锚定年度</p>
      <h3>贵州茅台：用六个页面读一家公司的商业实质</h3>
      <p>本案例按分析页面的顺序走完一遍 600519.SH：每一步只引用数据包中已算好的结果，
        给出该步能识别的事实与边界，并链接到对应页面继续交互探索。
        金额为人民币，按亿元展示；所有计算在数据管道中完成并带勾稽校验。</p>
      <ol>
        <li>总览——这是一门什么生意？</li>
        <li>商业经济地图——钱从哪里来、用在哪里？</li>
        <li>盈利驱动树——回报由利润率还是周转驱动？</li>
        <li>资本与再投资——新增资本的形态与出资人？</li>
        <li>价值创造——扣除资本机会成本后还剩什么？</li>
        <li>估值与反向分析——市场为什么样的未来定了价？</li>
      </ol>
    </section>
    <StepOverview facts={facts} year={year} />
    <StepMap facts={facts} year={year} />
    <StepTree facts={facts} year={year} />
    <StepCapital facts={facts} year={year} />
    <StepValue facts={facts} year={year} />
    <StepValuation facts={facts} year={year} />
    <section className="panel cases__section cases__sources">
      <h3>商业实质小结与口径</h3>
      <p>六步合起来：一门由品牌定价权支撑的超高毛利生意，所需报表资本极少，历史上甚至由客户预付融资；
        近年预收消退、存货累积，回报率的回落全部来自周转端；市场定价已从高增长预期回落至隐含增长低于 3%。
        接下来值得跟踪的是：存货能否转化为收入、预收款天数是否企稳、现金池的分红节奏——以上为观察清单，不构成预测。</p>
      <p className="panel__note">口径提示：税后经营收益（OI）为分析重构口径，不等同于报表“营业利润”；
        RNOA 等比率为平均资本口径；必要报酬率与永续增长率为显式假设，可在相应页面查看敏感性；
        应付款项天数的采购额为近似口径；空值表示未披露或不予展示，原因见各页提示。</p>
      <p>数据来源：Tushare 年度合并财务报表与每日指标（600519.SH），数据导出于 {facts.exportedAt.slice(0, 10)}。</p>
      <p><a href={bundleUrl(MOUTAI_TS_CODE)} download>下载公司数据包（gzip 压缩的 JSON，含勾稽校验）</a></p>
      <p><AppLink href={withYear("/knowledge/data-quality", year)}>阅读数据口径</AppLink>{" · "}
        <AppLink href={withYear("/knowledge/units", year)}>金额单位说明</AppLink></p>
    </section>
  </>;
}
