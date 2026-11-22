import { palette } from "./charts/theme";

// 三张重构报表的勾稽示意图（Penman 口径），展示在相关概念条目中。
const ARTICULATION_IDS = new Set(["reformulation", "noa", "nfo", "oi", "fcf"]);
export function showsArticulation(id: string | undefined): boolean {
  return !!id && ARTICULATION_IDS.has(id);
}

const card = { fill: "var(--panel)", stroke: "var(--line)" };

export function ArticulationDiagram() {
  return <figure className="articulation">
    <svg viewBox="0 0 940 700" role="img"
      aria-label="重构利润表、重构资产负债表与重构现金流量表的勾稽关系示意图">
      <title>三张重构报表如何勾稽</title>
      <defs>
        <marker id="arrow-op" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L8 4 L0 8 Z" fill={palette.operating} />
        </marker>
        <marker id="arrow-fin" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L8 4 L0 8 Z" fill={palette.financing} />
        </marker>
        <marker id="arrow-eq" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L8 4 L0 8 Z" fill={palette.equity} />
        </marker>
      </defs>

      <g className="articulation__label">
        <circle cx="30" cy="26" r="5" fill={palette.operating} />
        <text x="41" y="31">经营</text>
        <circle cx="92" cy="26" r="5" fill={palette.financing} />
        <text x="103" y="31">融资</text>
        <circle cx="154" cy="26" r="5" fill={palette.equity} />
        <text x="165" y="31">权益</text>
      </g>

      {/* 重构利润表 */}
      <rect x="300" y="16" width="340" height="128" rx="7" {...card} />
      <text x="470" y="46" textAnchor="middle" fill="var(--ink)" className="articulation__title">重构利润表</text>
      <text x="470" y="76" textAnchor="middle" fill={palette.operating}>税后经营收益（OI）</text>
      <text x="470" y="100" textAnchor="middle" fill={palette.financing}>－ 税后净财务费用（NFE）</text>
      <text x="470" y="124" textAnchor="middle" fill={palette.equity}>＝ 合并净利润（项目计量）</text>

      {/* 重构资产负债表 */}
      <rect x="20" y="204" width="900" height="240" rx="7" fill="#f4f7fd" stroke="#b5c9f6" />
      <text x="40" y="236" fill="var(--ink)" className="articulation__title">重构资产负债表</text>
      <text x="250" y="284" textAnchor="middle" fill={palette.operating}>净经营资产 NOA₁ ＝ NOA₀ ＋ OI － FCF</text>
      <text x="690" y="284" textAnchor="middle" fill={palette.financing}>净金融负债 NFO₁ ＝ NFO₀ ＋ NFE － FCF ＋ 净股利 d</text>
      <line x1="60" y1="322" x2="880" y2="322" stroke="var(--line)" strokeDasharray="4 4" />
      <text x="470" y="366" textAnchor="middle" fill={palette.equity}>合并权益 TE₁ ＝ TE₀ ＋ 合并综合收益 － 净分配 d</text>
      <text x="470" y="404" textAnchor="middle" fill={palette.equity}>TE₁ ＝ NOA₁ － NFO₁；CSE₁ ＝ TE₁ － 少数股东权益</text>

      {/* 重构现金流量表 */}
      <rect x="190" y="504" width="560" height="180" rx="7" {...card} />
      <text x="470" y="534" textAnchor="middle" fill="var(--ink)" className="articulation__title">重构现金流量表</text>
      <text x="470" y="568" textAnchor="middle" fill={palette.operating}>经营端：FCF ＝ OI － ΔNOA</text>
      <text x="470" y="596" textAnchor="middle" fill={palette.financing}>融资端：FCF ＝ NFE － ΔNFO ＋ 净股利 d</text>
      <rect x="214" y="614" width="512" height="48" rx="5" fill="#eff4ff" />
      <text x="470" y="637" textAnchor="middle" className="articulation__note" fill={palette.ink}>两式在综合收益与净分配口径一致时勾稽</text>
      <text x="470" y="655" textAnchor="middle" className="articulation__note" fill={palette.ink}>净分配包含合并口径下少数股东的交易</text>

      {/* 勾稽箭头 */}
      <g fill="none" strokeWidth="1.6">
        <path d="M300 72 H250 V200" stroke={palette.operating} markerEnd="url(#arrow-op)" />
        <path d="M640 96 H690 V200" stroke={palette.financing} markerEnd="url(#arrow-fin)" />
        <path d="M470 144 V200" stroke={palette.equity} markerEnd="url(#arrow-eq)" />
        <path d="M190 564 H150 V448" stroke={palette.operating} markerEnd="url(#arrow-op)" />
        <path d="M750 596 H790 V448" stroke={palette.financing} markerEnd="url(#arrow-fin)" />
      </g>
      <g className="articulation__label">
        <text x="242" y="180" textAnchor="end">OI</text>
        <text x="698" y="180">NFE</text>
        <text x="478" y="180">合并净利润</text>
        <text x="142" y="500" textAnchor="end">FCF</text>
        <text x="798" y="500">FCF</text>
      </g>
    </svg>
    <figcaption>
      <ul className="articulation__caption">
        <li>OI 为重构口径的税后经营收益（所得税在经营与融资之间按明确税率分摊），不直接等同于利润表“营业利润”；NFE 为税后净财务费用，净财务收益时符号为负。</li>
        <li>NFO 为净金融负债＝金融负债－金融资产；净股利 d ＝ 现金分红 ＋ 回购 － 增发。示意基于合并口径，权益含少数股东权益。原文示意中的 OI、NFE 按综合收益口径划分，项目实际计算的 OI 与 NFE 由净利润重构。</li>
        <li>此处 FCF 为重构口径（OI － ΔNOA），与报表简式口径的差异及勾稽差额见“自由现金流的不同口径”。</li>
      </ul>
    </figcaption>
  </figure>;
}
