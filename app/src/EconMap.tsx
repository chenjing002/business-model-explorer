/** Business Economics Map: one year's economic engine read top-to-bottom as a
 *  cycle — capital structure → operating cycle (days) → profit → cash
 *  conversion → allocation, looping back into next year's capital.
 *  Values precomputed in Python; this view renders, filters and JOINS
 *  declared related-metric keys — it never computes a financial number.
 *  Stack widths, waterfall offsets and share tooltips are chart geometry.
 *  Money sections share ONE linear scale so sizes compare across layers.
 */
import type { EChartsOption } from "echarts";
import { useMemo, useState, type ReactNode } from "react";
import { axisStyle, baseTextStyle, palette } from "./charts/theme";
import { toYiYuan, yearOf } from "./data";
import { METRIC_SOURCES, fmtMetric, relatedValue } from "./metrics";
import type { Bundle, EconMapNode } from "./types";
import { useECharts } from "./useECharts";
import { EvolutionSection } from "./EconEvolution";
import { KnowledgeLink } from "./KnowledgeLink";
import { conceptFor } from "./knowledge";
import { AuditValue } from "./CalculationPopover";
import { auditTarget } from "./calculationDetails";
import { accountLabel } from "./locale";
import { formatAmount, formatResidual, formatYiValue } from "./format";

/** Segment colors: hue = reformulation family (blue operating, teal financial,
 *  slate equity, amber customer money, sand "other"), lightness = member.
 *  Adjacent pairs validated (CVD + normal-vision floors) per dataviz method;
 *  the always-visible chips are the labeling relief for light segments. */
const SEG_COLORS: Record<string, string> = {
  // L1 资本来源
  common_equity: "#334155",
  minority_interests: "#a9b6c9",
  financial_debt: "#0d9488",
  supplier_credit: "#1d4ed8",
  customer_advances: "#b45309",
  other_operating_liabilities: "#cbb98f",
  // L2 资本占用
  inventory: "#1e3a8a",
  receivables_prepaid: "#1d4ed8",
  ppe_cip: "#3b82f6",
  intangibles_other_lt: "#60a5fa",
  other_operating_assets: "#cbb98f",
  financial_assets: "#0d9488",
  // L3 利润漏斗（浅→深：收入逐步提纯为税后经营收益）
  total_revenue: "#60a5fa",
  gross_profit: "#3b82f6",
  oi_core_pretax: "#1d4ed8",
  unusual_items: "#9ca3af",
  oi_after_tax: "#1e3a8a",
  // L5 资本配置
  capex_alloc: "#1d4ed8",
  dividends_interest: "#334155",
  debt_repaid: "#0d9488",
  other_financing_out: "#cbb98f",
  equity_raised: "#0d9488",
  net_cash_change: "#334155",
};
const ANCHOR = "#334155";
const POS_ADJ = "#1d4ed8";
const NEG = "#b91c1c";

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function NodeHistory({ nodes }: { nodes: EconMapNode[] }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...nodes].sort((a, b) => a.end_date.localeCompare(b.end_date));
    return {
      textStyle: baseTextStyle,
      grid: { left: 48, right: 8, top: 8, bottom: 22 },
      tooltip: { trigger: "axis", valueFormatter: (v) => (formatYiValue(v, 1)) },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", ...axisStyle() },
      series: [{
        type: "line",
        data: rows.map((r) => toYiYuan(r.value)),
        color: palette.operating,
        symbolSize: 4,
        areaStyle: { opacity: 0.08 },
      }],
    };
  }, [nodes]);
  return <div ref={useECharts(option, ({ axisValueLabel }) =>
    nodes[0] ? { date: `${axisValueLabel}1231`, code: `map:${nodes[0].node_id}` } : undefined)} className="inspector__chart" />;
}

/** 指标徽章：按声明键联接已导出指标表（METRIC_SOURCES），不做任何计算。 */
function Kpi({ bundle, year, k, caliber }: { bundle: Bundle; year: string; k: string; caliber?: string }) {
  const src = METRIC_SOURCES[k];
  if (!src) return null;
  return (
    <span className="kpi" title={caliber}>
      <span>{src.label}</span>
      <b><AuditValue year={year} code={k}>{fmtMetric(relatedValue(bundle, year, k), src.fmt)}</AuditValue></b>
    </span>
  );
}

function Connector({ text, children }: { text: string; children?: ReactNode }) {
  return (
    <div className="connector">
      <span className="connector__arrow" aria-hidden="true">↓</span>
      <span className="connector__text">{text}</span>
      {children}
    </div>
  );
}

function CheckLine({ label, residual }: { label: string; residual: number | null | undefined }) {
  return (
    <p className="mapsec__check">
      {label}：差额 {isNum(residual) ? formatResidual(residual) : "—"}（如实列示，不强制轧平）
    </p>
  );
}

/** 堆叠条 + 图例芯片。宽度按统一比例尺，段宽即金额占比。 */
function StackBar({ title, nodes, scaleMax, selected, onSelect }: {
  title: string; nodes: EconMapNode[]; scaleMax: number;
  selected: string; onSelect: (id: string) => void;
}) {
  const segs = nodes.filter((n) => (n.value ?? 0) > 0);
  const total = segs.reduce((s, n) => s + (n.value as number), 0);
  const negs = nodes.filter((n) => n.value != null && (n.value as number) < 0);
  return (
    <div className="stack">
      <div className="stack__head">
        <span className="stack__title">{title}</span>
        <span className="stack__total">合计 {formatAmount(total)}</span>
      </div>
      <div className="stack__bar" style={{ width: `${(total / scaleMax) * 100}%` }}>
        {segs.map((n) => {
          const share = (n.value as number) / total;
          const tip = `${n.label}：${formatAmount(n.value)}（占 ${(share * 100).toFixed(1)}%）`;
          return (
            <button key={n.node_id} type="button"
              className={`stack__seg${selected === n.node_id ? " stack__seg--active" : ""}`}
              style={{ width: `${share * 100}%`, background: SEG_COLORS[n.node_id] ?? palette.neutral }}
              aria-label={tip} {...auditTarget(n.end_date, `map:${n.node_id}`)}
              onClick={() => onSelect(n.node_id)} />
          );
        })}
      </div>
      <div className="stack__chips">
        {nodes.map((n) => (
          <button key={n.node_id} type="button"
            className={`chip${selected === n.node_id ? " chip--active" : ""}`}
            {...auditTarget(n.end_date, `map:${n.node_id}`)} onClick={() => onSelect(n.node_id)}>
            <i style={{ background: SEG_COLORS[n.node_id] ?? palette.neutral }} />
            <span>{n.label}</span>
            <b>{n.value == null ? "未披露" : formatAmount(n.value, "亿元", 1)}</b>
          </button>
        ))}
      </div>
      {negs.length > 0 && (
        <p className="mapsec__note">
          负值项不绘入堆叠条：{negs.map((n) => `${n.label} ${formatAmount(n.value)}`).join("；")}
        </p>
      )}
    </div>
  );
}

/** 单行流量条：标签 | 同比例尺条形 | 金额（与可选口径注记）。 */
function FlowRow({ node, scaleMax, selected, onSelect, color, annotation, offsetPct = 0, op }: {
  node: EconMapNode | undefined; scaleMax: number; selected: string;
  onSelect: (id: string) => void; color: string; annotation?: string;
  offsetPct?: number; op?: "+" | "−";
}) {
  if (!node) return null;
  const v = node.value;
  const w = v == null ? 0 : (Math.abs(v) / scaleMax) * 100;
  return (
    <button type="button"
      className={`frow${selected === node.node_id ? " frow--active" : ""}`}
      {...auditTarget(node.end_date, `map:${node.node_id}`)} onClick={() => onSelect(node.node_id)}>
      <span className="frow__label">{op && <em className="frow__op">{op}</em>}{node.label}</span>
      <span className="frow__track">
        {v != null && (
          <span className="frow__fill"
            style={{ marginLeft: `${offsetPct}%`, width: `${w}%`, background: v < 0 ? NEG : color }} />
        )}
      </span>
      <span className={`frow__value${v != null && v < 0 ? " frow__value--neg" : ""}`}>
        {v == null ? "未披露" : formatAmount(v)}
        {annotation && <small>{annotation}</small>}
      </span>
    </button>
  );
}

/** 天数条（本节使用天数比例尺）。点击跳到对应存量科目。 */
function DayBar({ title, parts, dayMax, marker, selected, onSelect, year }: {
  title: string;
  year: string; parts: { label: string; nodeId: string; metric: string; color: string; v: unknown }[];
  dayMax: number;
  marker?: { label: string; v: unknown };
  selected: string; onSelect: (id: string) => void;
}) {
  const shown = parts.filter((p) => isNum(p.v));
  return (
    <div className="days__row">
      <span className="days__title">{title}</span>
      <span className="days__track">
        {shown.map((p) => (
          <button key={p.nodeId} type="button" className="days__seg"
            style={{ width: `${(100 * (p.v as number)) / dayMax}%`, background: p.color }}
            {...auditTarget(year, p.metric)} aria-label={`${p.label}：${fmtMetric(p.v, "days")}`}
            onClick={() => onSelect(p.nodeId)} />
        ))}
        {marker && isNum(marker.v) && (
          <span className="days__marker" style={{ left: `${(100 * marker.v) / dayMax}%` }}
            {...auditTarget(year, "ccc")} aria-label={marker.label} />
        )}
      </span>
      <span className="days__legend">
        {parts.map((p) => (
          <button key={p.nodeId} type="button"
            className={`chip${selected === p.nodeId ? " chip--active" : ""}`}
            {...auditTarget(year, p.metric)} onClick={() => onSelect(p.nodeId)}>
            <i style={{ background: p.color }} />
            <span>{p.label}</span>
            <b>{isNum(p.v) ? fmtMetric(p.v, "days") : "未披露"}</b>
          </button>
        ))}
      </span>
    </div>
  );
}

export function EconMap({ bundle, year }: { bundle: Bundle; year: string }) {
  const [selected, setSelected] = useState<string>("inventory");

  const yearNodes = useMemo(
    () => bundle.econ_map_nodes.filter((n) => yearOf(n.end_date) === year),
    [bundle, year],
  );
  const byId = useMemo(() => new Map(yearNodes.map((n) => [n.node_id, n])), [yearNodes]);
  const layer = (l: number) => yearNodes.filter((n) => n.layer === l);

  /** 统一金额比例尺：取两条资产恒等式堆叠合计与各流量绝对值的最大者。 */
  const scaleMax = useMemo(() => {
    const stackSum = (l: number) =>
      layer(l).reduce((s, n) => s + Math.max(n.value ?? 0, 0), 0);
    const flowMax = Math.max(0, ...yearNodes.filter((n) => n.flow_or_stock === "flow")
      .map((n) => Math.abs(n.value ?? 0)));
    return Math.max(stackSum(1), stackSum(2), flowMax) || 1;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [yearNodes]);

  const checks = useMemo(
    () => bundle.econ_map_checks.filter((c) => yearOf(c.end_date) === year),
    [bundle, year],
  );
  const checkOf = (l: number) => checks.find((c) => c.layer === l)?.residual;

  const sel = byId.get(selected) ?? yearNodes[0];
  const selHistory = useMemo(
    () => bundle.econ_map_nodes.filter((n) => n.node_id === (sel?.node_id ?? "")),
    [bundle, sel],
  );

  if (!sel) return <div className="status">{year}年暂无经济地图数据。</div>;
  const components = JSON.parse(sel.components_json) as { concept: string; value: number }[];
  const related = JSON.parse(sel.related_json) as string[];

  /** 瀑布几何：锚点（净利润、CFO、FCF）按报表值从 0 画起；调整项自上一
   *  锚点累计偏移；资本开支按已声明的“CFO − 资本开支”关系作扣减绘制。 */
  const wf = (() => {
    const seq: { id: string; kind: "anchor" | "adj" | "sub" }[] = [
      { id: "net_income", kind: "anchor" },
      { id: "noncash_addbacks", kind: "adj" },
      { id: "owc_change", kind: "adj" },
      { id: "cfo", kind: "anchor" },
      { id: "capex", kind: "sub" },
      { id: "fcf_simple", kind: "anchor" },
    ];
    let run = 0;
    const rows: { node: EconMapNode; kind: string; base: number; delta: number | null }[] = [];
    for (const { id, kind } of seq) {
      const node = byId.get(id);
      if (!node) continue;
      const v = node.value;
      if (v == null) { rows.push({ node, kind, base: 0, delta: null }); continue; }
      if (kind === "anchor") { run = v; rows.push({ node, kind, base: 0, delta: v }); continue; }
      const delta = kind === "sub" ? -v : v;
      rows.push({ node, kind, base: Math.min(run, run + delta), delta });
      run += delta;
    }
    return rows;
  })();

  /** 天数（营运资金表联接）。 */
  const dv = (k: string) => relatedValue(bundle, year, k);
  const dio = dv("dio"), dso = dv("dso"), dpo = dv("dpo"), adv = dv("advance_days"), ccc = dv("ccc");
  const dayMax = Math.max(
    (isNum(dio) ? dio : 0) + (isNum(dso) ? dso : 0),
    (isNum(dpo) ? dpo : 0) + (isNum(adv) ? adv : 0),
  ) || 1;

  const annot = (k: string) => {
    const src = METRIC_SOURCES[k];
    return src ? `${src.label} ${fmtMetric(relatedValue(bundle, year, k), src.fmt)}` : undefined;
  };

  return (
    <div className="map">
      <div className="map__flow">
        <p className="map__intro">
          按一年的经济循环自上而下阅读：出资人与上下游投入资本 → 资本在一年内演化与周转 →
          周转创造收入与利润 → 利润转成现金 → 现金再投资或分配，进入下一年循环。
          金额条形共用同一比例尺（年度演化与营运资金循环两节使用各自标注的比例尺）；
          点击任意项目在右侧查看口径、历史与相关指标。
        </p>

        <section className="mapsec" aria-label="资本结构">
          <div className="mapsec__head">
            <h3><span className="mapsec__no">①</span>资本结构：钱从哪里来，投到了哪里</h3>
            <span className="mapsec__tag">存量 · {year}年末</span>
          </div>
          <p className="mapsec__sub">
            两条等长即会计恒等式“资产 = 负债 + 所有者权益”：上条按出资人分（权益、金融负债与经营性信用），
            下条按资金形态分（经营资产与金融资产）。
          </p>
          <StackBar title="资本来源（谁出的钱）" nodes={layer(1)} scaleMax={scaleMax}
            selected={sel.node_id} onSelect={setSelected} />
          <StackBar title="资本占用（钱变成了什么）" nodes={layer(2)} scaleMax={scaleMax}
            selected={sel.node_id} onSelect={setSelected} />
          <CheckLine label="来源合计与报表资产总计恒等式校验" residual={checkOf(1)} />
          <CheckLine label="占用合计与报表资产总计恒等式校验" residual={checkOf(2)} />
        </section>

        <Connector text="年末结构从何而来？对照年初余额，看资本一年内的增减与去向" />

        <EvolutionSection bundle={bundle} year={year} selected={sel.node_id} onSelect={setSelected} />

        <Connector text="经营资产周而复始地转为存货、应收与现金 —— 一元资金被占用多久？" />

        <section className="mapsec" aria-label="营运资金循环">
          <div className="mapsec__head">
            <h3><span className="mapsec__no">③</span>营运资金循环：资金被占用多久</h3>
            <span className="mapsec__tag">天数 · {year}年（本节为天数比例尺）</span>
          </div>
          <DayBar year={year} title="自有资金被占用" dayMax={dayMax}
            parts={[
              { label: "存货周转天数（DIO）", nodeId: "inventory", metric: "dio", color: "#1e3a8a", v: dio },
              { label: "应收款项周转天数（DSO）", nodeId: "receivables_prepaid", metric: "dso", color: "#3b82f6", v: dso },
            ]}
            marker={{ label: "现金循环周期（CCC）", v: ccc }}
            selected={sel.node_id} onSelect={setSelected} />
          <DayBar year={year} title="上下游资金垫付" dayMax={dayMax}
            parts={[
              { label: "应付款项周转天数（DPO）", nodeId: "supplier_credit", metric: "dpo", color: "#1d4ed8", v: dpo },
              { label: "客户预收款天数", nodeId: "customer_advances", metric: "advance_days", color: "#b45309", v: adv },
            ]}
            selected={sel.node_id} onSelect={setSelected} />
          <p className="mapsec__note">
            现金循环周期（CCC）= 存货天数 + 应收天数 − 应付天数 ≈ <b><AuditValue year={year} code="ccc">{fmtMetric(ccc, "days")}</AuditValue></b>（▲标记）。
            口径说明：客户预收款天数不并入 CCC，单独列示以免掩盖客户资金的贡献；
            应付天数的采购额近似为营业成本加存货增加额。
          </p>
        </section>

        <Connector text="资产周转创造全年收入">
          <Kpi bundle={bundle} year={year} k="ato" caliber="营业总收入 ÷ 平均净经营资产" />
        </Connector>

        <section className="mapsec" aria-label="经营成果">
          <div className="mapsec__head">
            <h3><span className="mapsec__no">④</span>经营成果：收入沉淀为多少利润</h3>
            <span className="mapsec__tag">流量 · {year}年全年</span>
          </div>
          <p className="mapsec__sub">
            自上而下为利润漏斗（与①同一金额比例尺，可与投入资本直接比较）。
            税后经营收益（OI）为重构口径，不等同于报表“营业利润”。
          </p>
          <FlowRow node={byId.get("total_revenue")} scaleMax={scaleMax} color={SEG_COLORS.total_revenue}
            selected={sel.node_id} onSelect={setSelected} />
          <FlowRow node={byId.get("gross_profit")} scaleMax={scaleMax} color={SEG_COLORS.gross_profit}
            annotation={annot("gross_margin")} selected={sel.node_id} onSelect={setSelected} />
          <FlowRow node={byId.get("oi_core_pretax")} scaleMax={scaleMax} color={SEG_COLORS.oi_core_pretax}
            annotation={annot("opm_core")} selected={sel.node_id} onSelect={setSelected} />
          <FlowRow node={byId.get("unusual_items")} scaleMax={scaleMax} color={SEG_COLORS.unusual_items}
            selected={sel.node_id} onSelect={setSelected} />
          <FlowRow node={byId.get("oi_after_tax")} scaleMax={scaleMax} color={SEG_COLORS.oi_after_tax}
            annotation={annot("opm")} selected={sel.node_id} onSelect={setSelected} />
          <div className="mapsec__kpis">
            <Kpi bundle={bundle} year={year} k="rnoa" caliber="税后经营收益 ÷ 平均净经营资产" />
          </div>
          <CheckLine label="税前重分类恒等式校验（R4）" residual={checkOf(3)} />
        </section>

        <Connector text="权责发生制利润要落袋为真金白银">
          <Kpi bundle={bundle} year={year} k="cash_conversion" caliber="经营活动现金流量净额 ÷ 净利润" />
        </Connector>

        <section className="mapsec" aria-label="现金转换">
          <div className="mapsec__head">
            <h3><span className="mapsec__no">⑤</span>现金转换：利润变成多少现金</h3>
            <span className="mapsec__tag">流量 · {year}年全年</span>
          </div>
          <p className="mapsec__sub">
            按披露的间接法：净利润加回非付现项目、加减营运资本变动得经营现金流；
            再扣现金资本开支得简式自由现金流。深灰蓝为合计锚点，蓝为加项，红为减项。
          </p>
          {wf.map(({ node, kind, base, delta }) => (
            <FlowRow key={node.node_id} node={node} scaleMax={scaleMax}
              offsetPct={(base / scaleMax) * 100}
              color={kind === "anchor" ? ANCHOR : (delta ?? 0) >= 0 ? POS_ADJ : NEG}
              op={kind === "anchor" ? undefined : (delta ?? 0) >= 0 ? "+" : "−"}
              selected={sel.node_id} onSelect={setSelected} />
          ))}
          <CheckLine label="净利润—经营现金流桥恒等式校验" residual={checkOf(4)} />
        </section>

        <Connector text="到手的现金由公司配置：再投入经营，或回馈出资人" />

        <section className="mapsec" aria-label="资本配置">
          <div className="mapsec__head">
            <h3><span className="mapsec__no">⑥</span>资本配置：现金流向了哪里</h3>
            <span className="mapsec__tag">流量 · {year}年全年</span>
          </div>
          <p className="mapsec__sub">按报表现金流出入列示；各项口径限制见右侧说明，未披露项如实标注。</p>
          <p className="mapsec__group">现金流出</p>
          <FlowRow node={byId.get("capex_alloc")} scaleMax={scaleMax} color={SEG_COLORS.capex_alloc}
            selected={sel.node_id} onSelect={setSelected} />
          <FlowRow node={byId.get("dividends_interest")} scaleMax={scaleMax} color={SEG_COLORS.dividends_interest}
            selected={sel.node_id} onSelect={setSelected} />
          <FlowRow node={byId.get("debt_repaid")} scaleMax={scaleMax} color={SEG_COLORS.debt_repaid}
            selected={sel.node_id} onSelect={setSelected} />
          <FlowRow node={byId.get("other_financing_out")} scaleMax={scaleMax} color={SEG_COLORS.other_financing_out}
            selected={sel.node_id} onSelect={setSelected} />
          <p className="mapsec__group">现金流入与结余</p>
          <FlowRow node={byId.get("equity_raised")} scaleMax={scaleMax} color={SEG_COLORS.equity_raised}
            selected={sel.node_id} onSelect={setSelected} />
          <FlowRow node={byId.get("net_cash_change")} scaleMax={scaleMax} color={SEG_COLORS.net_cash_change}
            selected={sel.node_id} onSelect={setSelected} />
          <div className="mapsec__kpis">
            <Kpi bundle={bundle} year={year} k="reinvestment_rate" caliber="净经营资产增加额 ÷ 税后经营收益" />
            <Kpi bundle={bundle} year={year} k="capex_to_da" caliber="现金资本开支 ÷ 折旧与摊销" />
          </div>
          <CheckLine label="现金流量表恒等式校验（CFO+CFI+CFF+汇率影响 = 现金净增加）" residual={checkOf(5)} />
          <p className="mapsec__loop">
            ↺ 现金结余沉淀为①中的金融资产，再投资沉淀为经营资产 —— 进入下一年的资本结构。
          </p>
        </section>
      </div>

      <aside className="inspector">
        <div className="inspector__head">
          <h3>{sel.label}</h3>
          <span className={`tag ${sel.flow_or_stock === "stock" ? "tag--stock" : "tag--flow"}`}>
            {sel.flow_or_stock === "stock" ? "存量 · 年末" : "流量 · 全年"}
          </span>
        </div>
        <p className="inspector__note"><KnowledgeLink concept={conceptFor("map", sel.node_id)} year={year} /></p>
        {sel.note && <p className="inspector__note">{sel.note}</p>}

        <h4>历史数据（亿元）</h4>
        <NodeHistory nodes={selHistory} />

        {components.length > 0 && (
          <>
            <h4>构成科目，{year}年（亿元）</h4>
            <table className="inspector__table">
              <tbody>
                {components.map((c) => (
                  <tr key={c.concept}>
                    <td title={c.concept}>{accountLabel(c.concept)}</td>
                    <td className="num"><AuditValue year={year} code={`raw:${c.concept}`}>{formatAmount(c.value)}</AuditValue></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {related.length > 0 && (
          <>
            <h4>相关指标，{year}年</h4>
            <table className="inspector__table">
              <tbody>
                {related.map((key) => (
                  <tr key={key}>
                    <td><KnowledgeLink concept={conceptFor("metrics", key)} year={year}>{METRIC_SOURCES[key]?.label ?? key}</KnowledgeLink></td>
                    <td className="num">
                      <AuditValue year={year} code={key}>{fmtMetric(relatedValue(bundle, year, key), METRIC_SOURCES[key]?.fmt ?? "ratio")}</AuditValue>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="inspector__caveat">
              以上为会计定义关联；跨期相关性不代表因果关系。
            </p>
          </>
        )}
      </aside>
    </div>
  );
}
