/** Profitability Driver Tree: expandable RNOA/ROTCE decomposition.
 *  Structure, values, weights and identity residuals all come precomputed
 *  from Python (driver_tree_nodes / driver_tree_checks); this view renders,
 *  expands/collapses and joins declared related-metric keys — it never
 *  computes a financial number.
 */
import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";
import { axisStyle, baseTextStyle, palette } from "./charts/theme";
import { toPercent, yearOf } from "./data";
import { METRIC_SOURCES, fmtMetric, relatedValue } from "./metrics";
import type { Bundle, DriverTreeNode } from "./types";
import { useECharts } from "./useECharts";
import { AuditValue } from "./CalculationPopover";
import { auditTarget } from "./calculationDetails";
import { KnowledgeLink } from "./KnowledgeLink";
import { conceptFor } from "./knowledge";

const BASIS = "average";
const DEFAULT_EXPANDED = ["rotce", "rnoa"];

const RELATION_TAGS: Partial<Record<DriverTreeNode["relation"], string>> = {
  residual: "余项",
  context: "参考",
  reciprocal: "上级指标的倒数",
};

function fmtNodeValue(n: DriverTreeNode): string {
  if (n.value == null) return "—";
  return fmtMetric(n.value, n.node_id === "spread" ? "pp" : n.fmt);
}

function NodeHistory({ nodes }: { nodes: DriverTreeNode[] }) {
  const option = useMemo<EChartsOption>(() => {
    const rows = [...nodes].sort((a, b) => a.end_date.localeCompare(b.end_date));
    const pct = rows[0]?.fmt === "pct";
    const pp = rows[0]?.node_id === "spread";
    return {
      textStyle: baseTextStyle,
      grid: { left: 48, right: 8, top: 8, bottom: 22 },
      tooltip: {
        trigger: "axis",
        valueFormatter: (v) =>
          v == null ? "—" : pct ? `${(v as number).toFixed(1)}${pp ? " 个百分点" : "%"}` : `${(v as number).toFixed(2)}×`,
      },
      xAxis: { type: "category", data: rows.map((r) => yearOf(r.end_date)), ...axisStyle() },
      yAxis: { type: "value", ...axisStyle() },
      series: [{
        type: "line",
        data: rows.map((r) => (pct ? toPercent(r.value) : r.value)),
        color: palette.operating,
        symbolSize: 4,
        areaStyle: { opacity: 0.08 },
      }],
    };
  }, [nodes]);
  return <div ref={useECharts(option, ({ axisValueLabel }) =>
    nodes[0] ? { date: `${axisValueLabel}1231`, code: `tree:${nodes[0].node_id}` } : undefined)} className="inspector__chart" />;
}

export function DriverTree({ bundle, year }: { bundle: Bundle; year: string }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set(DEFAULT_EXPANDED));
  const [selected, setSelected] = useState<string>("rnoa");

  const yearNodes = useMemo(
    () =>
      bundle.driver_tree_nodes
        .filter((n) => n.basis === BASIS && yearOf(n.end_date) === year)
        .sort((a, b) => a.sort_order - b.sort_order),
    [bundle, year],
  );
  const childrenOf = useMemo(() => {
    const m = new Map<string, DriverTreeNode[]>();
    for (const n of yearNodes) {
      if (n.parent_id == null) continue;
      const list = m.get(n.parent_id) ?? [];
      list.push(n);
      m.set(n.parent_id, list);
    }
    return m;
  }, [yearNodes]);

  const sel = yearNodes.find((n) => n.node_id === selected) ?? yearNodes[0];
  const selHistory = useMemo(
    () =>
      bundle.driver_tree_nodes.filter(
        (n) => n.basis === BASIS && n.node_id === (sel?.node_id ?? ""),
      ),
    [bundle, sel],
  );
  const checks = useMemo(
    () =>
      bundle.driver_tree_checks.filter(
        (c) => c.basis === BASIS && yearOf(c.end_date) === year,
      ),
    [bundle, year],
  );
  const maxResidual = Math.max(...checks.map((c) => Math.abs(c.residual ?? 0)), 0);
  const nullChecks = checks.filter((c) => c.residual == null).length;

  if (!sel) return <div className="status">{year}年暂无盈利驱动树数据。</div>;
  const related = JSON.parse(sel.related_json) as string[];

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const renderNode = (n: DriverTreeNode): JSX.Element => {
    const kids = childrenOf.get(n.node_id) ?? [];
    const open = expanded.has(n.node_id);
    const tag = RELATION_TAGS[n.relation];
    return (
      <div key={n.node_id}>
        <button
          className={`trow ${sel.node_id === n.node_id ? "trow--active" : ""}`}
          style={{ paddingLeft: 8 + n.depth * 18 }}
          {...auditTarget(n.end_date, `tree:${n.node_id}`)}
          onClick={() => setSelected(n.node_id)}
        >
          <span
            className={`trow__chevron ${kids.length === 0 ? "trow__chevron--leaf" : ""}`}
            onClick={(e) => {
              if (kids.length === 0) return;
              e.stopPropagation();
              toggle(n.node_id);
            }}
          >
            {kids.length > 0 ? (open ? "▾" : "▸") : "·"}
          </span>
          {n.weight != null && n.weight < 0 && (
            <span className="trow__sign" title="以减项计入上级合计">−</span>
          )}
          <span className="trow__label">{n.label}</span>
          {tag && <span className="trow__tag">{tag}</span>}
          <span className={`trow__value ${n.value != null && n.value < 0 ? "trow__value--neg" : ""}`}>
            {fmtNodeValue(n)}
          </span>
        </button>
        {open && kids.map(renderNode)}
      </div>
    );
  };

  const roots = yearNodes.filter((n) => n.parent_id == null);

  return (
    <div className="map">
      <div className="tree">
        <p className="panel__note">
          Nissim–Penman分解采用平均资本基数。各连接为会计恒等式或定义；子项按正负号加总，“－”表示抵减上级指标，余项如实列示。
        </p>
        {roots.map(renderNode)}
      </div>

      <aside className="inspector">
        <div className="inspector__head">
          <h3>{sel.label}</h3>
          <span className={`tag ${sel.fmt === "pct" ? "tag--stock" : "tag--flow"}`}>
            {sel.node_id === "spread" ? "百分点" : sel.fmt === "pct" ? "百分比" : "倍数"}
          </span>
        </div>
        <p className="inspector__formula">{sel.formula}</p>
        <p className="inspector__note"><KnowledgeLink concept={conceptFor("tree", sel.node_id)} year={year} /></p>
        {sel.note && <p className="inspector__note">{sel.note}</p>}
        {sel.node_flags && <p className="inspector__note flag">提示：{sel.node_flags}</p>}

        <h4>历史数据（{sel.node_id === "spread" ? "百分点" : sel.fmt === "pct" ? "%" : "倍"}，平均资本口径）</h4>
        <NodeHistory nodes={selHistory} />

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

        <p className="inspector__caveat">
          {year}年恒等式校验：最大绝对差额 {maxResidual.toExponential(1)}
          {nullChecks > 0 && `；${nullChecks}项无法计算（分母受限或首年）`}.
          差额如实列示。
        </p>
      </aside>
    </div>
  );
}
