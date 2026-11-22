/** 年度演化：年初 → 年末，各资本科目的余额如何变化，并把账面变动与
 *  报表"披露流量"（现金流量表、补充资料、利润表）逐项勾稽：
 *      期初余额 + 披露流量 + 推算轧差 = 期末余额（按构造精确成立）
 *  所有数值在 Python 中算好导出（econ_evolution_*）；本组件只做排序、
 *  比例尺与瀑布偏移等图形几何。披露与推算在视觉上严格区分：
 *  实色＝报表披露流量，斜纹＝推算轧差（不代表科目间的直接转换）。 */
import { useMemo } from "react";
import { yearOf } from "./data";
import { AuditValue } from "./CalculationPopover";
import { auditTarget } from "./calculationDetails";
import { formatAmount, formatResidual } from "./format";

/** 极小非零金额不得显示成 0.00 亿元：缩小到万元乃至元级展示（AGENTS 约定）。 */
function fmtFlowAmount(yuan: number): string {
  const a = Math.abs(yuan);
  if (a !== 0 && a < 5_000) return formatResidual(yuan);
  if (a !== 0 && a < 50_000_000) return formatAmount(yuan, "万元", 1);
  return formatAmount(yuan);
}
import type { Bundle, EconEvolutionFlow, EconEvolutionGroup } from "./types";

const POS = "#1d4ed8";
const NEG = "#b91c1c";
const ANCHOR = "#334155";

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const nz = (v: number | null): number => (isNum(v) ? v : 0);

const BASIS_LABEL: Record<EconEvolutionFlow["basis"], string> = {
  balance: "报表余额",
  disclosed_cashflow: "现金流量表",
  disclosed_supplemental: "补充资料",
  disclosed_income: "利润表",
  inferred_residual: "推算轧差",
};

/** 单科目变动行：余额变动的发散条（蓝＝增加，红＝减少，零轴对齐）。 */
function DeltaRow({ g, span, zeroPct, selected, onSelect }: {
  g: EconEvolutionGroup; span: number; zeroPct: number;
  selected: string; onSelect: (id: string) => void;
}) {
  const d = g.delta;
  const major = isNum(g.delta_share_of_assets) && Math.abs(g.delta_share_of_assets) >= 0.01;
  const w = isNum(d) ? (Math.abs(d) / span) * 100 : 0;
  const left = !isNum(d) ? zeroPct : d >= 0 ? zeroPct : zeroPct - w;
  return (
    <button type="button"
      className={`evo-row${selected === g.group_id ? " evo-row--active" : ""}${major ? " evo-row--major" : ""}`}
      {...auditTarget(g.end_date, `delta:${g.group_id}`)} onClick={() => onSelect(g.group_id)}>
      <span className="evo-row__label">
        {g.label}
        <small className="evo-row__range">
          {formatAmount(g.begin_value, "亿元", 0)} → {formatAmount(g.end_value, "亿元", 0)}
        </small>
      </span>
      <span className="evo-row__track">
        <span className="evo-row__zero" style={{ left: `${zeroPct}%` }} aria-hidden="true" />
        {isNum(d) && (
          <span className="evo-row__bar"
            style={{ left: `${left}%`, width: `${w}%`, background: d >= 0 ? POS : NEG }} />
        )}
      </span>
      <span className={`evo-row__value${isNum(d) && d < 0 ? " evo-row__value--neg" : ""}`}>
        {!isNum(d) ? (g.evo_flags || "未披露") : `${d >= 0 ? "+" : ""}${formatAmount(d, "亿元", 1)}`}
        {isNum(g.delta_share_of_assets) && (
          <small>占年初总资产 {(g.delta_share_of_assets * 100).toFixed(1)}%</small>
        )}
      </span>
    </button>
  );
}

/** 勾稽桥的一行（非按钮：披露项不是地图节点）。瀑布偏移为图形几何。 */
function BridgeRow({ s, base, scale }: { s: EconEvolutionFlow; base: number; scale: number }) {
  const v = s.value;
  const anchor = s.step_kind !== "adjustment";
  const inferred = s.basis === "inferred_residual";
  const w = isNum(v) ? (Math.abs(v) / scale) * 100 : 0;
  const offset = anchor ? 0 : (base / scale) * 100;
  return (
    <div className="frow frow--static" tabIndex={0} {...auditTarget(s.end_date, `flow:${s.panel_id}:${s.concept}`)}>
      <span className="frow__label">
        {!anchor && <em className="frow__op">{isNum(v) && v < 0 ? "−" : "+"}</em>}
        {s.label}
        <span className={`evo-badge evo-badge--${inferred ? "inferred" : anchor ? "balance" : "disclosed"}`}>
          {BASIS_LABEL[s.basis]}
        </span>
      </span>
      <span className="frow__track">
        {isNum(v) && (
          <span
            className={`frow__fill${inferred ? " evo-fill--inferred" : ""}`}
            style={{
              marginLeft: `${offset}%`, width: `${w}%`,
              background: inferred ? undefined : anchor ? ANCHOR : v >= 0 ? POS : NEG,
            }} />
        )}
      </span>
      <span className={`frow__value${isNum(v) && v < 0 ? " frow__value--neg" : ""}`}>
        {isNum(v) ? fmtFlowAmount(v) : "未披露"}
      </span>
    </div>
  );
}

export function EvolutionSection({ bundle, year, selected, onSelect }: {
  bundle: Bundle; year: string; selected: string; onSelect: (id: string) => void;
}) {
  const groups = useMemo(
    () => bundle.econ_evolution_groups.filter((g) => yearOf(g.end_date) === year),
    [bundle, year],
  );
  const flows = useMemo(
    () => bundle.econ_evolution_flows.filter((f) => yearOf(f.end_date) === year),
    [bundle, year],
  );
  const checks = useMemo(
    () => bundle.econ_evolution_checks.filter((c) => yearOf(c.end_date) === year),
    [bundle, year],
  );

  const prevYear = String(Number(year) - 1);
  const firstYear = groups.length > 0 && groups.every((g) => g.begin_value == null);

  /** 发散条比例尺：正负向最大变动决定零轴位置，两列共用。 */
  const posMax = Math.max(0, ...groups.map((g) => nz(g.delta)));
  const negMax = Math.max(0, ...groups.map((g) => -nz(g.delta)));
  const span = posMax + negMax || 1;
  const zeroPct = (negMax / span) * 100;

  const bySide = (side: EconEvolutionGroup["side"]) =>
    [...groups.filter((g) => g.side === side)]
      .sort((a, b) => Math.abs(nz(b.delta)) - Math.abs(nz(a.delta)));

  const totalAssets = (y: string) => bundle.reformulated_bs
    .find((r) => yearOf(r.end_date) === y)?.total_assets_reported ?? null;
  const assetChange = bundle.calculation_details?.[`${year}1231`]?.delta_assets?.value ?? null;

  /** 当前勾稽面板：选中科目所属面板；否则默认变动最大的科目。 */
  const activePanel = useMemo(() => {
    const bySel = groups.find((g) => g.group_id === selected);
    if (bySel) return bySel.panel_id;
    const largest = [...groups].sort(
      (a, b) => Math.abs(nz(b.delta)) - Math.abs(nz(a.delta)))[0];
    return largest?.panel_id;
  }, [groups, selected]);

  const panelSteps = useMemo(
    () => flows.filter((f) => f.panel_id === activePanel)
      .sort((a, b) => a.step_order - b.step_order),
    [flows, activePanel],
  );
  const panelMembers = groups.filter((g) => g.panel_id === activePanel);

  /** 瀑布几何：锚点从 0 画起，调整项按累计偏移。 */
  const bridge = useMemo(() => {
    let run = 0;
    const rows: { s: EconEvolutionFlow; base: number }[] = [];
    for (const s of panelSteps) {
      const v = s.value;
      if (s.step_kind !== "adjustment") {
        if (isNum(v)) run = v;
        rows.push({ s, base: 0 });
        continue;
      }
      const d = nz(v);
      rows.push({ s, base: Math.min(run, run + d) });
      run += d;
    }
    const scale = Math.max(1, ...rows.map(({ s, base }) =>
      Math.max(Math.abs(base), Math.abs(base) + Math.abs(nz(s.value)))));
    return { rows, scale };
  }, [panelSteps]);

  const notes = panelSteps.filter((s) => s.note);
  const checkOf = (prefix: string) =>
    checks.find((c) => c.check.startsWith(prefix))?.residual;

  return (
    <section className="mapsec" aria-label="年度演化">
      <div className="mapsec__head">
        <h3><span className="mapsec__no">②</span>年度演化：年初到年末，资本发生了什么</h3>
        <span className="mapsec__tag">存量变动 · {prevYear}年末 → {year}年末（本节为变动额比例尺）</span>
      </div>
      {firstYear ? (
        <p className="mapsec__note">{year}年为数据首年，缺少期初余额，无法展示年度演化。</p>
      ) : (
        <>
          <p className="mapsec__sub">
            总资产由年初 <AuditValue year={prevYear} code="raw:total_assets">{formatAmount(totalAssets(prevYear), "亿元", 0)}</AuditValue>
            {" "}变为年末 <AuditValue year={year} code="raw:total_assets">{formatAmount(totalAssets(year), "亿元", 0)}</AuditValue>
            （变动 <AuditValue year={year} code="delta_assets">{formatAmount(assetChange, "亿元", 1)}</AuditValue>）。下表按变动额排序（蓝＝增加，红＝减少，加粗＝变动超过年初总资产的
            1%）；点击科目，在下方查看其变动与利润表、现金流量表披露流量的勾稽。
          </p>
          <div className="evo__cols">
            <div>
              <p className="evo__side-title">资本占用（资产端）的变动</p>
              {bySide("employment").map((g) => (
                <DeltaRow key={g.group_id} g={g} span={span} zeroPct={zeroPct}
                  selected={selected} onSelect={onSelect} />
              ))}
            </div>
            <div>
              <p className="evo__side-title">资本来源（负债与权益端）的变动</p>
              {bySide("sources").map((g) => (
                <DeltaRow key={g.group_id} g={g} span={span} zeroPct={zeroPct}
                  selected={selected} onSelect={onSelect} />
              ))}
            </div>
          </div>

          {panelSteps.length > 0 && (
            <div className="evo-bridge">
              <p className="evo-bridge__title">
                变动勾稽：{panelSteps[0].panel_label}（期初 ＋ 披露流量 ＋ 推算轧差 ＝ 期末）
              </p>
              {panelMembers.length > 1 && (
                <p className="mapsec__note">
                  本面板合并勾稽以下科目（披露口径无法按科目拆分）：
                  {panelMembers.map((m) => m.label).join("、")}。
                </p>
              )}
              <div className="evo-legend">
                <span><i style={{ background: POS }} />披露流量（现金流量表／补充资料／利润表）</span>
                <span><i className="evo-fill--inferred" />推算轧差（账面变动 − 披露流量）</span>
                <span><i style={{ background: ANCHOR }} />期初／期末余额</span>
              </div>
              {bridge.rows.map(({ s, base }) => (
                <BridgeRow key={`${s.step_order}-${s.concept}`} s={s} base={base} scale={bridge.scale} />
              ))}
              {notes.length > 0 && (
                <ul className="evo-notes">
                  {notes.map((s) => (
                    <li key={`${s.step_order}-${s.concept}`}><b>{s.label}</b>：{s.note}</li>
                  ))}
                </ul>
              )}
              <p className="mapsec__note">
                口径声明：账面差额不代表科目之间的直接转换。披露流量为报表口径（现金收付或补充资料），与账面变动的差额一律如实列为"推算轧差"，不强制轧平、不虚构去向。
              </p>
            </div>
          )}

          <CheckText label="来源端变动合计与报表总资产变动恒等式校验（E1）" residual={checkOf("E1")} />
          <CheckText label="占用端变动合计与报表总资产变动恒等式校验（E2）" residual={checkOf("E2")} />
          <CheckText label="现金期初＋净增加＝期末（披露值滚动校验，E4）" residual={checkOf("E4")} />
        </>
      )}
    </section>
  );
}

function CheckText({ label, residual }: { label: string; residual: number | null | undefined }) {
  return (
    <p className="mapsec__check">
      {label}：差额 {isNum(residual) ? formatResidual(residual) : "—"}（如实列示，不强制轧平）
    </p>
  );
}
